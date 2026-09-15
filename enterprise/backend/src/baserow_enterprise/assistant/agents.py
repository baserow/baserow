import json

from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps
from baserow_enterprise.assistant.output_validation import validate_final_answer
from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT

FREE_LICENSE_TIER = "free"
_CANONICAL_LICENSE_TIERS = {
    FREE_LICENSE_TIER,
    "premium",
    "advanced",
    "enterprise",
}
_LICENSE_TIER_ALIASES = {
    "enterprise_without_support": "enterprise",
}

main_agent: Agent[AssistantDeps, str] = Agent(
    deps_type=AssistantDeps,
    output_type=str,
    instructions=AGENT_SYSTEM_PROMPT,
    retries=3,
    name="main_agent",
)
main_agent.output_validator(validate_final_answer)


def _canonical_license_tier(license_tier: str) -> str:
    """
    Return the public license tier token that is safe to inject into the prompt.
    """

    normalized_tier = _LICENSE_TIER_ALIASES.get(license_tier, license_tier)
    if normalized_tier in _CANONICAL_LICENSE_TIERS:
        return normalized_tier
    return FREE_LICENSE_TIER


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
def dynamic_license_tier(ctx) -> str:
    """Inject the active workspace license tier and its paid features."""

    lt = ctx.deps.license_tier
    if lt is None:
        return f"\n<license_tier>{FREE_LICENSE_TIER}</license_tier>"
    features = ",".join(sorted(lt.features))
    return (
        f"\n<license_tier>{_canonical_license_tier(lt.type)}</license_tier>"
        f"\n<features>{features}</features>"
    )


@main_agent.instructions
def dynamic_verified_tool_outcomes(ctx) -> str:
    """
    Inject bounded, verified prior tool outcomes.

    :param ctx: The agent run context.
    :return: The <verified_prior_actions> instruction block, or an empty
        string when there are no outcomes.
    """

    outcomes = ctx.deps.verified_tool_outcomes
    if not outcomes:
        return ""
    visible_outcomes = [
        {key: value for key, value in outcome.items() if key != "_request_fingerprint"}
        for outcome in outcomes
    ]
    serialized = json.dumps(visible_outcomes, separators=(",", ":"), ensure_ascii=False)
    return (
        "\n<verified_prior_actions>\n"
        f"{serialized}\n"
        "These are factual results from earlier tool calls. Reuse their verified "
        "IDs and do not duplicate resources. Results may describe reused or "
        "partial work; they do not prove the current request is complete.\n"
        "</verified_prior_actions>"
    )


@main_agent.instructions
def dynamic_tool_catalog(ctx) -> str:
    """
    Inject the compact tool ownership catalog into the system prompt.

    :param ctx: The agent run context.
    :return: The <tool_catalog> instruction block, or an empty string when
        there is no catalog.
    """

    catalog = ctx.deps.tool_catalog
    if not catalog:
        return ""

    if ctx.deps.mode == AgentMode.DATABASE and ctx.deps.dynamic_tools:
        names = ", ".join(tool.name for tool in ctx.deps.dynamic_tools)
        catalog = f"{catalog}\n- database row tools: {names}"

    return f"\n<tool_catalog>\n{catalog}\n</tool_catalog>"


@main_agent.toolset
def dynamic_toolset(ctx: RunContext[AssistantDeps]):
    """
    Make dynamically loaded tools available to the agent.

    :param ctx: The agent run context.
    :return: A toolset with the dynamic row tools in database mode, or None.
    """

    if ctx.deps.mode == AgentMode.DATABASE and ctx.deps.dynamic_tools:
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
