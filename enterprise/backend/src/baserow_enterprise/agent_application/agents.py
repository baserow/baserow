from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .deps import AgentRunDeps
from .prompts import (
    AGENT_BASE_PROMPT,
    AGENT_INSTRUCTIONS_PROMPT,
    AGENT_MEMORY_PROMPT,
)

agent_run_agent: Agent[AgentRunDeps, str] = Agent(
    deps_type=AgentRunDeps,
    output_type=str,
    name="agent_application_agent",
    retries=3,
)


@agent_run_agent.instructions
def base_instructions(ctx: RunContext[AgentRunDeps]) -> str:
    return AGENT_BASE_PROMPT.format(
        agent_name=ctx.deps.agent.name,
        workspace_name=ctx.deps.workspace.name,
    )


@agent_run_agent.instructions
def user_instructions(ctx: RunContext[AgentRunDeps]) -> str:
    instructions = ctx.deps.agent.instructions.strip()
    if not instructions:
        return ""
    return AGENT_INSTRUCTIONS_PROMPT.format(instructions=instructions)


@agent_run_agent.instructions
def persistent_memory(ctx: RunContext[AgentRunDeps]) -> str:
    memory = (ctx.deps.agent.memory or "").strip()
    if not memory:
        return ""
    return AGENT_MEMORY_PROMPT.format(memory=memory)


@agent_run_agent.instructions
def system_notes(ctx: RunContext[AgentRunDeps]) -> str:
    if not ctx.deps.system_notes:
        return ""
    return "Notes:\n" + "\n".join(f"- {note}" for note in ctx.deps.system_notes)


@agent_run_agent.toolset
def dynamic_toolset(ctx: RunContext[AgentRunDeps]):
    from .tools.gating import wrap_workspace_toolset

    # Tools can be appended to `deps.dynamic_tools` while a run is in
    # progress (e.g. per-table row tools loaded by the database tools).
    # Those are workspace tools, so the same read-only/approval gating as
    # the workspace toolset applies.
    return wrap_workspace_toolset(FunctionToolset(ctx.deps.dynamic_tools), ctx.deps)
