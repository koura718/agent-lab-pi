import argparse
import json

import pytest
from agents.tracing import get_trace_provider

from agent_lab import tracing_config as tracing
from agent_lab.config import (
    ConfigurationError,
    Settings,
    add_settings_arguments,
    load_settings,
)


def parse(args):
    parser = argparse.ArgumentParser()
    add_settings_arguments(parser)
    return load_settings(parser.parse_args(args))


def test_tracing_precedence(tmp_path, monkeypatch):
    path = tmp_path / "tracing.toml"
    path.write_text("[tracing]\nenabled = true\n")
    assert not parse([]).tracing_enabled
    assert parse(["--config", str(path)]).tracing_enabled
    monkeypatch.setenv("AGENT_TRACING_ENABLED", "false")
    assert not parse(["--config", str(path)]).tracing_enabled
    assert parse(["--tracing"]).tracing_enabled
    monkeypatch.setenv("AGENT_TRACING_ENABLED", "true")
    assert not parse(["--no-tracing"]).tracing_enabled


@pytest.mark.parametrize("value", ["yes", "secret-value", "", "2"])
def test_invalid_bool_environment(monkeypatch, value):
    monkeypatch.setenv("AGENT_TRACING_ENABLED", value)
    with pytest.raises(ConfigurationError) as error:
        parse([])
    assert "secret-value" not in str(error.value)


@pytest.mark.parametrize("value", ["true", 1, None])
def test_invalid_bool_setting(value):
    with pytest.raises(ConfigurationError):
        Settings(tracing_enabled=value)


def test_disabled_runtime_never_builds_exporter(monkeypatch):
    def forbidden():
        pytest.fail("Disabled tracing must not construct an exporter")

    monkeypatch.setattr(tracing, "make_processor", forbidden)
    previous = get_trace_provider()
    with tracing.tracing_runtime(False):
        assert tracing.agent_run_config(Settings()).tracing_disabled
    assert get_trace_provider() is previous


def test_environment_kill_switch(monkeypatch):
    monkeypatch.setenv("OPENAI_AGENTS_DISABLE_TRACING", "1")
    with (
        pytest.raises(ConfigurationError, match="blocked"),
        tracing.tracing_runtime(True),
    ):
        pytest.fail("Must not start tracing")


def test_requires_runtime(monkeypatch):
    monkeypatch.setenv("OPENAI_AGENTS_DISABLE_TRACING", "0")
    with pytest.raises(ConfigurationError, match="requires tracing_runtime"):
        tracing.agent_run_config(Settings(tracing_enabled=True))


def test_snapshot_strips_all_unapproved_data():
    class Unsafe:
        def export(self):
            return {
                "object": "trace.span",
                "id": "span_id",
                "trace_id": "trace_id",
                "parent_id": None,
                "started_at": "start",
                "ended_at": "end",
                "span_data": {
                    "type": "response",
                    "response_id": "private-response-id",
                    "input": "private-prompt",
                    "output": "private-output",
                    "model_config": {"key": "private-key"},
                },
                "error": {"message": "private-error", "data": {"key": "private-key"}},
                "extra": "private-extra",
            }

    payload = tracing.metadata_snapshot(Unsafe()).export()
    assert "private-" not in json.dumps(payload)
    assert payload["error"] == {"message": "Operation failed", "data": {}}
    assert payload["span_data"] == {
        "type": "custom",
        "name": "response",
        "data": {"kind": "response"},
    }


def test_backend_serialization_uses_only_metadata(monkeypatch):
    import httpx2
    from agents.tracing.processors import BackendSpanExporter

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200)

    real_client = httpx2.Client
    with real_client(
        transport=httpx2.MockTransport(respond), trust_env=False
    ) as client:
        monkeypatch.setattr(httpx2, "Client", lambda **kwargs: client)
        exporter = BackendSpanExporter(api_key="dummy-key", max_retries=1)
        exporter.export(
            [
                tracing.MetadataItem(
                    {
                        "object": "trace",
                        "id": "trace_" + "a" * 32,
                        "workflow_name": "agent-lab",
                        "group_id": "a" * 32,
                        "metadata": {},
                    }
                )
            ]
        )
    assert len(requests) == 1
    assert requests[0]["data"][0]["workflow_name"] == "agent-lab"
    assert "dummy-key" not in json.dumps(requests)


def test_export_warning_does_not_echo_sdk_message(caplog):
    import logging

    record = logging.LogRecord(
        "openai.agents",
        logging.ERROR,
        "/sdk/agents/tracing/processors.py",
        1,
        "private-response-body",
        (),
        None,
    )
    tracing.ExportWarnings().emit(record)
    assert "private-response-body" not in caplog.text
    assert "verify the trace" in caplog.text


def test_runtime_setup_failure_releases_lock(monkeypatch):
    monkeypatch.setenv("OPENAI_AGENTS_DISABLE_TRACING", "0")
    previous = get_trace_provider()

    def broken():
        raise RuntimeError("private-startup-error")

    monkeypatch.setattr(tracing, "make_processor", broken)
    with pytest.raises(RuntimeError), tracing.tracing_runtime(True):
        pass
    assert get_trace_provider() is previous
    assert not tracing._RUNTIME_LOCK.locked()


@pytest.mark.parametrize("client", [False, True])
def test_offline_cli_rejects_tracing(client, monkeypatch):
    from agent_lab.main import cli as agent_cli
    from agent_lab.mcp.client import cli as diagnostic_cli

    def forbidden():
        pytest.fail("Offline CLI must not construct a tracing exporter")

    monkeypatch.setattr(tracing, "make_processor", forbidden)
    with pytest.raises(SystemExit) as error:
        if client:
            diagnostic_cli(["--tracing", "list-tools"])
        else:
            agent_cli(["--tracing", "--compare-json", "{}"])
    assert error.value.code == 2
