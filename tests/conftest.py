"""Default tests are offline, with credentials and tracing disabled."""

import os
import socket
from pathlib import Path

import pytest
from agents.tracing import set_trace_provider
from agents.tracing.provider import DefaultTraceProvider

from agent_lab.config import ENVIRONMENT
from agent_lab.model_provider import PROVIDER_KEYS

pytest_plugins = ["pytester"]


def pytest_addoption(parser):
    parser.addoption(
        "--run-live", action="store_true", help="Allow paid real-model tests."
    )


def pytest_configure(config):
    if config.getoption("--run-live"):
        provider = os.getenv("AGENT_PROVIDER", "openai")
        if provider not in PROVIDER_KEYS:
            raise pytest.UsageError(
                "AGENT_PROVIDER must be openai, anthropic or cerebras"
            )
        key_name = PROVIDER_KEYS[provider]
        missing = [
            name
            for name in (key_name, "AGENT_MODEL")
            if not os.getenv(name, "").strip()
        ]
        if missing:
            raise pytest.UsageError("--run-live requires: " + ", ".join(missing))


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Directory classification prevents an omitted marker enabling live calls.
        if "live" in Path(item.path).relative_to(config.rootpath).parts:
            item.add_marker(pytest.mark.live)
        if item.get_closest_marker("live") and not config.getoption("--run-live"):
            item.add_marker(
                pytest.mark.skip(reason="requires --run-live (API charges)")
            )


@pytest.fixture(scope="session", autouse=True)
def tracing_without_exporters():
    # No default HTTP exporter: offline tests also work behind SOCKS proxies.
    provider = DefaultTraceProvider()
    provider.set_disabled(True)
    set_trace_provider(provider)
    yield
    provider.shutdown()


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, request):
    if request.node.get_closest_marker("live") and request.config.getoption(
        "--run-live"
    ):
        return
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    for name in ENVIRONMENT.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_AGENTS_DISABLE_TRACING", "1")

    def deny_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests.")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)


@pytest.fixture(autouse=True)
def restore_application_logging():
    # CLI tests install a real stderr handler; don't keep a captured/closed stream.
    import logging

    package = logging.getLogger("agent_lab")
    level = package.level
    yield
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, "_agent_lab_handler", False):
            root.removeHandler(handler)
            handler.close()
    package.setLevel(level)
