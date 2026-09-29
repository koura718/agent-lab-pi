"""Real SDK client/server subprocess tests; no model or network required."""

import json
import os
import sys

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from agent_lab.domain.list_comparison import compare_arguments, input_schema
from agent_lab.tools.list_tools import compare_json

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def child_processes(monkeypatch):
    """Observe actual SDK child processes, without replacing their behavior."""
    children = []
    real_open = anyio.open_process

    async def tracked_open(*args, **kwargs):
        child = await real_open(*args, **kwargs)
        children.append((child, kwargs.get("env", {})))
        return child

    monkeypatch.setattr(anyio, "open_process", tracked_open)
    return children


def parameters(cwd):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "agent_lab.mcp.server"],
        cwd=cwd,
        env={"PYTHONIOENCODING": "utf-8"},
    )


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_stdio_contract_and_clean_exit(
    tmp_path, child_processes, monkeypatch, mode
):
    cwd = tmp_path / "日本語 path with spaces"
    cwd.mkdir()
    monkeypatch.setenv("AGENT_LAB_TEST_SECRET", "never-inherit-me")
    cases = [
        {"source": ["A", "B", "B"], "baseline": ["B", "C"]},
        {"source": [], "baseline": []},
        {"source": ["猫", "犬", "猫"], "baseline": ["犬", "鳥"]},
        {"source": [" A", "a", "é"], "baseline": ["A", "e\u0301"]},
        {"source": ["猫" * 256] * 1000, "baseline": []},
    ]
    with (tmp_path / "server.log").open("w+", encoding="utf-8") as log:
        with anyio.fail_after(20):
            async with Client(
                stdio_client(parameters(cwd), errlog=log),
                mode=mode,
                read_timeout_seconds=5,
            ) as client:
                listing = (await client.list_tools()).model_dump(by_alias=True)
                assert [tool["name"] for tool in listing["tools"]] == ["compare_lists"]
                assert listing["tools"][0]["inputSchema"] == input_schema()
                assert listing["tools"][0]["annotations"]["readOnlyHint"] is True
                for arguments in cases:
                    result = (
                        await client.call_tool("compare_lists", arguments)
                    ).model_dump(by_alias=True)
                    assert result["isError"] is False
                    assert result["structuredContent"] == compare_arguments(arguments)
                    assert json.loads(result["content"][0]["text"]) == json.loads(
                        compare_json(json.dumps(arguments))
                    )
                invalid_cases = [
                    {},
                    {"source": [], "baseline": [], "extra": "sensitive-input"},
                    {"source": [1], "baseline": []},
                    {"source": [True], "baseline": []},
                    {"source": [None], "baseline": []},
                    {"source": [""], "baseline": []},
                    {"source": [], "baseline": "not-a-list"},
                    {"source": ["A"] * 1001, "baseline": []},
                    {"source": [], "baseline": ["x" * 257]},
                ]
                for arguments in invalid_cases:
                    result = (
                        await client.call_tool("compare_lists", arguments)
                    ).model_dump(by_alias=True)
                    assert result["isError"] is True
                    error = json.loads(result["content"][0]["text"])
                    assert error["error"]["code"] == "INVALID_INPUT"
                    assert "sensitive-input" not in json.dumps(result)
                with pytest.raises(MCPError):
                    await client.call_tool("unknown-sensitive-name", {})
                # An error must not poison the next request.
                assert (
                    await client.call_tool("compare_lists", cases[0])
                ).is_error is False
        log.seek(0)
        logs = log.read()
    assert "MCP stdio server starting" in logs
    assert "compare_lists completed" in logs
    assert "MCP stdio server stopped" in logs
    assert "sensitive-input" not in logs
    assert "never-inherit-me" not in logs
    assert len(child_processes) == 1
    child, environment = child_processes[0]
    assert child.pid != os.getpid()
    assert child.returncode == 0  # Graceful EOF exit, not just a killed process.
    assert "AGENT_LAB_TEST_SECRET" not in environment
    assert "OPENAI_API_KEY" not in environment


async def test_client_exception_reaps_server(tmp_path, child_processes):
    class ClientFailure(Exception):
        pass

    with anyio.fail_after(15):
        with pytest.RaisesGroup(ClientFailure, flatten_subgroups=True):
            async with Client(parameters(tmp_path), read_timeout_seconds=5) as client:
                await client.list_tools()
                raise ClientFailure()
    assert len(child_processes) == 1
    assert child_processes[0][0].returncode is not None


async def test_cancellation_reaps_server(tmp_path, child_processes):
    with anyio.fail_after(15):
        with anyio.CancelScope() as scope:
            async with Client(parameters(tmp_path), read_timeout_seconds=5) as client:
                await client.list_tools()
                scope.cancel()
                await anyio.sleep_forever()
        assert scope.cancelled_caught
    assert len(child_processes) == 1
    assert child_processes[0][0].returncode is not None
