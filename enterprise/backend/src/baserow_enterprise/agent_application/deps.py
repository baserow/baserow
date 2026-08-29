from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union

from pydantic_ai import Tool

from baserow_enterprise.assistant.deps import (  # noqa: F401
    EventBus,
    QueueEvent,
    QueueEventKind,
    ToolHelpers,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Agent, Workspace

    from .models import AgentChat, AgentDefinition


@dataclass
class AgentRunDeps:
    """
    Typed dependency container for an agent run.

    The actor is exposed as ``user`` because the reused assistant tools read
    ``ctx.deps.user`` and pass it as the actor into the permission-checked
    service/action layers, which accept both users and `core.Agent` subjects.
    """

    user: Union["AbstractUser", "Agent"]
    workspace: "Workspace"
    agent: "AgentDefinition"
    chat: "AgentChat"
    tool_helpers: ToolHelpers
    sources: list[str] = field(default_factory=list)
    dynamic_tools: list[Tool] = field(default_factory=list)
    # Extra notes tool types can add to the system prompt (e.g. "web search
    # unavailable for this provider").
    system_notes: list[str] = field(default_factory=list)
    # Set from the workspace AgentTool config; these also apply to the
    # dynamically loaded per-table row tools.
    workspace_tools_read_only: bool = False
    workspace_write_approval: bool = True

    def extend_sources(self, new_sources: list[str]):
        self.sources.extend(s for s in new_sources if s not in self.sources)
