"""Two independent real Runner/Tool executions with deterministic local models."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call

from agent_lab import main as agent_main
from agent_lab.config import Settings
from agent_lab.model_comparison import compare_models

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("include_cerebras", [False, True])
@pytest.mark.parametrize("mode", ["function", "mcp"])
def test_parallel_runner_paths(monkeypatch, mode, child_processes, include_cerebras):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic")
    monkeypatch.setenv("CEREBRAS_API_KEY", "dummy-cerebras")
    models = {"openai": "gpt-test", "anthropic": "claude-test"}
    if include_cerebras:
        models["cerebras"] = "qwen-3.8-27b"
    arguments = {"source": ["A", "B", "B"], "baseline": ["B", "C"]}
    seen = {}

    @asynccontextmanager
    async def scripted(settings, model):
        instance = ScriptedModel(
            [
                [function_call("compare_lists", arguments, call_id=settings.provider)],
                [assistant_message(settings.provider + " finished")],
            ]
        )
        seen[settings.provider] = instance
        yield instance
        instance.assert_complete()

    monkeypatch.setattr(agent_main, "configured_model", scripted)
    report = asyncio.run(
        compare_models(
            arguments,
            models,
            Settings(tool_mode=mode),
        )
    )
    assert report["status"] == "success"
    assert report["results_match"] is True
    assert set(seen) == set(models)
    assert report["runs"][0]["final_output"] == "openai finished"
    assert report["runs"][1]["final_output"] == "anthropic finished"
    assert len(child_processes) == (len(models) if mode == "mcp" else 0)
    assert all(process.returncode == 0 for process, _ in child_processes)
