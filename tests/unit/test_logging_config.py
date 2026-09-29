import asyncio
import logging
import re

import pytest

from agent_lab import logging_config as logs
from agent_lab.tools.list_tools import compare_json


def test_format_id_duration_and_no_payload(capsys):
    logs.configure_logging()
    logs.configure_logging()
    with logs.run_context() as run_id:
        compare_json('{"source":["private-payload"],"baseline":[]}')
    output = capsys.readouterr()
    assert not output.out
    assert re.search(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]", output.err)
    assert "private-payload" not in output.err
    assert f"run_id={run_id}" in output.err
    assert output.err.count("event=compare_lists_completed") == 1
    assert re.search(r"duration_ms=\d+(\.\d+)? error_kind=none", output.err)
    assert logs.current_run_id() == "-"


def test_level_and_invalid_input(capsys):
    logs.configure_logging("ERROR")
    compare_json('{"source":[],"baseline":[]}')
    assert not capsys.readouterr().err
    compare_json("{}")
    assert "error_kind=invalid_input" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error,kind",
    [
        (TimeoutError("private-value"), "timeout"),
        (ValueError("private-value"), "invalid_input"),
        (ConnectionError("private-value"), "transport_error"),
        (RuntimeError("private-value"), "execution_error"),
        (asyncio.CancelledError("private-value"), "cancelled"),
    ],
)
def test_failure_classification_and_context_reset(error, kind, capsys):
    logs.configure_logging()
    with pytest.raises(type(error)), logs.operation("probe"):
        raise error
    output = capsys.readouterr().err
    assert "event=probe_failed" in output
    assert f"error_kind={kind}" in output
    assert "private-value" not in output
    assert logs.current_run_id() == "-"


@pytest.mark.parametrize("inherited", [None, "forged\nERROR secret", "a" * 32])
def test_inherited_id_validation(inherited):
    with logs.run_context(inherited) as run_id:
        assert re.fullmatch(r"[0-9a-f]{32}", run_id)
        if inherited == "a" * 32:
            assert run_id == inherited


def test_concurrent_runs_are_isolated():
    async def worker():
        with logs.run_context() as run_id:
            await asyncio.sleep(0)
            assert logs.current_run_id() == run_id
            return run_id

    async def run():
        return await asyncio.gather(worker(), worker())

    first, second = asyncio.run(run())
    assert first != second
    assert logs.current_run_id() == "-"


def test_external_logs_are_not_emitted_by_application_handler(capsys):
    logs.configure_logging()
    logging.getLogger("external_sdk").error("private-request-body")
    assert "private-request-body" not in capsys.readouterr().err
