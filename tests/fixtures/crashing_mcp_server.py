"""Exit abnormally only after a real tools/call request arrives."""

import os

from agent_lab.mcp import server


async def crash(context, params):
    os._exit(23)


if __name__ == "__main__":
    server.call_tool = crash
    raise SystemExit(server.cli())
