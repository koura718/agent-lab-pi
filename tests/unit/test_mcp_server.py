import asyncio
import json

from mcp import types

from agent_lab.mcp import server


def test_unexpected_failure_is_sanitized(monkeypatch, caplog):
    def broken(*args):
        raise RuntimeError("secret-value")

    monkeypatch.setattr(server, "compare_arguments", broken)
    result = asyncio.run(
        server.call_tool(
            None,
            types.CallToolRequestParams(
                name="compare_lists", arguments={"source": [], "baseline": []}
            ),
        )
    ).model_dump(by_alias=True)
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["error"]["code"] == "INTERNAL_ERROR"
    assert "secret-value" not in json.dumps(result) + caplog.text
