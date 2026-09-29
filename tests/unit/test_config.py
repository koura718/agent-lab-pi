import argparse

import pytest

from agent_lab.config import (
    ConfigurationError,
    Settings,
    add_settings_arguments,
    load_settings,
)


def parse(argv):
    parser = argparse.ArgumentParser()
    add_settings_arguments(parser)
    return load_settings(parser.parse_args(argv))


def test_configuration_precedence(tmp_path, monkeypatch):
    config = tmp_path / "settings.toml"
    config.write_text(
        '[agent]\ntool_mode="mcp"\nmodel="file-model"\n[mcp]\ncall_timeout_seconds=3\n'
    )
    monkeypatch.setenv("AGENT_MODEL", "env-model")
    settings = parse(["--config", str(config), "--model", "cli-model"])
    assert settings.model == "cli-model"
    assert settings.tool_mode == "mcp"
    assert settings.call_timeout_seconds == 3
    assert settings.connect_timeout_seconds == 10
    assert parse(["--config", str(config)]).model == "env-model"


@pytest.mark.parametrize(
    "content",
    [
        "[broken",
        "[agent]\nmax_turns=true",
        "[agent]\nmodel=123",
        "[mcp]\ncall_timeout_seconds=0",
        '[mcp]\ncall_timeout_seconds="10"',
        '[logging]\nlevel="DEBUG"',
        '[agent]\nsecret="not-allowed"',
        "[unknown]\nx=1",
    ],
)
def test_invalid_toml_rejected(tmp_path, content):
    config = tmp_path / "settings.toml"
    config.write_text(content)
    with pytest.raises(ConfigurationError):
        parse(["--config", str(config)])


def test_missing_explicit_file(tmp_path):
    with pytest.raises(ConfigurationError):
        parse(["--config", str(tmp_path / "missing.toml")])


@pytest.mark.parametrize("value", ["nan", "inf", "0", "-1", "3601", "secret-value"])
def test_bad_timeout_environment(monkeypatch, value):
    monkeypatch.setenv("MCP_CALL_TIMEOUT_SECONDS", value)
    with pytest.raises(ConfigurationError) as error:
        parse([])
    assert "secret-value" not in str(error.value)


def test_default_settings():
    assert parse([]) == Settings()
