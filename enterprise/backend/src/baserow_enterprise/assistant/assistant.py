import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.utils import translation

from loguru import logger
from pydantic_ai._thinking_part import split_content_into_text_and_thinking
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.tool_manager import ToolManager
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from baserow.api.sessions import get_client_undo_redo_action_group_id
from baserow.core.models import Workspace
from baserow_enterprise.assistant.action_memory import get_verified_tool_outcomes
from baserow_enterprise.assistant.agents import main_agent, title_agent
from baserow_enterprise.assistant.deps import (
    AgentMode,
    AssistantDeps,
    EventBus,
    QueueEvent,
    QueueEventKind,
    ToolHelpers,
)
from baserow_enterprise.assistant.exceptions import AssistantMessageCancelled
from baserow_enterprise.assistant.history import compact_message_history
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    TITLE,
    get_model_settings,
    get_model_string,
)
from baserow_enterprise.assistant.retrying_model import RetryingModel
from baserow_enterprise.assistant.telemetry import (
    PosthogTracingCallback,
    setup_instrumentation,
)
from baserow_enterprise.assistant.tools.navigation.utils import unsafe_navigate_to
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_premium.api.user.user_data_types import ActiveLicensesDataType
from baserow_premium.license.registries import LicenseType, license_type_registry

from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
from .types import (
    AiMessage,
    AiMessageChunk,
    AiReasoningChunk,
    AiStartedMessage,
    AiThinkingMessage,
    AssistantMessageUnion,
    ChatTitleMessage,
    HumanMessage,
    UIContext,
)

_CANCELLATION_KEY_TTL = 300  # seconds
_THINKING_TAGS = ("<think>", "</think>")


@dataclass
class _QueuedRunResult:
    answer: str | None = None
    messages_json: bytes = b""


def _strip_think_tags(text: str) -> str:
    """Remove ``<think>...</think>`` blocks from *text*, returning only the
    non-thinking content.  Uses pydantic-ai's own tag parser.

    Also strips any trailing unclosed ``<think>`` block that may appear
    during streaming (the closing tag hasn't arrived yet).
    """

    if "<think>" not in text:
        return text

    # Strip any trailing unclosed <think> block (common during streaming)
    last_open = text.rfind("<think>")
    last_close = text.rfind("</think>")
    if last_open > last_close:
        text = text[:last_open]

    if "<think>" not in text:
        return text.strip()

    parts = split_content_into_text_and_thinking(text, _THINKING_TAGS)
    return "".join(p.content for p in parts if not isinstance(p, ThinkingPart)).strip()


def get_assistant_cancellation_key(chat_uuid: str) -> str:
    """Return the cache key used to signal cancellation for a chat session."""

    return f"assistant:chat:{chat_uuid}:cancelled"


def set_assistant_cancellation_key(
    chat_uuid: str, timeout: int = _CANCELLATION_KEY_TTL
) -> None:
    """Set the cancellation flag in the cache for a chat session."""

    cache.set(get_assistant_cancellation_key(chat_uuid), True, timeout=timeout)


def _get_workspace_license_type(
    user: AbstractUser, workspace: Workspace
) -> LicenseType | None:
    """
    Pick the highest-``order`` ``LicenseType`` active for the user in the workspace,
    reusing the same data the frontend consumes from ``ActiveLicensesDataType``. Returns
    ``None`` when no license applies.

    :param user: The user for whom to get the license type.
    :param workspace: The workspace for which to get the license type.
    :return: The active LicenseType with the highest order, or None if no license is
        active.
    """

    try:
        active = ActiveLicensesDataType().get_user_data(user, None)
        names = set(active["instance_wide"]) | set(
            active["per_workspace"].get(workspace.id, {})
        )
        return max(
            (lt for lt in license_type_registry.get_all() if lt.type in names),
            key=lambda lt: lt.order,
            default=None,
        )
    except Exception:
        logger.exception(
            "Failed to determine workspace license type for assistant context."
        )
        return None


