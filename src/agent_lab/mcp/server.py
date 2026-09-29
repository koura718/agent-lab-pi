"""Expose compare_lists over MCP stdio. stdout is protocol-only."""

import asyncio
import json
import logging
from typing import Any

from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError

from agent_lab.domain.list_comparison import (
    ComparisonInputError,
    compare_arguments,
    input_schema,
)
from agent_lab.logging_config import cli_context, error_kind, timed

logger = logging.getLogger("agent_lab.mcp.server")


async def list_tools(
    context: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    if params is not None and params.cursor is not None:
        raise MCPError(-32602, "This server does not accept pagination cursors.")
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="compare_lists",
                description=(
                    "Compare string lists as sets; return sorted same, source_only "
                    "and baseline_only. Preserve case, whitespace and Unicode spelling."
                ),
                inputSchema=input_schema(),
                outputSchema={
                    "type": "object",
                    "properties": {
                        field: {"type": "array", "items": {"type": "string"}}
                        for field in ("same", "source_only", "baseline_only")
                    },
                    "required": ["same", "source_only", "baseline_only"],
                    "additionalProperties": False,
                },
                annotations=types.ToolAnnotations(
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]
    )


def _error_result(code: str, message: str) -> types.CallToolResult:
    # Error results need not conform to the success outputSchema.
    return types.CallToolResult(
        isError=True,
        content=[
            types.TextContent(
                type="text",
                text=json.dumps({"error": {"code": code, "message": message}}),
            )
        ],
    )


@timed(
    "mcp_tool",
    lambda result: (
        "tool_error" if result.model_dump(by_alias=True).get("isError") else "none"
    ),
)
async def call_tool(
    context: ServerRequestContext[Any], params: types.CallToolRequestParams
) -> types.CallToolResult:
    if params.name != "compare_lists":
        raise MCPError(-32602, "Unknown tool.")
    try:
        result = compare_arguments(params.arguments)
    except ComparisonInputError as error:
        logger.warning("compare_lists rejected invalid input")
        return _error_result("INVALID_INPUT", str(error))
    except Exception:  # noqa: BLE001 - sanitize internal failures at the protocol boundary
        logger.error("compare_lists failed internally")
        return _error_result("INTERNAL_ERROR", "Comparison failed internally.")
    logger.info("compare_lists completed")
    return types.CallToolResult(
        content=[
            types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))
        ],
        structuredContent=result,
        isError=False,
    )


def create_server() -> Server:
    return Server(
        "agent-lab-compare-lists",
        version="0.1.0",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


@timed("mcp_server")
async def main() -> None:
    server = create_server()
    logger.info("MCP stdio server starting")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        logger.info("MCP stdio server stopped")


@cli_context(server=True)
def cli() -> int:

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("MCP server interrupted", extra={"error_kind": "cancelled"})
        return 130
    except Exception as error:  # noqa: BLE001 - no request data in terminal errors
        logger.error(
            "MCP server failed (%s)",
            type(error).__name__,
            extra={"error_kind": error_kind(error)},
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
