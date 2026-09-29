"""CLI for offline comparison and explicit model-backed Agent runs."""

import argparse
import asyncio
import json
import logging

from agents import Model, Runner

from agent_lab.agent_factory import create_agent
from agent_lab.config import (
    ConfigurationError,
    Settings,
    add_settings_arguments,
    load_settings,
)
from agent_lab.mcp.connection import agent_connection
from agent_lab.model_provider import configured_model, validate_model_access
from agent_lab.tools.list_tools import compare_json
from agent_lab.tracing_config import agent_run_config, tracing_runtime

DEFAULT_PROMPT = (
    "OpenAI Agents SDK が正常に動作していることを日本語で短く確認してください。"
)
from agent_lab.logging_config import cli_context, configure_logging, error_kind, timed

logger = logging.getLogger("agent_lab.main")


@timed("agent")
async def run_agent(prompt: str, model: str | Model | None, settings: Settings):
    if settings.provider != "openai":
        validate_model_access(settings, model)
    run_config = agent_run_config(settings)
    async with asyncio.timeout(settings.run_timeout_seconds):
        async with configured_model(settings, model) as selected_model:
            if settings.tool_mode == "mcp":
                async with agent_connection(settings) as server:
                    return await Runner.run(
                        create_agent(
                            model=selected_model,
                            mcp_server=server,
                            provider=settings.provider,
                        ),
                        prompt,
                        max_turns=settings.max_turns,
                        run_config=run_config,
                    )
            return await Runner.run(
                create_agent(model=selected_model, provider=settings.provider),
                prompt,
                max_turns=settings.max_turns,
                run_config=run_config,
            )


async def main(
    prompt: str = DEFAULT_PROMPT,
    model: str | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or Settings()
    if settings.provider != "openai":
        validate_model_access(settings, model)
    with tracing_runtime(settings.tracing_enabled):
        result = await run_agent(prompt, model, settings)
    print(result.final_output)


@cli_context()
def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--compare-json", help="Compare a JSON object locally; no API.")
    inputs.add_argument(
        "--prompt", help="Send this prompt to the model (API charges apply)."
    )
    add_settings_arguments(parser)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args)
    except ConfigurationError as error:
        logger.error(
            "Invalid configuration or CLI input",
            extra={"error_kind": "configuration_error"},
        )
        parser.error(str(error))
    if args.compare_json is not None and settings.tracing_enabled:
        parser.error("Tracing is available only for model-backed Agent runs.")
    if args.compare_json is not None and settings.tool_mode != "function":
        parser.error(
            "--compare-json is local-only; use the MCP diagnostic CLI for MCP calls."
        )
    configure_logging(settings.log_level)
    if args.compare_json is not None:
        output = compare_json(args.compare_json)
        print(output)
        return 2 if "error" in json.loads(output) else 0
    try:
        validate_model_access(settings, settings.model)
    except ConfigurationError as error:
        logger.error(str(error), extra={"error_kind": "configuration_error"})
        return 2
    try:
        logger.info("Starting Agent")
        asyncio.run(
            main(
                args.prompt if args.prompt is not None else DEFAULT_PROMPT,
                settings.model,
                settings,
            )
        )
    except KeyboardInterrupt:
        logger.warning("Agent interrupted", extra={"error_kind": "cancelled"})
        return 130
    except Exception as error:  # noqa: BLE001 - sanitize errors at the CLI boundary
        # Exception messages may include request data or credentials.
        logger.error(
            "Agent failed (%s). Check configuration and connectivity.",
            type(error).__name__,
            extra={"event": "agent_failed", "error_kind": error_kind(error)},
        )
        return 1
    logger.info("Agent completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
