import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

from pydantic_ai import Tool

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace
    from baserow_enterprise.assistant.tools.navigation.types import (
        AnyNavigationRequestType,
    )


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
class EventBus:
    """
    Pushes streaming events into the queue consumed by
    Assistant.astream_messages(). Events are silently dropped when no
    queue is attached.
    """

    _queue: asyncio.Queue[QueueEvent] | None = None

    def set_queue(self, queue: asyncio.Queue[QueueEvent] | None):
        self._queue = queue

    def emit(self, event):
        if self._queue is not None:
            self._queue.put_nowait(
                QueueEvent(kind=QueueEventKind.STREAM, message=event)
            )


@dataclass
class ToolHelpers:
    """
    Contextual helpers available to every tool via ``RunContext[AssistantDeps]``.

    Provides status updates (shown in the UI), navigation actions,
    cancellation support, and an event bus for emitting custom streaming
    events (thinking messages, navigation messages, etc.).
    """

    update_status: Callable[[str], None]
    navigate_to: Callable[["AnyNavigationRequestType"], str]
    request_context: dict = field(default_factory=dict)
    event_bus: EventBus = field(default_factory=EventBus)
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
    sources: list[str] = field(default_factory=list)
    dynamic_tools: list[Tool] = field(default_factory=list)
    database_manifest: str = ""
    application_manifest: str = ""
    automation_manifest: str = ""
    explain_manifest: str = ""
    original_request: str = ""

    @property
    def active_manifest(self) -> str:
        return {
            AgentMode.DATABASE: self.database_manifest,
            AgentMode.APPLICATION: self.application_manifest,
            AgentMode.AUTOMATION: self.automation_manifest,
            AgentMode.EXPLAIN: self.explain_manifest,
        }[self.mode]

    def extend_sources(self, new_sources: list[str]):
        """
        Extend the current list of sources with new ones, avoiding
        duplicates.

        :param new_sources: The list of new source URLs to add.
        """

        self.sources.extend(s for s in new_sources if s not in self.sources)
