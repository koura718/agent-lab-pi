"""Fixed local-server connection settings shared by both clients."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters

from agent_lab.config import Settings
from agent_lab.logging_config import current_run_id

logger = logging.getLogger(__name__)


def server_parameters() -> StdioServerParameters:
    # The SDK adds only its documented OS environment allowlist. Never copy
    # os.environ here: OPENAI_API_KEY must remain exclusively in the Agent.
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "agent_lab.mcp.server"],
        cwd=Path.cwd().resolve(),
        env={
            "PYTHONIOENCODING": "utf-8",
            "AGENT_LAB_RUN_ID": current_run_id(),
            "AGENT_LAB_SERVER_LOG_LEVEL": logging.getLevelName(
                logging.getLogger("agent_lab").getEffectiveLevel()
            ),
        },
    )


@asynccontextmanager
async def _owned_connection(resource, timeout: float):
    """Keep SDK cancel scopes in one task, outside the caller's cancel scope."""
    ready = asyncio.get_running_loop().create_future()
    stop = asyncio.Event()

    async def own_connection():
        try:
            async with asyncio.timeout(timeout):
                await resource.__aenter__()
        except BaseException as error:
            if not ready.done():
                ready.set_exception(error)
            raise
        try:
            if not ready.done():
                ready.set_result(resource)
            await stop.wait()
        finally:
            await resource.__aexit__(None, None, None)

    owner = asyncio.create_task(own_connection())
    cancelled_before_ready = False
    try:
        yield await asyncio.shield(ready)
    finally:
        stop.set()
        if not ready.done():
            cancelled_before_ready = True
            ready.cancel()
            owner.cancel()
        # Safe to shield here: the SDK's open cancel scopes live in owner,
        # never in this task. Do not clean up SDK scopes in a different task.
        with anyio.CancelScope(shield=True):
            try:
                await owner
            except asyncio.CancelledError:
                if not cancelled_before_ready:
                    raise


@asynccontextmanager
async def diagnostic_connection(settings: Settings):
    client = Client(
        server_parameters(), read_timeout_seconds=settings.call_timeout_seconds
    )
    async with _owned_connection(client, settings.connect_timeout_seconds) as connected:
        logger.info("MCP client connected")
        yield connected
    logger.info("MCP client disconnected")


@asynccontextmanager
async def agent_connection(settings: Settings):
    # Lazy import keeps the diagnostic CLI independent of Agents SDK.
    from agents.mcp import MCPServerStdio

    params = server_parameters().model_dump(exclude_none=True)
    server = MCPServerStdio(
        params=params,
        name="agent-lab-local",
        client_session_timeout_seconds=settings.call_timeout_seconds,
        cache_tools_list=True,
        max_retry_attempts=0,
        use_structured_content=True,
        failure_error_function=None,
    )
    async with _owned_connection(server, settings.connect_timeout_seconds) as connected:
        logger.info("Agent MCP connection established")
        yield connected
    logger.info("Agent MCP connection closed")
