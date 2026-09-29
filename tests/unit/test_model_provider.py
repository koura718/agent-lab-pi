import argparse
import asyncio

import pytest

from agent_lab.config import (
    ConfigurationError,
    Settings,
    add_settings_arguments,
    load_settings,
)
from agent_lab.main import cli, main
from agent_lab.model_provider import configured_model, validate_model_access


def test_provider_precedence(tmp_path, monkeypatch):
    config = tmp_path / "settings.toml"
    config.write_text('[agent]\nprovider = "anthropic"\n')
    parser = argparse.ArgumentParser()
    add_settings_arguments(parser)
    assert (
        load_settings(parser.parse_args(["--config", str(config)])).provider
        == "anthropic"
    )
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    assert (
        load_settings(parser.parse_args(["--config", str(config)])).provider == "openai"
    )
    assert (
        load_settings(parser.parse_args(["--provider", "anthropic"])).provider
        == "anthropic"
    )


def test_unknown_provider():
    with pytest.raises(ConfigurationError):
        Settings(provider="unknown")


def test_claude_requires_own_key(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-private-marker")
    assert cli(["--provider", "anthropic", "--model", "claude-example"]) == 2
    captured = capsys.readouterr()
    assert "ANTHROPIC_API_KEY is required" in captured.err
    assert "openai-private-marker" not in captured.err


def test_claude_requires_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")
    with pytest.raises(ConfigurationError, match="explicit"):
        validate_model_access(Settings(provider="anthropic"), None)


def test_claude_cli_uses_anthropic_key(monkeypatch):
    from agent_lab import main as app

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")
    observed = []

    async def fake_main(prompt, model, settings):
        observed.append((settings.provider, model))

    monkeypatch.setattr(app, "main", fake_main)
    assert cli(["--provider", "anthropic", "--model", "claude-example"]) == 0
    assert observed == [("anthropic", "claude-example")]


def test_claude_tracing_rejected_before_exporter(monkeypatch):
    from agent_lab import main as app

    def forbidden(*args):
        raise AssertionError("Must not start OpenAI tracing")

    monkeypatch.setattr(app, "tracing_runtime", forbidden)
    with pytest.raises(ConfigurationError, match="no-tracing"):
        asyncio.run(
            main(
                model="claude-example",
                settings=Settings(provider="anthropic", tracing_enabled=True),
            )
        )


def test_offline_comparison_needs_no_provider_credentials(capsys):
    assert (
        cli(
            ["--provider", "anthropic", "--compare-json", '{"source":[],"baseline":[]}']
        )
        == 0
    )
    assert '"same": []' in capsys.readouterr().out


def test_openai_model_passthrough():
    async def check():
        async with configured_model(Settings(), "test-model") as model:
            assert model == "test-model"

    asyncio.run(check())


@pytest.mark.parametrize("problem", ["key", "model", "tracing"])
def test_cerebras_access_validation(monkeypatch, problem):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unrelated-anthropic-secret")
    if problem != "key":
        monkeypatch.setenv("CEREBRAS_API_KEY", "dummy")
    with pytest.raises(
        ConfigurationError,
        match={"key": "CEREBRAS_API_KEY", "model": "explicit", "tracing": "no-tracing"}[
            problem
        ],
    ):
        validate_model_access(
            Settings(provider="cerebras", tracing_enabled=problem == "tracing"),
            None if problem == "model" else "qwen-3.8-27b",
        )


def test_cerebras_cli_and_config(monkeypatch, tmp_path):
    from agent_lab import main as app

    config = tmp_path / "cerebras.toml"
    config.write_text('[agent]\nprovider="cerebras"\nmodel="qwen-3.8-27b"\n')
    monkeypatch.setenv("CEREBRAS_API_KEY", "dummy")
    observed = []

    async def fake_main(prompt, model, settings):
        observed.append((settings.provider, model))

    monkeypatch.setattr(app, "main", fake_main)
    assert cli(["--config", str(config)]) == 0
    assert observed == [("cerebras", "qwen-3.8-27b")]
    monkeypatch.setenv("AGENT_PROVIDER", "cerebras")
    monkeypatch.setenv("AGENT_MODEL", "qwen-3.8-27b")
    assert cli([]) == 0
    assert cli(["--provider", "cerebras", "--model", "gpt-oss-120b"]) == 0
    assert observed[-1] == ("cerebras", "gpt-oss-120b")
