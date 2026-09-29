"""Application-only stderr logging and task-local execution correlation."""

import asyncio
import inspect
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4

_RUN_ID = ContextVar("agent_lab_run_id", default="-")
_LEVELS = {"INFO", "WARNING", "ERROR"}
logger = logging.getLogger(__name__)


def current_run_id():
    return _RUN_ID.get()


def error_kind(error):
    if isinstance(error, BaseExceptionGroup):
        kinds = {error_kind(item) for item in error.exceptions}
        return kinds.pop() if len(kinds) == 1 else "execution_error"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt)):
        return "cancelled"
    if isinstance(error, ValueError):
        return "invalid_input"
    if isinstance(error, (ConnectionError, OSError)):
        return "transport_error"
    # Avoid importing model SDKs into the API-free diagnostic client.
    if type(error).__name__ in {"MCPError", "EndOfStream", "ClosedResourceError"}:
        return "mcp_error"
    return "execution_error"


class ApplicationFilter(logging.Filter):
    def filter(self, record):
        if not record.name.startswith("agent_lab.") and record.name != "agent_lab":
            return False
        record.run_id = current_run_id()
        for name, default in (
            ("event", "message"),
            ("duration_ms", "-"),
            ("error_kind", "none"),
        ):
            if not hasattr(record, name):
                setattr(record, name, default)
        return True


def configure_logging(level="INFO"):
    """Replace only our own handler; leave embedding applications' handlers alone."""
    if level not in _LEVELS:
        raise ValueError("Unsupported log level.")
    root = logging.getLogger()
    for old in root.handlers[:]:
        if getattr(old, "_agent_lab_handler", False):
            root.removeHandler(old)
            old.close()
    handler = logging.StreamHandler(sys.stderr)
    handler._agent_lab_handler = True
    handler.addFilter(ApplicationFilter())
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] run_id=%(run_id)s event=%(event)s "
        "duration_ms=%(duration_ms)s error_kind=%(error_kind)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    root.addHandler(handler)
    logging.getLogger("agent_lab").setLevel(level)


@contextmanager
def run_context(inherited=None):
    # Only a generated lowercase UUID hex is allowed across the process boundary.
    run_id = (
        inherited
        if isinstance(inherited, str) and re.fullmatch(r"[0-9a-f]{32}", inherited)
        else uuid4().hex
    )
    token = _RUN_ID.set(run_id)
    try:
        yield run_id
    finally:
        _RUN_ID.reset(token)


def cli_context(*, server=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            inherited = os.getenv("AGENT_LAB_RUN_ID") if server else None
            level = (
                os.getenv("AGENT_LAB_SERVER_LOG_LEVEL", "INFO") if server else "INFO"
            )
            configure_logging(level if level in _LEVELS else "INFO")
            with run_context(inherited):
                return function(*args, **kwargs)

        return wrapped

    return decorate


@contextmanager
def operation(name):
    """Emit paired events without arguments, outputs, or exception messages."""
    token = _RUN_ID.set(uuid4().hex) if current_run_id() == "-" else None
    started = time.perf_counter()
    state = {"error_kind": "none"}
    logger.info("started", extra={"event": name + "_started"})
    try:
        yield state
    except BaseException as error:
        state["error_kind"] = error_kind(error)
        raise
    finally:
        failed = state["error_kind"] != "none"
        logger.log(
            logging.ERROR if failed else logging.INFO,
            "failed" if failed else "completed",
            extra={
                "event": name + ("_failed" if failed else "_completed"),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "error_kind": state["error_kind"],
            },
        )
        if token is not None:
            _RUN_ID.reset(token)


def timed(name, result_error=None):
    def decorate(function):
        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def asynchronous(*args, **kwargs):
                with operation(name) as state:
                    result = await function(*args, **kwargs)
                    if result_error:
                        state["error_kind"] = result_error(result)
                    return result

            return asynchronous

        @wraps(function)
        def synchronous(*args, **kwargs):
            with operation(name) as state:
                result = function(*args, **kwargs)
                if result_error:
                    state["error_kind"] = result_error(result)
                return result

        return synchronous

    return decorate
