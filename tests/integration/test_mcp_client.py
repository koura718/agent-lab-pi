import asyncio
import json
import sys
from pathlib import Path

import anyio
import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from mcp import StdioServerParameters
from mcp.shared.exceptions import MCPError

from agent_lab.config import Settings
from agent_lab.main import run_agent
from agent_lab.mcp import connection
from agent_lab.mcp.client import execute

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def assert_reaped(children):
    assert len(children) == 1
    assert children[0][0].returncode is not None


async def test_diagnostics(tmp_path, monkeypatch, child_processes):
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    listing, code = await execute("list-tools", settings)
    assert code == 0
    assert [tool["name"] for tool in listing["tools"]] == ["compare_lists"]
    result, code = await execute(
        "call",
        settings,
        "compare_lists",
        {"source": ["A", "B"], "baseline": ["B", "C"]},
    )
    assert code == 0
    assert result == {"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]}
    error, code = await execute(
        "call", settings, "compare_lists", {"source": [True], "baseline": []}
    )
    assert code == 1 and error["error"]["code"] == "MCP_TOOL_ERROR"
    assert len(child_processes) == 3
    assert all(child.returncode == 0 for child, env in child_processes)


async def test_agent_mcp_roundtrip(child_processes, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "parent-only-placeholder")
    monkeypatch.setenv("AGENT_LAB_TEST_SECRET", "parent-only-secret")
    model = ScriptedModel(
        [
            [
                function_call(
                    "compare_lists",
                    {"source": ["猫", "犬"], "baseline": ["犬"]},
                    call_id="mcp-1",
                )
            ],
            [assistant_message("MCP比較完了")],
        ]
    )
    result = await run_agent("比較", model, Settings(tool_mode="mcp"))
    model.assert_complete()
    assert result.final_output == "MCP比較完了"
    assert [tool.name for tool in model.calls[0].tools] == ["compare_lists"]
    outputs = [
        item
        for item in model.calls[1].input
        if item.get("type") == "function_call_output"
    ]
    assert json.loads(outputs[0]["output"]) == {
        "same": ["犬"],
        "source_only": ["猫"],
        "baseline_only": [],
    }
    assert_reaped(child_processes)
    assert child_processes[0][0].returncode == 0
    assert "OPENAI_API_KEY" not in child_processes[0][1]
    assert "AGENT_LAB_TEST_SECRET" not in child_processes[0][1]


@pytest.mark.parametrize(
    "factory", [connection.diagnostic_connection, connection.agent_connection]
)
async def test_connection_timeout_cleans_up(factory, monkeypatch, child_processes):
    params = StdioServerParameters(
        command=sys.executable, args=["-c", "import time; time.sleep(60)"]
    )
    monkeypatch.setattr(connection, "server_parameters", lambda: params)
    with anyio.fail_after(15):
        with pytest.raises(TimeoutError):
            async with factory(Settings(connect_timeout_seconds=0.2)):
                pytest.fail("Unresponsive process must not connect.")
    assert_reaped(child_processes)


async def test_call_timeout_cleans_up(monkeypatch, child_processes, tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures" / "slow_mcp_server.py"
    marker = tmp_path / "called"
    params = StdioServerParameters(
        command=sys.executable, args=[str(fixture), str(marker)]
    )
    monkeypatch.setattr(connection, "server_parameters", lambda: params)
    with anyio.fail_after(15):
        with pytest.raises(MCPError) as error:
            await execute(
                "call",
                Settings(call_timeout_seconds=2),
                "compare_lists",
                {"source": [], "baseline": []},
            )
        assert "timed out" in str(error.value).lower()
    assert marker.read_text() == "called"
    assert_reaped(child_processes)


@pytest.mark.parametrize(
    "factory", [connection.diagnostic_connection, connection.agent_connection]
)
async def test_cancellation_closes_connection(factory, child_processes):
    with anyio.fail_after(15):
        with anyio.CancelScope() as scope:
            async with factory(Settings()):
                scope.cancel()
                await anyio.sleep_forever()
        assert scope.cancelled_caught
    assert_reaped(child_processes)


async def test_overall_agent_timeout_closes_server(child_processes):
    async def slow_response(call):
        await asyncio.sleep(60)

    model = ScriptedModel([{"responder": slow_response}])
    with anyio.fail_after(15):
        with pytest.raises(TimeoutError):
            await run_agent(
                "比較", model, Settings(tool_mode="mcp", run_timeout_seconds=2)
            )
    assert_reaped(child_processes)
