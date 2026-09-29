"""Real Runner and HTTP adapter, mocked model API, real MCP subprocess."""

import asyncio
import json

import httpx2 as httpx
import pytest
from openai import AsyncOpenAI

from agent_lab import model_provider
from agent_lab.config import Settings
from agent_lab.main import run_agent

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("provider", ["anthropic", "cerebras"])
@pytest.mark.parametrize("mode", ["function", "mcp"])
def test_compatibility_tool_roundtrip(monkeypatch, mode, provider):
    key_name = model_provider.PROVIDER_KEYS[provider]
    model_name = "qwen-3.8-27b" if provider == "cerebras" else "claude-test-model"
    monkeypatch.setenv(key_name, "provider-test-key")
    monkeypatch.setenv("OPENAI_ORG_ID", "must-not-send-org")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "must-not-send-project")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-send-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://must-not-use.invalid/")
    requests = []
    clients = []

    def handle(request):
        assert (
            str(request.url)
            == model_provider.COMPATIBILITY_URLS[provider] + "chat/completions"
        )
        assert request.headers["authorization"] == "Bearer provider-test-key"
        payload = json.loads(request.content)
        assert payload["model"] == model_name
        assert not request.headers.get("openai-organization")
        assert not request.headers.get("openai-project")
        assert "response_format" not in payload
        if provider == "cerebras":
            assert payload["reasoning_effort"] == "none"
            assert all(
                not tool["function"].get("strict", False) for tool in payload["tools"]
            )
            assert "minLength" in json.dumps(payload["tools"])
        assert any(
            tool["function"]["name"] == "compare_lists" for tool in payload["tools"]
        )
        requests.append(payload)
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_test123",
                        "type": "function",
                        "function": {
                            "name": "compare_lists",
                            "arguments": '{"source":["A","B","B"],"baseline":["B","C"]}',
                        },
                    }
                ],
            }
            reason = "tool_calls"
        else:
            tool_message = next(m for m in payload["messages"] if m["role"] == "tool")
            assert tool_message["tool_call_id"] == "toolu_test123"
            assert json.loads(tool_message["content"]) == {
                "same": ["B"],
                "source_only": ["A"],
                "baseline_only": ["C"],
            }
            message = {"role": "assistant", "content": "Comparison complete."}
            reason = "stop"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "created": 1,
                "model": model_name,
                "choices": [{"index": 0, "message": message, "finish_reason": reason}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    def create_client(**kwargs):
        client = AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(model_provider, "AsyncOpenAI", create_client)
    result = asyncio.run(
        run_agent(
            "Compare the lists.",
            model_name,
            Settings(provider=provider, tool_mode=mode),
        )
    )
    assert result.final_output == "Comparison complete."
    assert len(requests) == 2
    assert clients[0].is_closed()


@pytest.mark.parametrize("provider", ["anthropic", "cerebras"])
@pytest.mark.parametrize(
    "error", [RuntimeError("private-marker"), asyncio.CancelledError()]
)
def test_compatibility_client_closed_on_error(monkeypatch, error, provider):
    monkeypatch.setenv(model_provider.PROVIDER_KEYS[provider], "dummy")
    clients = []

    def create_client(**kwargs):
        client = AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: httpx.Response(500))
            ),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(model_provider, "AsyncOpenAI", create_client)

    async def execute():
        async with model_provider.configured_model(
            Settings(provider=provider), "test-model"
        ):
            raise error

    with pytest.raises(type(error)):
        asyncio.run(execute())
    assert clients[0].is_closed()
