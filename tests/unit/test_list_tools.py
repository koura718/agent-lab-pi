import asyncio
import json
import logging

import pytest
from agents import RunConfig, Runner
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.tool_context import ToolContext

from agent_lab.agent_factory import create_agent
from agent_lab.tools import list_tools


def invoke(arguments):
    tool = list_tools.create_compare_lists_tool()
    context = ToolContext(
        context=None,
        tool_name=tool.name,
        tool_call_id="test-call",
        tool_arguments=arguments,
    )
    return json.loads(asyncio.run(tool.on_invoke_tool(context, arguments)))


def test_tool_success():
    assert invoke('{"source":["A","B","B"],"baseline":["B","C"]}') == {
        "same": ["B"],
        "source_only": ["A"],
        "baseline_only": ["C"],
    }


@pytest.mark.parametrize(
    "arguments",
    [
        "not-json",
        "null",
        "[]",
        "{}",
        '{"source":[]}',
        '{"source":[],"baseline":[],"extra":"secret-value"}',
        '{"source":[],"source":["A"],"baseline":[]}',
        '{"source":[NaN],"baseline":[]}',
        '{"source":[1],"baseline":[]}',
        '{"source":[true],"baseline":[]}',
        '{"source":[null],"baseline":[]}',
        '{"source":[""],"baseline":[]}',
        '{"source":[],"baseline":"A"}',
        json.dumps({"source": ["A"] * 1001, "baseline": []}),
        json.dumps({"source": [], "baseline": ["x" * 257]}),
    ],
)
def test_tool_rejects_bad_arguments(arguments, caplog):
    output = invoke(arguments)
    assert set(output) == {"error"}
    assert output["error"]["code"] == "INVALID_INPUT"
    assert "secret-value" not in json.dumps(output) + caplog.text


def test_schema_and_fresh_registration():
    first, second = create_agent(), create_agent()
    assert [tool.name for tool in first.tools] == ["compare_lists"]
    assert first.tools[0] is not second.tools[0]
    schema = first.tools[0].params_json_schema
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"source", "baseline"}
    for field in schema["required"]:
        assert schema["properties"][field] == {
            "type": "array",
            "maxItems": 1000,
            "items": {"type": "string", "minLength": 1, "maxLength": 256},
        }


def test_logs_do_not_echo_values(caplog):
    caplog.set_level(logging.INFO)
    invoke('{"source":["secret-value"],"baseline":[]}')
    assert "completed" in caplog.text
    assert "secret-value" not in caplog.text


def test_unexpected_domain_error_fails_run(monkeypatch):
    def broken(*args):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(list_tools, "compare_arguments", broken)
    with pytest.raises(RuntimeError):
        invoke('{"source":[],"baseline":[]}')


@pytest.mark.parametrize("invalid", [False, True])
def test_runner_calls_tool_and_passes_result_to_model(invalid):
    arguments = {"source": ["A", "B", "B"], "baseline": ["B", "C"]}
    if invalid:
        arguments["source"] = [1]
    model = ScriptedModel(
        [
            [function_call("compare_lists", arguments, call_id="compare-1")],
            [assistant_message("比較エラー" if invalid else "比較完了")],
        ]
    )
    result = asyncio.run(
        Runner.run(
            create_agent(model=model),
            "リストを比較してください。",
            max_turns=3,
            run_config=RunConfig(tracing_disabled=True),
        )
    )
    model.assert_complete()
    assert len(model.calls) == 2
    outputs = [
        item
        for item in model.calls[1].input
        if item.get("type") == "function_call_output"
    ]
    assert len(outputs) == 1
    assert outputs[0]["call_id"] == "compare-1"
    payload = json.loads(outputs[0]["output"])
    if invalid:
        assert payload["error"]["code"] == "INVALID_INPUT"
    else:
        assert payload == {"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]}
    assert result.final_output == ("比較エラー" if invalid else "比較完了")
