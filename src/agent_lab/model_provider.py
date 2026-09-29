"""Explicit provider selection for model evaluation; no global SDK changes."""

import os
from contextlib import asynccontextmanager

from agents import Model, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from agent_lab.config import ConfigurationError, Settings

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1/"
PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
}
COMPATIBILITY_URLS = {
    "anthropic": ANTHROPIC_BASE_URL,
    "cerebras": CEREBRAS_BASE_URL,
}


def validate_model_access(settings: Settings, model: str | Model | None) -> None:
    """Validate credentials without including their values in errors."""
    if settings.provider != "openai":
        if settings.tracing_enabled:
            raise ConfigurationError("Non-OpenAI providers require --no-tracing.")
        if not isinstance(model, str) or not model.strip():
            raise ConfigurationError(
                "Non-OpenAI providers require an explicit --model or AGENT_MODEL."
            )
    key_name = PROVIDER_KEYS[settings.provider]
    if not os.getenv(key_name, "").strip():
        raise ConfigurationError(f"{key_name} is required for a model-backed run.")


@asynccontextmanager
async def configured_model(settings: Settings, model: str | Model | None):
    """Own and close the provider-specific compatibility client, even on cancellation."""
    if settings.provider == "openai":
        # Preserve ScriptedModel and the SDK's existing OpenAI resolution.
        yield model
        return
    validate_model_access(settings, model)
    async with AsyncOpenAI(
        api_key=os.environ[PROVIDER_KEYS[settings.provider]],
        base_url=COMPATIBILITY_URLS[settings.provider],
        # Do not inherit OpenAI account selection for another provider.
        organization="",
        project="",
        max_retries=0,
        timeout=settings.run_timeout_seconds,
    ) as client:
        yield OpenAIChatCompletionsModel(model=model, openai_client=client)
