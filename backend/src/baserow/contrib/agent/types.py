from dataclasses import dataclass, field
from typing import NotRequired, TypedDict
from uuid import UUID

from django.db.models import F, Value

from pydantic_ai import Conversation, DeferredToolResults, WebSearchTool

from baserow.contrib.integrations.mcp.toolset import MCPServerSnapshot
from baserow.core.chat_runs.types import ChatRunStep, ChatRunWaitingCall
from baserow.core.models import Workspace
from baserow.core.pagination import KeysetCursor, RowLessThan
from baserow.core.types import Subject

from .constants import AgentConfigurationErrorCode, AgentReadinessState, AgentRunAsState
from .models import AgentApplication, AgentConversation, AgentMessage


@dataclass(frozen=True)
class AgentRunAsResolution:
    """A configured identity and its availability in the Agent's workspace."""

    status: AgentRunAsState
    subject_type: str | None
    subject_id: int | None
    subject: Subject | None = None
    name: str | None = None


class AgentToolConfiguration(TypedDict):
    allowed_tools: list[str]
    ask_first_tools: list[str]


@dataclass(frozen=True)
class AgentConfiguration:
    """The saved Agent configuration and its readiness at the time it was read."""

    readiness: AgentReadinessState
    instructions: str
    provider_type: str | None
    model_identifier: str | None
    reasoning_effort: str | None
    applied_reasoning_effort: str | None
    run_as: AgentRunAsResolution
    allowed_tools: list[str]
    web_search_enabled: bool
    web_search_available: bool
    web_search_blocked_by_tools: bool
    ask_first_tools: list[str]
    errors: dict[str, AgentConfigurationErrorCode]


class AgentToolDecision(TypedDict):
    """The owner's decision on a held call, by the id of its approval."""

    id: int
    approved: bool
    reason: NotRequired[str]
    """Why a held call is rejected, for the model."""


@dataclass
class AgentMessageCreated:
    """An accepted message, its reply's run, and the conversation's current run."""

    conversation: AgentConversation
    message: AgentMessage
    reply: AgentMessage | None
    run_id: UUID | None
    conversation_run_id: UUID | None
    created: bool


@dataclass
class AgentConfigurationUpdated:
    agent: AgentApplication
    original_values: dict[str, str | int | list[str] | None]
    new_values: dict[str, str | int | list[str] | None]
    configuration: AgentConfiguration


@dataclass
class AgentConversationUpdated:
    conversation: AgentConversation
    original_values: dict[str, str | bool]
    new_values: dict[str, str | bool]


@dataclass(frozen=True)
class AgentConversationCursor(KeysetCursor):
    """A position in pinned-first, then most recently active conversation order."""

    pinned: bool = False

    def get_filter(self, field_name: str):
        return RowLessThan(
            (F("pinned"), F(field_name), F("id")),
            (Value(self.pinned), Value(self.value), Value(self.id)),
        )


@dataclass(frozen=True)
class AgentToolDecisionsResult:
    """Saved decisions on a reply's held calls, and what they changed."""

    reply: AgentMessage
    approved_tools: list[str]
    """The tools of the calls approved by these decisions."""
    rejected_tools: list[str]
    """The tools of the calls rejected by these decisions."""
    always_allowed_tools: list[str]
    """The tools that stopped asking first, in registry order."""
    run_id: UUID | None
    """The run continuing the reply, or None while some calls are undecided."""


@dataclass(frozen=True)
class AgentReplyResume:
    """A paused run of a reply, continued once its held calls are decided."""

    paused_conversation: Conversation
    """The paused run, with its messages and held calls."""
    deferred_tool_results: DeferredToolResults
    """The owner's decisions on the held calls."""
    saved_steps: list[ChatRunStep]
    """The steps the paused reply saved, in call order."""
    held_step_ids: dict[str, str]
    """The step id of each held call, by its tool call id."""
    approved_ids: frozenset[str]
    """The tool call ids of the held calls the owner approved."""


@dataclass(frozen=True)
class AgentReplyRequest:
    reply_id: int
    workspace: Workspace | None
    instructions: str
    provider_type: str
    model_identifier: str
    prompt: str | None = None
    """The message the reply answers, or None when it resumes."""
    history: list[AgentMessage] = field(default_factory=list)
    """The earlier messages of the conversation, oldest first."""
    resume: AgentReplyResume | None = None
    """The paused run to continue, instead of answering a prompt."""
    run_as_unavailable: bool = False
    """An identity is configured but cannot be used for workspace access."""
    acting_subject: Subject | None = None
    """Who the tools act as, or None for no workspace access."""
    allowed_tool_names: list[str] = field(default_factory=list)
    """The tools the reply may call, none without an identity to act as."""
    ask_first_tool_names: list[str] = field(default_factory=list)
    """The allowed tools whose calls wait for the owner's approval."""
    timezone: str | None = None
    """The timezone of the owner, for the dates the tools read and write."""
    mcp_servers: tuple[MCPServerSnapshot, ...] = ()
    """The MCP servers with tools turned on, as reviewed when the reply started."""
    reasoning_effort: str | None = None
    """How much the model reasons, or None for its default."""
    web_search_tool: WebSearchTool | None = None
    """The provider's web search, when it's turned on and the model has one."""
    web_search_enabled: bool = False
    """Whether web search is turned on, even when the model can't use it."""


@dataclass(frozen=True)
class AgentPausedRun:
    """A run that paused for approvals, with what its resume must continue with."""

    conversation: dict
    """The run, dumped with its messages and held calls."""
    web_search: bool
    """Whether it offered web search."""
    run_as: Subject | None
    """Who its tools acted as, or None for no workspace access."""


@dataclass(frozen=True)
class AgentReplyResult:
    """What a reply produced, complete or partial."""

    text: str
    provider_type: str | None = None
    model_identifier: str | None = None
    model_messages: list[dict] | None = None
    usage: dict | None = None
    steps: list[ChatRunStep] | None = None
    """Its tool calls in call order, or None when it made none."""
    waiting_calls: list[ChatRunWaitingCall] = field(default_factory=list)
    """The calls held for the owner's approval, when the run paused."""
    tool_keys: dict[str, str] = field(default_factory=dict)
    """The approval key of each held MCP call's tool, by tool name."""
    paused_run: AgentPausedRun | None = None
    """The paused run, to resume once its held calls are decided."""

    @property
    def paused(self) -> bool:
        """Whether the run paused for approvals instead of answering."""

        return self.paused_run is not None
