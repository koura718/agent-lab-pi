"""Same contract through both real tool adapters; no external API."""

import json

import anyio
import pytest
from agents.testing import ScriptedModel, assistant_message, function_call

from agent_lab.config import Settings
from agent_lab.main import run_agent
from agent_lab.mcp.connection import diagnostic_connection
from agent_lab.tools.list_tools import compare_json

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_adapter_equivalence(child_processes):
    cases = [
        {"source": ["A", "B", "B"], "baseline": ["B", "C"]},
        {"source": [], "baseline": []},
        {"source": ["猫", "犬", "猫", "é", "é"], "baseline": ["犬", "é"]},
        {"source": ["A", "a", " A"], "baseline": ["A"]},
        {"source": [str(i) for i in range(1000)], "baseline": ["x" * 256]},
        {"source": [True], "baseline": []},
        {"source": [""], "baseline": []},
        {"source": ["x" * 257], "baseline": []},
        {"source": ["x"] * 1001, "baseline": []},
        {"source": []},
        {"source": [], "baseline": [], "unknown": True},
    ]
    with anyio.fail_after(30):
        async with diagnostic_connection(Settings()) as client:
            for payload in cases:
                function = json.loads(compare_json(json.dumps(payload)))
                mcp = await client.call_tool("compare_lists", payload)
                if "error" in function:
                    assert mcp.is_error
                    assert mcp.structured_content is None
                else:
                    assert not mcp.is_error
                    assert mcp.structured_content == function
    assert len(child_processes) == 1
    assert child_processes[0][0].returncode == 0


@pytest.mark.parametrize("mode", ["function", "mcp"])
async def test_runner_equivalence(mode):
    payload = {"source": ["猫", "犬", "猫"], "baseline": ["犬", "鳥"]}
    model = ScriptedModel(
        [
            [function_call("compare_lists", payload, call_id="equivalence")],
            [assistant_message("done")],
        ]
    )
    result = await run_agent("Compare", model, Settings(tool_mode=mode))
    model.assert_complete()
    outputs = [
        item
        for item in model.calls[1].input
        if item.get("type") == "function_call_output"
    ]
    assert len(outputs) == 1
    assert json.loads(outputs[0]["output"]) == json.loads(
        compare_json(json.dumps(payload))
    )
    # Verify the same result-item interface used by the opt-in live assertions.
    calls = [item for item in result.new_items if item.type == "tool_call_item"]
    assert any(
        getattr(item.raw_item, "name", None) == "compare_lists" for item in calls
    )
    tool_outputs = [
        item.output for item in result.new_items if item.type == "tool_call_output_item"
    ]
    assert len(tool_outputs) == 1
    assert json.loads(tool_outputs[0]) == json.loads(compare_json(json.dumps(payload)))
    assert result.final_output == "done"
