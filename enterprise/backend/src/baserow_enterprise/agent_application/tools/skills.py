from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from ..deps import AgentRunDeps


async def load_skill(
    ctx: RunContext[AgentRunDeps],
    name: Annotated[str, Field(description="The exact name of the skill to load.")],
) -> str:
    """
    Returns the full instructions of one of the on-demand skills listed in
    your instructions. Call it before doing work the skill covers.
    """

    # The skills were preloaded with the run, so this never hits the database
    # from the async tool call.
    for agent_skill in ctx.deps.skills:
        if agent_skill.skill.name == name:
            return agent_skill.skill.content or "This skill has no content."
    available = ", ".join(agent_skill.skill.name for agent_skill in ctx.deps.skills)
    return f"Unknown skill {name!r}. Available skills: {available or 'none'}."


def build_skills_toolset() -> FunctionToolset:
    return FunctionToolset([load_skill])
