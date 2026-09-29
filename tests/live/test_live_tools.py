"""Opt-in real model tests: assert actual tool output, not generated wording."""

import asyncio
import json
import os

import pytest

from agent_lab.config import Settings
from agent_lab.main import run_agent

pytestmark = pytest.mark.live


@pytest.mark.parametrize("mode", ["function", "mcp"])
def test_live_compare_lists(mode):
    result = asyncio.run(
        run_agent(
            'Call compare_lists exactly once with source=["A","B","B"] '
            'and baseline=["B","C"], then briefly report the result.',
            os.environ["AGENT_MODEL"],
            Settings(
                provider=os.getenv("AGENT_PROVIDER", "openai"),
                tool_mode=mode,
                max_turns=3,
                run_timeout_seconds=60,
            ),
        )
    )
    calls = [item for item in result.new_items if item.type == "tool_call_item"]
    assert any(
        getattr(item.raw_item, "name", None) == "compare_lists" for item in calls
    )
    outputs = [
        item.output for item in result.new_items if item.type == "tool_call_output_item"
    ]
    expected = {"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]}
    assert any(
        json.loads(output) == expected for output in outputs if isinstance(output, str)
    )
    assert result.final_output
