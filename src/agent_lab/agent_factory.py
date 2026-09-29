"""Build Agents without performing model requests."""

from agents import Agent, Model, ModelSettings
from agents.mcp import MCPServer
from openai.types.shared import Reasoning

from agent_lab.tools.list_tools import create_compare_lists_tool


def create_agent(
    *,
    model: str | Model | None = None,
    mcp_server: MCPServer | None = None,
    provider: str = "openai",
) -> Agent:
    return Agent(
        name="Assistant",
        instructions=(
            "You are a concise and reliable AI development assistant. "
            "Answer in Japanese unless instructed otherwise. "
            "Use compare_lists when asked to compare two string lists. "
            "Preserve the user's values exactly. If a list is missing, ask for it. "
            "Report tool input errors; never invent a successful comparison."
        ),
        model=model,
        # Qwen strict schemas reject string length constraints. Keep the full
        # schema and enforce bounds in the shared domain validator instead.
        tools=[]
        if mcp_server is not None
        else [create_compare_lists_tool(strict_json_schema=provider != "cerebras")],
        # This adapter does not replay Cerebras' separate reasoning field.
        # Disable Qwen reasoning for the supported text/tool evaluation path.
        model_settings=ModelSettings(reasoning=Reasoning(effort="none"))
        if provider == "cerebras" and getattr(model, "model", model) == "qwen-3.8-27b"
        else ModelSettings(),
        mcp_servers=[mcp_server] if mcp_server is not None else [],
    )
