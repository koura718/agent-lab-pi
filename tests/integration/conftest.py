import anyio
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def child_processes(monkeypatch):
    children = []
    real_open = anyio.open_process

    async def tracked_open(*args, **kwargs):
        child = await real_open(*args, **kwargs)
        children.append((child, kwargs.get("env", {})))
        return child

    monkeypatch.setattr(anyio, "open_process", tracked_open)
    return children
