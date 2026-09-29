"""Actual SDK spans with an in-memory sink; no exporter/network/model API."""

import asyncio
import json

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.tracing import get_trace_provider

from agent_lab import tracing_config as tracing
from agent_lab.config import Settings
from agent_lab.logging_config import run_context
from agent_lab.main import run_agent

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


class Sink:
    def __init__(self):
        self.items = []
        self.timeout = None

    def on_trace_start(self, item):
        self.items.append(item.export())

    def on_span_end(self, item):
        self.items.append(item.export())

    def shutdown(self, timeout=None):
        self.timeout = timeout

    def force_flush(self):
        pass


@pytest.fixture
def sink(monkeypatch):
    target = Sink()
    monkeypatch.setenv("OPENAI_AGENTS_DISABLE_TRACING", "0")
    monkeypatch.setattr(
        tracing, "make_processor", lambda: tracing.MetadataProcessor(target)
    )
    return target


@pytest.mark.parametrize("mode", ["function", "mcp"])
async def test_metadata_tracing_roundtrip(mode, sink):
    previous = get_trace_provider()
    model = ScriptedModel(
        [
            [
                function_call(
                    "compare_lists",
                    {"source": ["private-input"], "baseline": []},
                    call_id="test",
                )
            ],
            [assistant_message("private-output")],
        ]
    )
    with run_context() as run_id, tracing.tracing_runtime(True):
        result = await run_agent(
            "private-prompt", model, Settings(tool_mode=mode, tracing_enabled=True)
        )
    assert result.final_output == "private-output"
    assert get_trace_provider() is previous
    assert sink.timeout == 5
    traces = [item for item in sink.items if item["object"] == "trace"]
    spans = [item for item in sink.items if item["object"] == "trace.span"]
    assert len(traces) == 1
    assert traces[0]["id"] == "trace_" + run_id
    assert traces[0]["group_id"] == run_id
    assert any(item["span_data"]["name"] == "compare_lists" for item in spans)
    assert all(item["trace_id"] == traces[0]["id"] for item in spans)
    assert all(item["started_at"] and item["ended_at"] for item in spans)
    serialized = json.dumps(sink.items)
    for private in ("private-input", "private-output", "private-prompt"):
        assert private not in serialized


async def test_disabled_run_inside_runtime_has_no_spans(sink):
    with tracing.tracing_runtime(True):
        await run_agent(
            "private-prompt", ScriptedModel([[assistant_message("ok")]]), Settings()
        )
    assert sink.items == []


@pytest.mark.parametrize("cancel", [False, True])
async def test_error_or_timeout_restores_provider(cancel, sink):
    previous = get_trace_provider()

    async def responder(call):
        if cancel:
            await asyncio.sleep(60)
        raise RuntimeError("private-error")

    expected = TimeoutError if cancel else RuntimeError
    with pytest.raises(expected), tracing.tracing_runtime(True):
        await run_agent(
            "private-prompt",
            ScriptedModel([{"responder": responder}]),
            Settings(tracing_enabled=True, run_timeout_seconds=0.1),
        )
    assert get_trace_provider() is previous
    assert sink.timeout == 5
    assert "private-error" not in json.dumps(sink.items)
    assert sink.items


async def test_runtime_rejects_nested_ownership(sink):
    from agent_lab.config import ConfigurationError

    with tracing.tracing_runtime(True):
        with (
            pytest.raises(ConfigurationError, match="already active"),
            tracing.tracing_runtime(True),
        ):
            pytest.fail("Must not replace an active provider")
        await run_agent(
            "hello",
            ScriptedModel([[assistant_message("ok")]]),
            Settings(tracing_enabled=True),
        )
    assert sink.items
