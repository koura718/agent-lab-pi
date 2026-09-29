import json

import pytest

from agent_lab.config import ConfigurationError
from agent_lab.mcp import client


@pytest.mark.parametrize("raw", ["[]", "null", "{", '{"x":1,"x":2}', '{"x":NaN}'])
def test_bad_arguments(raw):
    with pytest.raises(ConfigurationError):
        client.parse_arguments(raw)


def test_diagnostic_cli_json_stdout(monkeypatch, capsys):
    async def execute(command, settings, tool, arguments):
        assert command == "call"
        assert tool == "compare_lists"
        assert arguments == {"source": [], "baseline": []}
        return {"same": [], "source_only": [], "baseline_only": []}, 0

    monkeypatch.setattr(client, "execute", execute)
    assert (
        client.cli(
            ["call", "compare_lists", "--arguments", '{"source":[],"baseline":[]}']
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["same"] == []


@pytest.mark.parametrize(
    "error,code", [(TimeoutError("secret-value"), 1), (KeyboardInterrupt(), 130)]
)
def test_cli_sanitizes_failure(monkeypatch, caplog, capsys, error, code):
    async def fail(*args):
        raise error

    monkeypatch.setattr(client, "execute", fail)
    assert client.cli(["list-tools"]) == code
    assert "secret-value" not in caplog.text
    assert capsys.readouterr().out == ""
