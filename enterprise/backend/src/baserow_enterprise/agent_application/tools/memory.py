from typing import Annotated

from django.db.models import Case, F, TextField, Value, When
from django.db.models.functions import Concat

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from ..deps import AgentRunDeps

# Soft cap keeping the memory small enough to inject into every prompt.
AGENT_MEMORY_MAX_LENGTH = 10000

_THOUGHT = Annotated[str, Field(description="Brief reasoning for calling this tool.")]


def _broadcast(agent_id: int) -> None:
    from ..models import AgentDefinition
    from ..realtime import broadcast_agent_definition_updated

    broadcast_agent_definition_updated(AgentDefinition.objects.get(id=agent_id))


async def remember(
    ctx: RunContext[AgentRunDeps],
    text: Annotated[
        str,
        Field(
            description=(
                "The note to append to your memory. One or a few short "
                "lines; include concrete identifiers (e.g. table ids)."
            )
        ),
    ],
    thought: _THOUGHT,
) -> dict:
    """
    Appends a note to your persistent memory, which is loaded into every
    future conversation. Only use it for durable facts you will need again
    (things you created and their ids, user preferences, lessons learned) —
    never for conversation-specific details.
    """

    from ..models import AgentDefinition

    def append():
        current_length = len(ctx.deps.agent.memory or "")
        if current_length + len(text) > AGENT_MEMORY_MAX_LENGTH:
            return {
                "error": (
                    "Your memory is full. Use rewrite_memory to rewrite it "
                    "more compactly, keeping only what still matters."
                )
            }

        # A single UPDATE statement appending to the current value, so
        # concurrent runs can both remember without losing each other's
        # notes. The first note must not start with a separator newline.
        AgentDefinition.objects.filter(id=ctx.deps.agent.id).update(
            memory=Case(
                When(memory="", then=Value(text)),
                default=Concat(
                    F("memory"), Value(f"\n{text}"), output_field=TextField()
                ),
                output_field=TextField(),
            )
        )
        ctx.deps.agent.refresh_from_db(fields=["memory"])
        _broadcast(ctx.deps.agent.id)
        return {"success": True}

    return await sync_to_async(append)()


async def rewrite_memory(
    ctx: RunContext[AgentRunDeps],
    new_memory: Annotated[
        str,
        Field(description="The complete new memory content, replacing the old one."),
    ],
    thought: _THOUGHT,
) -> dict:
    """
    Replaces your entire persistent memory. Only use this to compact or
    reorganize it (e.g. when it is full or contains outdated notes); to add
    a note, use remember instead, which is safe when multiple of your runs
    happen at the same time.
    """

    from ..models import AgentDefinition

    def rewrite():
        if len(new_memory) > AGENT_MEMORY_MAX_LENGTH:
            return {
                "error": f"The memory cannot exceed {AGENT_MEMORY_MAX_LENGTH} "
                "characters. Write it more compactly."
            }

        AgentDefinition.objects.filter(id=ctx.deps.agent.id).update(memory=new_memory)
        ctx.deps.agent.refresh_from_db(fields=["memory"])
        _broadcast(ctx.deps.agent.id)
        return {"success": True}

    return await sync_to_async(rewrite)()


MEMORY_TOOL_FUNCTIONS = [remember, rewrite_memory]


def build_memory_toolset() -> FunctionToolset:
    return FunctionToolset(MEMORY_TOOL_FUNCTIONS, max_retries=3)
