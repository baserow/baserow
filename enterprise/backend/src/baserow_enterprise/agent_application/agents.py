from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .deps import AgentRunDeps
from .prompts import (
    AGENT_BASE_PROMPT,
    AGENT_INSTRUCTIONS_PROMPT,
    AGENT_MEMORY_PROMPT,
    AGENT_SKILLS_ON_DEMAND_PROMPT,
    AGENT_SKILLS_PROMPT,
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
    from .triggers.registries import substitute_trigger_tokens

    instructions = ctx.deps.agent.instructions.strip()
    if not instructions:
        return ""
    chat = ctx.deps.chat
    if chat is not None and chat.trigger_type:
        instructions = substitute_trigger_tokens(
            instructions, chat.trigger_type, chat.event_payload
        )
    return AGENT_INSTRUCTIONS_PROMPT.format(instructions=instructions)


@agent_run_agent.instructions
def workspace_skills(ctx: RunContext[AgentRunDeps]) -> str:
    from .models import AgentSkill

    always = [
        agent_skill.skill
        for agent_skill in ctx.deps.skills
        if agent_skill.mode == AgentSkill.Mode.ALWAYS
    ]
    on_demand = [
        agent_skill.skill
        for agent_skill in ctx.deps.skills
        if agent_skill.mode == AgentSkill.Mode.ON_DEMAND
    ]
    if not always and not on_demand:
        return ""

    always_text = "".join(
        f'<skill name="{skill.name}">\n{skill.content.strip()}\n</skill>\n'
        for skill in always
    )
    on_demand_text = (
        AGENT_SKILLS_ON_DEMAND_PROMPT.format(
            listing="\n".join(
                f"- {skill.name}: {skill.description.strip() or 'No description.'}"
                for skill in on_demand
            )
        )
        if on_demand
        else ""
    )
    return AGENT_SKILLS_PROMPT.format(always=always_text, on_demand=on_demand_text)


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
    from .tools.workspace import ErrorHandlingToolset

    # Tools can be appended to `deps.dynamic_tools` while a run is in
    # progress (e.g. per-table row tools loaded by the database tools).
    # Those are workspace tools, so the same tool rules and error handling
    # as the workspace toolset apply.
    return wrap_workspace_toolset(
        ErrorHandlingToolset(FunctionToolset(ctx.deps.dynamic_tools)), ctx.deps
    )
