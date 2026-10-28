import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

from pydantic_ai import Tool

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace
    from baserow.core.tools import ToolContext
    from baserow_enterprise.assistant.model_profiles import (
        ResolvedAssistantModelProfile,
    )
    from baserow_enterprise.assistant.tools.navigation.types import (
        AnyNavigationRequestType,
    )
    from baserow_premium.license.registries import LicenseType


class AgentMode(str, Enum):
    """Operating mode that controls which tools are available to the agent."""

    DATABASE = "database"
    APPLICATION = "application"
    AUTOMATION = "automation"
    EXPLAIN = "explain"


class QueueEventKind(Enum):
    STREAM = auto()
    RESULT = auto()
    ERROR = auto()
    DONE = auto()


@dataclass
class QueueEvent:
    kind: QueueEventKind
    message: Any = None
    answer: str = ""
    messages_json: bytes = b""
    error: Exception | None = None


@dataclass
class ToolHelpers:
    """
    Contextual helpers available to every tool via ``RunContext[AssistantDeps]``.

    Provides the request's resolved model profile, UI status and navigation
    callbacks, and cancellation support.
    """

    update_status: Callable[[str], None]
    navigate_to: Callable[["AnyNavigationRequestType"], str]
    model_profile: "ResolvedAssistantModelProfile"
    request_context: dict = field(default_factory=dict)
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    def raise_if_cancelled(self) -> None:
        """Check cancellation and raise if set. Thread-safe.

        Call this in tool loops or between expensive operations.
        Raises ``CancelledError`` (``BaseException``) which escapes the
        agent's ``except Exception`` handler and propagates through the
        async chain.
        """

        if self._cancel_event.is_set():
            raise asyncio.CancelledError()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancelled without raising. Thread-safe."""

        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Signal cancellation to running tools. Thread-safe."""

        self._cancel_event.set()


_agent_tool_helpers: ContextVar[ToolHelpers | None] = ContextVar(
    "assistant_agent_tool_helpers", default=None
)


@contextmanager
def bind_tool_helpers(tool_helpers: ToolHelpers) -> Iterator[None]:
    """
    Makes an agent's tool helpers visible to every model call made for it,
    including the calls of sub-agents that its tools start in other threads,
    which inherit its context.

    :param tool_helpers: The tool helpers of the agent.
    """

    token = _agent_tool_helpers.set(tool_helpers)
    try:
        yield
    finally:
        _agent_tool_helpers.reset(token)


def raise_if_agent_cancelled() -> None:
    """
    Stops a model call before it starts when the agent it is made for was
    cancelled, so sub-agents of a stopped agent make no new requests.

    :raises asyncio.CancelledError: When the agent was cancelled.
    """

    tool_helpers = _agent_tool_helpers.get()
    if tool_helpers is not None:
        tool_helpers.raise_if_cancelled()


@dataclass
class ResourceChanges:
    """Track successful resource changes within one run, across tool rebuilds."""

    created_row_counts: dict[int, int] = field(default_factory=dict)

    def record_created_rows(self, table_id: int, count: int) -> int:
        """Record a successful batch and return the table's running creation total."""

        total = self.created_row_counts.get(table_id, 0) + count
        self.created_row_counts[table_id] = total
        return total


@dataclass
class AssistantDeps:
    """
    Typed dependency container for the pydantic-ai agent.

    Every agent run operates on behalf of a user in a given workspace.
    This runtime-context also allows tools to share information (e.g.
    sources), provide helpers for emitting events or requesting navigation,
    switch between domain modes, and dynamically extend the toolset by
    adding tools to ``dynamic_tools`` during a run (e.g. row tools loaded
    by the database agent).

    Passed via ``deps=`` to every ``agent.run()`` / ``agent.run_stream()``
    call and accessible in tools via ``RunContext[AssistantDeps].deps``.
    """

    user: "AbstractUser"
    workspace: "Workspace"
    tool_helpers: ToolHelpers
    mode: AgentMode = AgentMode.DATABASE
    license_tier: "LicenseType | None" = None
    sources: list[str] = field(default_factory=list)
    dynamic_tools: list[Tool] = field(default_factory=list)
    resource_changes: ResourceChanges = field(default_factory=ResourceChanges)
    tool_catalog: str = ""
    verified_tool_outcomes: list[dict[str, Any]] = field(default_factory=list)
    pending_question: str | None = None

    def extend_sources(self, new_sources: list[str]):
        """
        Extend the current list of sources with new ones, avoiding
        duplicates.

        :param new_sources: The list of new source URLs to add.
        """

        self.sources.extend(s for s in new_sources if s not in self.sources)

    def tool_context(self) -> "ToolContext":
        """The context for calling a tool shared with the other clients."""

        from baserow.core.tools import ToolContext

        tool_helpers = self.tool_helpers

        # Shared tools report status between steps, so a cancelled chat stops there.
        def update_status(message: str) -> None:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(message)

        return ToolContext(
            user=self.user,
            workspace=self.workspace,
            update_status=update_status,
            timezone=self.user.profile.timezone,
        )
