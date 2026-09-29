"""Strict JSON boundary for the compare_lists Function Tool."""

import json
import logging
from typing import Any

from agents import FunctionTool
from agents.tool_context import ToolContext

from agent_lab.domain.list_comparison import (
    ComparisonInputError,
    compare_arguments,
    input_schema,
)
from agent_lab.logging_config import timed

logger = logging.getLogger(__name__)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ComparisonInputError("Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ComparisonInputError("Non-standard JSON constants are not allowed.")


@timed(
    "compare_lists",
    lambda result: "invalid_input" if "error" in json.loads(result) else "none",
)
def compare_json(arguments: str) -> str:
    """Execute the tool contract locally without an API or SDK runner.

    Success has three result arrays. Failure has only an error object, never
    empty success arrays. Neither logs nor error messages echo input values.
    """
    try:
        try:
            payload = json.loads(
                arguments,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except ComparisonInputError:
            raise
        except (ValueError, RecursionError) as error:
            # Includes oversized integers rejected by the JSON decoder.
            raise ComparisonInputError("Provide a valid JSON object.") from error
        result = compare_arguments(payload)
    except ComparisonInputError as error:
        logger.warning("compare_lists rejected invalid input")
        return json.dumps({"error": {"code": "INVALID_INPUT", "message": str(error)}})
    logger.info("compare_lists completed")
    return json.dumps(result, ensure_ascii=False)


async def _invoke_compare_lists(context: ToolContext[Any], arguments: str) -> str:
    return compare_json(arguments)


def create_compare_lists_tool(*, strict_json_schema: bool = True) -> FunctionTool:
    """Create a fresh tool/schema for each Agent; no model is initialized."""
    return FunctionTool(
        name="compare_lists",
        description=(
            "Compare source and baseline string lists as sets. Return same, "
            "source_only and baseline_only, sorted in Unicode code-point order. "
            "Preserve case and whitespace; do not normalize Unicode. "
            "Invalid input returns an error object, not comparison results."
        ),
        params_json_schema=input_schema(),
        on_invoke_tool=_invoke_compare_lists,
        strict_json_schema=strict_json_schema,
    )
