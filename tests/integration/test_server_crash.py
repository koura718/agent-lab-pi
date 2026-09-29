import sys
from pathlib import Path

import anyio
import pytest
from mcp import StdioServerParameters
from mcp.shared.exceptions import MCPError

from agent_lab.config import Settings
from agent_lab.mcp import connection

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_server_crash_during_call(monkeypatch, child_processes):
    fixture = Path(__file__).parents[1] / "fixtures" / "crashing_mcp_server.py"
    params = StdioServerParameters(command=sys.executable, args=[str(fixture)])
    monkeypatch.setattr(connection, "server_parameters", lambda: params)
    with anyio.fail_after(15):
        async with connection.diagnostic_connection(Settings()) as client:
            with pytest.raises(
                (MCPError, anyio.EndOfStream, anyio.ClosedResourceError)
            ):
                await client.call_tool("compare_lists", {"source": [], "baseline": []})
    assert len(child_processes) == 1
    assert child_processes[0][0].returncode == 23
