import json

import pytest

from agent_lab import main as app


def test_offline_cli_does_not_create_agent(monkeypatch, capsys):
    def forbidden(**kwargs):
        raise AssertionError("Offline comparison must not create an Agent.")

    monkeypatch.setattr(app, "create_agent", forbidden)
    assert app.cli(["--compare-json", '{"source":["猫"],"baseline":[]}']) == 0
    assert json.loads(capsys.readouterr().out) == {
        "same": [],
        "source_only": ["猫"],
        "baseline_only": [],
    }


def test_invalid_offline_input(capsys):
    assert app.cli(["--compare-json", "{}"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_INPUT"


def test_model_run_requires_key(caplog):
    assert app.cli([]) == 2
    assert "OPENAI_API_KEY is required" in caplog.text


def test_default_prompt_and_model_precedence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("AGENT_MODEL", "env-model")
    calls = []

    async def fake_main(prompt, model, settings):
        calls.append((prompt, model))

    monkeypatch.setattr(app, "main", fake_main)
    assert app.cli([]) == 0
    assert app.cli(["--prompt", "比較", "--model", "cli-model"]) == 0
    assert calls == [(app.DEFAULT_PROMPT, "env-model"), ("比較", "cli-model")]


@pytest.mark.parametrize(
    "error,code", [(TimeoutError("secret-value"), 1), (KeyboardInterrupt(), 130)]
)
def test_run_errors_are_sanitized(monkeypatch, caplog, error, code):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")

    async def failed(*args):
        raise error

    monkeypatch.setattr(app, "main", failed)
    assert app.cli([]) == code
    assert "secret-value" not in caplog.text


def test_mcp_mode_rejects_local_compare():
    with pytest.raises(SystemExit) as error:
        app.cli(["--tool-mode", "mcp", "--compare-json", "{}"])
    assert error.value.code == 2