@dataclass
class AgentRunContext:
    deps: AssistantDeps
    toolset: AbstractToolset
    model: RetryingModel | str


def build_agent_run_context(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: ToolHelpers,
    model: str | None = None,
    wrap_retrying: bool = True,
) -> AgentRunContext:
    """Single seam building deps + toolset + manifests, used by Assistant and evals.

    :param tool_helpers: Caller-provided helpers (production wires status
        updates/navigation via ``Assistant._build_tool_helpers``; evals pass
        no-op helpers).
    :param model: The pydantic-ai model string. ``None`` resolves the
        default via ``get_model_string()`` (reads Django settings).
    :param wrap_retrying: Wrap the resolved model in ``RetryingModel``.
    """

    model_string = get_model_string(model)
    resolved_model: RetryingModel | str = (
        RetryingModel(model_string) if wrap_retrying else model_string
    )

    deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
        license_tier=_get_workspace_license_type(user, workspace),
    )
    toolset, deps.tool_catalog = assistant_tool_registry.build_toolset(
        user=user, workspace=workspace, model=model_string, deps=deps
    )

    return AgentRunContext(deps=deps, toolset=toolset, model=resolved_model)


def _extract_tool_thought(event: FunctionToolCallEvent) -> str | None:
    """Extract the chain-of-thought ``thought`` argument from a tool call
    event, if present and non-empty."""

    try:
        args = event.part.args_as_dict()
    except Exception:
        return None
    thought = args.get("thought")
    return thought if isinstance(thought, str) and thought.strip() else None


def _mode_for_ui_context(ui_context: UIContext | None) -> AgentMode | None:
    """Return the mode implied by the current UI."""

    if ui_context is None:
        return None
    if ui_context.application or ui_context.page:
        return AgentMode.APPLICATION
    if ui_context.automation or ui_context.workflow:
        return AgentMode.AUTOMATION
    return AgentMode.DATABASE


