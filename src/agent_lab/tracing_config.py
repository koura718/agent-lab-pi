"""Opt-in SDK tracing with metadata-only export and bounded CLI shutdown."""

import logging
import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from agents import RunConfig
from agents.tracing import get_trace_provider, set_trace_provider
from agents.tracing.processor_interface import TracingProcessor
from agents.tracing.processors import BackendSpanExporter, BatchTraceProcessor
from agents.tracing.provider import DefaultTraceProvider

from agent_lab.config import ConfigurationError
from agent_lab.logging_config import current_run_id

logger = logging.getLogger(__name__)
_RUNTIME_LOCK = threading.Lock()


@dataclass
class MetadataItem:
    """Only this immutable-by-convention snapshot reaches the export queue."""

    payload: dict
    tracing_api_key: str | None = None

    def export(self):
        return self.payload


def metadata_snapshot(item):
    raw = item.export()
    if raw is None:
        return None
    if raw["object"] == "trace":
        group_id = raw.get("group_id")
        return MetadataItem(
            {
                "object": "trace",
                "id": raw["id"],
                "workflow_name": "agent-lab",
                "group_id": group_id
                if isinstance(group_id, str) and re.fullmatch(r"[0-9a-f]{32}", group_id)
                else None,
                "metadata": {},
            }
        )
    # Custom spans keep the timeline and parent relationships without forwarding
    # response IDs, arbitrary names, model configs, input/output, or SDK errors.
    source = raw.get("span_data", {})
    kind = source.get("type", "unknown")
    if kind not in {
        "agent",
        "function",
        "response",
        "generation",
        "mcp_tools",
        "custom",
    }:
        kind = "other"
    name = (
        "compare_lists"
        if kind == "function" and source.get("name") == "compare_lists"
        else kind
    )
    return MetadataItem(
        {
            "object": "trace.span",
            "id": raw["id"],
            "trace_id": raw["trace_id"],
            "parent_id": raw.get("parent_id"),
            "started_at": raw.get("started_at"),
            "ended_at": raw.get("ended_at"),
            "span_data": {"type": "custom", "name": name, "data": {"kind": kind}},
            "error": {"message": "Operation failed", "data": {}}
            if raw.get("error")
            else None,
        }
    )


class MetadataProcessor(TracingProcessor):
    def __init__(self, downstream):
        self.downstream = downstream

    def on_trace_start(self, trace):
        snapshot = metadata_snapshot(trace)
        if snapshot is not None:
            self.downstream.on_trace_start(snapshot)

    def on_trace_end(self, trace):
        pass

    def on_span_start(self, span):
        pass

    def on_span_end(self, span):
        snapshot = metadata_snapshot(span)
        if snapshot is not None:
            self.downstream.on_span_end(snapshot)

    def force_flush(self):
        self.downstream.force_flush()

    def shutdown(self, timeout=None):
        self.downstream.shutdown(timeout=timeout)


def tracing_disabled_by_environment():
    return os.getenv("OPENAI_AGENTS_DISABLE_TRACING", "").strip().lower() in {
        "true",
        "1",
    }


class ExportWarnings(logging.Handler):
    """Forward only fixed warning text, never SDK exception or response bodies."""

    def emit(self, record):
        if record.pathname.replace("\\", "/").endswith("/agents/tracing/processors.py"):
            logger.warning(
                "Tracing exporter reported a warning; verify the trace in the dashboard.",
                extra={"event": "trace_export_warning", "error_kind": "tracing_export"},
            )


def make_processor():
    return MetadataProcessor(BatchTraceProcessor(BackendSpanExporter(max_retries=1)))


@contextmanager
def tracing_runtime(enabled):
    """Own the process-wide SDK provider for one CLI run; restore on all exits.

    Embedded applications must enter this once around their runs, not once per
    concurrent task. Tests can inject make_processor without creating an exporter.
    """
    if not enabled:
        yield
        return
    if tracing_disabled_by_environment():
        raise ConfigurationError("Tracing is blocked by OPENAI_AGENTS_DISABLE_TRACING.")
    if not _RUNTIME_LOCK.acquire(blocking=False):
        raise ConfigurationError("A tracing runtime is already active.")
    previous = None
    processor = None
    warning_handler = ExportWarnings(level=logging.WARNING)
    sdk_logger = logging.getLogger("openai.agents")
    try:
        previous = get_trace_provider()
        sdk_logger.addHandler(warning_handler)
        processor = make_processor()
        provider = DefaultTraceProvider()
        provider.set_disabled(False)
        provider.register_processor(processor)
        set_trace_provider(provider)
        yield
    finally:
        try:
            if processor is not None:
                try:
                    processor.shutdown(timeout=5)
                except Exception:  # noqa: BLE001 - telemetry must not mask the Agent result
                    logger.warning(
                        "Tracing shutdown failed",
                        extra={
                            "event": "trace_shutdown_failed",
                            "error_kind": "tracing_export",
                        },
                    )
        finally:
            sdk_logger.removeHandler(warning_handler)
            warning_handler.close()
            if previous is not None:
                set_trace_provider(previous)
            _RUNTIME_LOCK.release()


def agent_run_config(settings):
    if not settings.tracing_enabled:
        return RunConfig(tracing_disabled=True, trace_include_sensitive_data=False)
    if tracing_disabled_by_environment():
        raise ConfigurationError("Tracing is blocked by OPENAI_AGENTS_DISABLE_TRACING.")
    if not _RUNTIME_LOCK.locked():
        raise ConfigurationError("Enabled tracing requires tracing_runtime.")
    run_id = current_run_id()
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ConfigurationError("Tracing requires a generated run ID.")
    trace_id = "trace_" + run_id
    logger.info("trace_id=%s", trace_id, extra={"event": "trace_enabled"})
    return RunConfig(
        tracing_disabled=False,
        trace_include_sensitive_data=False,
        workflow_name="agent-lab",
        trace_id=trace_id,
        group_id=run_id,
    )
