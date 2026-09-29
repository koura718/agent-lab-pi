"""Non-secret settings: CLI > environment > explicit TOML > defaults."""

import argparse
import math
import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Invalid configuration; messages do not echo supplied values."""


@dataclass(frozen=True)
class Settings:
    provider: str = "openai"
    tracing_enabled: bool = False
    tool_mode: str = "function"
    model: str | None = None
    max_turns: int = 5
    run_timeout_seconds: float = 60
    connect_timeout_seconds: float = 10
    call_timeout_seconds: float = 10
    log_level: str = "INFO"

    def __post_init__(self):
        if self.provider not in ("openai", "anthropic", "cerebras"):
            raise ConfigurationError("provider must be openai, anthropic or cerebras.")
        if type(self.tracing_enabled) is not bool:
            raise ConfigurationError("tracing_enabled must be a boolean.")
        if self.tool_mode not in ("function", "mcp"):
            raise ConfigurationError("tool_mode must be function or mcp.")
        if self.model is not None and (
            not isinstance(self.model, str) or not self.model.strip()
        ):
            raise ConfigurationError("model must be a nonempty string.")
        if type(self.max_turns) is not int or not 1 <= self.max_turns <= 100:
            raise ConfigurationError("max_turns must be an integer from 1 to 100.")
        for field in (
            "run_timeout_seconds",
            "connect_timeout_seconds",
            "call_timeout_seconds",
        ):
            value = getattr(self, field)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 < value <= 3600
            ):
                raise ConfigurationError(
                    f"{field} must be finite, positive and at most 3600."
                )
        if self.log_level not in ("INFO", "WARNING", "ERROR"):
            raise ConfigurationError("log_level must be INFO, WARNING or ERROR.")


SECTIONS = {
    "agent": {"provider", "tool_mode", "model", "max_turns", "run_timeout_seconds"},
    "mcp": {"connect_timeout_seconds", "call_timeout_seconds"},
    "logging": {"level"},
    "tracing": {"enabled"},
}
ENVIRONMENT = {
    "provider": "AGENT_PROVIDER",
    "tracing_enabled": "AGENT_TRACING_ENABLED",
    "tool_mode": "AGENT_TOOL_MODE",
    "model": "AGENT_MODEL",
    "max_turns": "AGENT_MAX_TURNS",
    "run_timeout_seconds": "AGENT_RUN_TIMEOUT_SECONDS",
    "connect_timeout_seconds": "MCP_CONNECT_TIMEOUT_SECONDS",
    "call_timeout_seconds": "MCP_CALL_TIMEOUT_SECONDS",
    "log_level": "AGENT_LOG_LEVEL",
}


def add_settings_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, help="Explicit UTF-8 TOML configuration."
    )
    parser.add_argument(
        "--tracing",
        dest="tracing_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Opt in to metadata tracing export to OpenAI.",
    )
    parser.add_argument("--provider", choices=["openai", "anthropic", "cerebras"])
    parser.add_argument("--tool-mode", choices=["function", "mcp"])
    parser.add_argument("--model")
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--run-timeout", dest="run_timeout_seconds", type=float)
    parser.add_argument("--connect-timeout", dest="connect_timeout_seconds", type=float)
    parser.add_argument("--call-timeout", dest="call_timeout_seconds", type=float)
    parser.add_argument("--log-level", choices=["INFO", "WARNING", "ERROR"])


def load_settings(args: argparse.Namespace) -> Settings:
    values = asdict(Settings())
    if args.config is not None:
        try:
            with args.config.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, ValueError) as error:
            raise ConfigurationError(
                "Cannot read a valid UTF-8 TOML configuration."
            ) from error
        if set(document) - set(SECTIONS):
            raise ConfigurationError("Unknown configuration section.")
        for section, entries in document.items():
            if not isinstance(entries, dict) or set(entries) - SECTIONS[section]:
                raise ConfigurationError(
                    "Unknown configuration field or invalid section."
                )
            for key, value in entries.items():
                field = (
                    "log_level"
                    if section == "logging"
                    else "tracing_enabled"
                    if section == "tracing"
                    else key
                )
                values[field] = value
        Settings(
            **values
        )  # Reject invalid explicit files even if a later layer overrides.
    for key, variable in ENVIRONMENT.items():
        value = os.getenv(variable)
        if value is None:
            continue
        try:
            if key == "tracing_enabled":
                normalized = value.strip().lower()
                if normalized not in {"true", "false", "1", "0"}:
                    raise ValueError("Invalid boolean.")
                value = normalized in {"true", "1"}
            elif key == "max_turns":
                value = int(value)
            elif key.endswith("_seconds"):
                value = float(value)
        except ValueError as error:
            raise ConfigurationError(f"Invalid {variable} setting.") from error
        values[key] = value
    Settings(**values)
    for key in values:
        value = getattr(args, key, None)
        if value is not None:
            values[key] = value
    return Settings(**values)
