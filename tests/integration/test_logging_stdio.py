import json
import os
import re
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("level", ["INFO", "WARNING"])
def test_stdio_log_correlation_and_level(level):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_lab.mcp.client",
            "--log-level",
            level,
            "call",
            "compare_lists",
            "--arguments",
            '{"source":["private-payload"],"baseline":[]}',
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        env={
            **os.environ,
            "AGENT_LAB_RUN_ID": "forged",
            "OPENAI_API_KEY": "dummy-secret",
        },
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["source_only"] == ["private-payload"]
    assert "private-payload" not in result.stderr
    assert "dummy-secret" not in result.stderr
    assert "forged" not in result.stderr
    if level == "WARNING":
        assert not result.stderr
    else:
        ids = set(re.findall(r"run_id=([0-9a-f]{32})", result.stderr))
        assert len(ids) == 1
        assert all(re.match(r"\[.*Z\] \[", line) for line in result.stderr.splitlines())
        for event in (
            "mcp_request_completed",
            "mcp_tool_completed",
            "mcp_server_completed",
        ):
            assert f"event={event}" in result.stderr
        assert "error_kind=none" in result.stderr
