from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT
from baserow_enterprise.assistant.tools.toolset import tool_manifest_line_compact

main_agent: Agent[AssistantDeps, str] = Agent(
    deps_type=AssistantDeps,
    output_type=str,
    instructions=AGENT_SYSTEM_PROMPT,
    retries=3,
    name="main_agent",
)


@main_agent.instructions
def dynamic_ui_context(ctx) -> str:
    """Inject the UI context into the system prompt dynamically."""

    ui_context = ctx.deps.tool_helpers.request_context.get("ui_context")
    if ui_context:
        return f"\n<ui_context>\n{ui_context}\n</ui_context>"
    return ""


@main_agent.instructions
def dynamic_mode(ctx) -> str:
    """Inject the current agent mode into the system prompt."""

    return f"\n<mode>{ctx.deps.mode.value}</mode>"


@main_agent.instructions
def dynamic_current_task(ctx) -> str:
    """Pin the original user request as immutable context."""

    if ctx.deps.original_request:
        return f"\n<current_task>\n{ctx.deps.original_request}\n</current_task>"
    return ""


@main_agent.instructions
def dynamic_tool_manifest(ctx) -> str:
    """
    Inject the available tools manifest into the system prompt, including both
    static and dynamically loaded tools name and description.
    """

    manifest = ctx.deps.active_manifest
    if not manifest:
        return ""

    # Append dynamically loaded tools (e.g. row tools from load_row_tools)
    if ctx.deps.dynamic_tools:
        extra = "\n".join(
            tool_manifest_line_compact(tool.name, tool.description or "")
            for tool in ctx.deps.dynamic_tools
        )
        manifest = manifest + "\n" + extra

    return f"\n<available_tools>\n{manifest}\n</available_tools>"


@main_agent.toolset
def dynamic_toolset(ctx: RunContext[AssistantDeps]):
    """Make dynamically loaded tools available to the agent."""

    if ctx.deps.dynamic_tools:
        ts = FunctionToolset()
        for tool in ctx.deps.dynamic_tools:
            ts.add_tool(tool)
        return ts
    return None


title_agent: Agent[None, str] = Agent(
    output_type=str,
    instructions="Create a short title (max 50 chars) for the following user request.",
    name="title_agent",
)
