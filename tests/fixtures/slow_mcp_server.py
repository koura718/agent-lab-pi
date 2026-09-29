"""Test-only server that accepts connections but does not finish tool calls."""

import asyncio
import sys
from pathlib import Path

from agent_lab.mcp import server


async def delayed_call(context, params):
    Path(sys.argv[1]).write_text("called")
    await asyncio.sleep(60)
    raise AssertionError("The client should have timed out and stopped this process.")


if __name__ == "__main__":
    server.call_tool = delayed_call
    raise SystemExit(server.cli())