class Assistant:
    """Orchestrates a single assistant chat session.

    Wires together the pydantic-ai agent, toolsets, telemetry, event
    streaming, and message persistence for one ``AssistantChat``.
    """

    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace
        self._event_bus = EventBus()
        self._tool_helpers = self._build_tool_helpers()
        self._telemetry = PosthogTracingCallback()

        self._model_string = get_model_string()
        ctx = build_agent_run_context(
            self._user, self._workspace, self._tool_helpers, model=self._model_string
        )
        self._model = ctx.model
        self._deps = ctx.deps
        self._toolset = ctx.toolset

        setup_instrumentation()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_tool_helpers(self) -> ToolHelpers:
        """Create the ``ToolHelpers`` that tools use for status updates,
        navigation, and cancellation during the agent run."""

        def update_status(status: str):
            with translation.override(self._user.profile.language):
                self._event_bus.emit(AiThinkingMessage(content=status))

        return ToolHelpers(
            update_status=update_status,
            navigate_to=lambda loc: unsafe_navigate_to(loc, self._event_bus),
            event_bus=self._event_bus,
        )

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    async def acreate_chat_message(
        self,
        role: AssistantChatMessage.Role,
        content: str,
        artifacts: dict[str, Any] | None = None,
        **kwargs,
    ) -> AssistantChatMessage:
        """Persist a new chat message to the database."""

        message = AssistantChatMessage(
            chat=self._chat, role=role, content=content, **kwargs
        )
        if artifacts:
            message.artifacts = artifacts
        await message.asave()
        return message

    def list_chat_messages(
        self, last_message_id: int | None = None, limit: int = 100
    ) -> list[AssistantMessageUnion]:
        """Return recent chat messages, oldest-first.

        :param last_message_id: If set, only return messages with ``id``
            below this value (cursor-based pagination).
        :param limit: Maximum number of messages to return.
        """

        queryset = (
            self._chat.messages.all()
            .select_related("prediction")
            .order_by("-created_on")
        )
        if last_message_id is not None:
            queryset = queryset.filter(id__lt=last_message_id)

        messages: list[AssistantMessageUnion] = []
        for msg in queryset[:limit]:
            if msg.role == AssistantChatMessage.Role.HUMAN:
                messages.append(
                    HumanMessage(
                        content=msg.content, id=msg.id, timestamp=msg.created_on
                    )
                )
            else:
                sentiment_data = {}
                if getattr(msg, "prediction", None):
                    sentiment_data = {
                        "can_submit_feedback": True,
                        "human_sentiment": msg.prediction.get_human_sentiment_display(),
                    }
                messages.append(
                    AiMessage(
                        content=msg.content,
                        id=msg.id,
                        timestamp=msg.created_on,
                        **sentiment_data,
                    )
                )
        return list(reversed(messages))

    async def _save_ai_response(
        self, human_msg: AssistantChatMessage, answer: str
    ) -> AiMessage:
        """Persist the AI answer and create a prediction record for
        feedback tracking."""

        sources = self._deps.sources
        ai_msg = await self.acreate_chat_message(
            AssistantChatMessage.Role.AI,
            answer,
            artifacts={"sources": sources},
            action_group_id=get_client_undo_redo_action_group_id(self._user),
        )
        await AssistantChatPrediction.objects.acreate(
            human_message=human_msg,
            ai_response=ai_msg,
            prediction={"answer": answer},
        )
        return AiMessage(
            id=ai_msg.id,
            content=answer,
            sources=sources,
            can_submit_feedback=True,
        )

    # ------------------------------------------------------------------
    # Message history (pydantic-ai ModelMessage round-trips)
    # ------------------------------------------------------------------

    async def _save_message_history(self, messages_json: bytes) -> None:
        """Persist the serialised pydantic-ai message history on the chat."""

        self._chat.message_history = messages_json
        await self._chat.asave(update_fields=["message_history", "updated_on"])

    async def _load_message_history(self) -> list[ModelMessage] | None:
        """Deserialise and compact the stored message history.

        :return: The compacted history, or ``None`` if absent or corrupt.
        """

        raw = self._chat.message_history
        if not raw:
            return None
        try:
            messages = ModelMessagesTypeAdapter.validate_json(bytes(raw))
            compacted = compact_message_history(messages)
            self._deps.verified_tool_outcomes = get_verified_tool_outcomes(compacted)
            return compacted
        except Exception:
            logger.opt(exception=True).warning(
                "Failed to load message history for chat {}, starting fresh",
                self._chat.pk,
            )
            return None

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def _generate_chat_title(self, user_message: str) -> str:
        """Ask the title agent to summarise a user message into a short
        chat title."""

        result = await title_agent.run(
            user_message,
            model=self._model,
            model_settings=get_model_settings(self._model_string, TITLE),
        )
        return result.output

    async def _emit_answer(
        self,
        answer: str,
        run_result: Any,
        queue: asyncio.Queue[QueueEvent],
    ) -> None:
        """Push the final answer and result events onto *queue*."""

        await queue.put(
            QueueEvent(
                kind=QueueEventKind.STREAM,
                message=AiMessageChunk(content=answer, sources=self._deps.sources),
            )
        )
        queue.put_nowait(
            QueueEvent(
                kind=QueueEventKind.RESULT,
                answer=answer,
                messages_json=run_result.all_messages_json(),
            )
        )

    async def _run_agent(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> None:
        """Execute the main agent via ``_stream_agent_run``.

        Pushes ``STREAM``, ``RESULT``, ``ERROR``, and ``DONE`` events
        onto *queue* for the consumer in ``astream_messages``.

        :param user_prompt: The user message to answer.
        :param message_history: Prior conversation to resume from, if any.
        :param queue: The queue consumed by ``astream_messages``.
        :raises RuntimeError: If the stream ends without a result event.
        """

        try:
            with self._telemetry.trace(self._chat, user_prompt) as tracer:
                result = await self._stream_agent_run(
                    user_prompt, message_history, queue
                )
                if result is None:
                    raise RuntimeError("Agent stream ended without a result event")
                answer, run_result = result
                tracer.set_trace_output(answer)
                await self._emit_answer(answer, run_result, queue)
        except Exception as exc:
            logger.exception("Error running main agent")
            queue.put_nowait(QueueEvent(kind=QueueEventKind.ERROR, error=exc))
        finally:
            queue.put_nowait(QueueEvent(kind=QueueEventKind.DONE))

    async def _stream_agent_run(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> tuple[str, Any] | None:
        """Run a single agent streaming pass.

        :param user_prompt: The user message to answer.
        :param message_history: Prior conversation to resume from, if any.
        :param queue: The queue reasoning/text chunks are streamed to.
        :return: ``(answer, run_result)`` when an ``AgentRunResultEvent`` is
            received, or ``None`` if the stream ends without one.
        """

        with ToolManager.parallel_execution_mode("sequential"):
            async with main_agent.run_stream_events(
                user_prompt=user_prompt,
                deps=self._deps,
                model=self._model,
                message_history=message_history,
                usage_limits=UsageLimits(request_limit=200),
                toolsets=[self._toolset],
                model_settings=get_model_settings(self._model_string, ORCHESTRATOR),
            ) as events:
                return await self._consume_agent_events(events, queue)

    async def _consume_agent_events(
        self, events: Any, queue: asyncio.Queue[QueueEvent]
    ) -> tuple[str, Any] | None:
        """Forward reasoning events and return the completed run."""

        reasoning = ""
        async for event in events:
            if isinstance(event, AgentRunResultEvent):
                answer = event.result.output
                if isinstance(answer, str):
                    answer = _strip_think_tags(answer)
                return answer, event.result

            if isinstance(event, FunctionToolCallEvent):
                if thought := _extract_tool_thought(event):
                    reasoning = await self._append_reasoning(queue, reasoning, thought)
                continue

            if isinstance(event, FunctionToolResultEvent):
                reasoning = ""
                continue

            if content := self._get_content_delta(event):
                reasoning = await self._append_reasoning(queue, reasoning, content)

        return None

    async def _append_reasoning(
        self,
        queue: asyncio.Queue[QueueEvent],
        reasoning: str,
        content: str,
    ) -> str:
        """Append content and publish the visible accumulated reasoning."""

        reasoning += content
        if visible_reasoning := _strip_think_tags(reasoning):
            await self._enqueue_reasoning(queue, visible_reasoning)
        return reasoning

    @staticmethod
    def _get_content_delta(event: Any) -> str | None:
        """Extract text or thinking content from a stream event delta."""

        if isinstance(event, PartStartEvent) and isinstance(
            event.part, (TextPart, ThinkingPart)
        ):
            return event.part.content or None
        if isinstance(event, PartDeltaEvent) and isinstance(
            event.delta, (TextPartDelta, ThinkingPartDelta)
        ):
            return event.delta.content_delta or None
        return None

    @staticmethod
    async def _enqueue_reasoning(
        queue: asyncio.Queue[QueueEvent], content: str
    ) -> None:
        """Push an ``AiReasoningChunk`` onto *queue*."""

        await queue.put(
            QueueEvent(
                kind=QueueEventKind.STREAM,
                message=AiReasoningChunk(content=content),
            )
        )

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    async def _monitor_cancellation(self, task: asyncio.Task) -> None:
        """Poll the cache for a cancellation flag and cancel *task* if
        set. Runs as a concurrent task alongside the agent."""

        cache_key = get_assistant_cancellation_key(self._chat.uuid)
        while not task.done():
            await asyncio.sleep(0.2)
            if cache.get(cache_key):
                cache.delete(cache_key)
                self._tool_helpers.cancel()
                task.cancel()
                return

    async def _stream_queue(
        self,
        queue: asyncio.Queue[QueueEvent],
        result: _QueuedRunResult,
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """Yield stream messages while collecting the completed run.

        :param queue: The queue fed by the agent task.
        :param result: The holder the completed answer is collected into.
        :return: An async generator of streamed assistant messages.
        :raises Exception: The error carried by an ERROR queue event.
        """

        while True:
            event = await queue.get()
            if event.kind == QueueEventKind.DONE:
                return
            if event.kind == QueueEventKind.RESULT:
                result.answer = event.answer
                result.messages_json = event.messages_json
            elif event.kind == QueueEventKind.ERROR:
                raise event.error
            else:
                yield event.message

    async def _save_completed_run(
        self,
        human_message: AssistantChatMessage,
        result: _QueuedRunResult,
    ) -> AiMessage | None:
        """Persist and return a completed answer."""

        if result.answer is None:
            return None
        message = await self._save_ai_response(human_message, result.answer)
        if result.messages_json:
            await self._save_message_history(result.messages_json)
        return message

    async def _stop_agent_tasks(
        self, agent_task: asyncio.Task, monitor_task: asyncio.Task
    ) -> None:
        monitor_task.cancel()
        if not agent_task.done():
            agent_task.cancel()
        await asyncio.gather(monitor_task, agent_task, return_exceptions=True)
        self._event_bus.set_queue(None)

    async def _create_title_message(
        self, human_message: AssistantChatMessage
    ) -> ChatTitleMessage | None:
        if self._chat.title:
            return None
        try:
            title = await self._generate_chat_title(human_message.content)
            self._chat.title = title[: AssistantChat.TITLE_MAX_LENGTH]
            await self._chat.asave(update_fields=["title", "updated_on"])
            return ChatTitleMessage(content=self._chat.title)
        except Exception:
            logger.exception("Failed to generate chat title")
            return None

    # ------------------------------------------------------------------
    # Public streaming API
    # ------------------------------------------------------------------

    async def astream_messages(
        self, message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """Stream the full response lifecycle for a user message.

        :param message: The user message, with optional UI context that
            selects the starting agent mode.
        :return: An async generator yielding, in order, ``AiStartedMessage``,
            zero or more streaming chunks (``AiMessageChunk`` /
            ``AiReasoningChunk`` / ``AiThinkingMessage``), and finally an
            ``AiMessage`` with the persisted answer. A ``ChatTitleMessage``
            is appended on the first message in a chat.
        """

        if mode := _mode_for_ui_context(message.ui_context):
            self._deps.mode = mode
        human_msg = await self.acreate_chat_message(
            AssistantChatMessage.Role.HUMAN, message.content
        )
        message_id = str(human_msg.id)
        yield AiStartedMessage(message_id=message_id)

        ui_context = message.ui_context.format() if message.ui_context else None
        self._tool_helpers.request_context["ui_context"] = ui_context
        message_history = await self._load_message_history()

        queue: asyncio.Queue[QueueEvent] = asyncio.Queue()
        self._event_bus.set_queue(queue)

        agent_task = asyncio.create_task(
            self._run_agent(message.content, message_history, queue)
        )
        monitor_task = asyncio.create_task(self._monitor_cancellation(agent_task))
        result = _QueuedRunResult()

        try:
            async for stream_message in self._stream_queue(queue, result):
                yield stream_message

            if agent_task.cancelled():
                raise AssistantMessageCancelled(message_id=message_id)

            if ai_message := await self._save_completed_run(human_msg, result):
                yield ai_message
        finally:
            await self._stop_agent_tasks(agent_task, monitor_task)

        if title_message := await self._create_title_message(human_msg):
            yield title_message
