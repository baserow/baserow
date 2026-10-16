import asyncio
import time
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.utils import translation

from loguru import logger
from pydantic_ai import Agent, UnexpectedModelBehavior, capture_run_messages
from pydantic_ai._thinking_part import split_content_into_text_and_thinking
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.tool_manager import ToolManager
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from baserow.api.sessions import get_client_undo_redo_action_group_id
from baserow.core.chat_runs.constants import (
    ERROR_FAILED,
    ERROR_INTERRUPTED,
    ERROR_TIMEOUT,
    PROGRESS,
    STOP_CANCELLED,
    STOP_LOST,
    STOP_TIMEOUT,
)
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.tool_executor import ShieldedToolset, ToolExecutor
from baserow.core.chat_runs.types import ChatRunOutcome
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
    bind_tool_helpers,
)
from baserow_enterprise.assistant.exceptions import AssistantMessageCancelled
from baserow_enterprise.assistant.history import (
    UNFINISHED_ANSWER,
    append_turn,
    compact_message_history,
    count_user_prompts,
    unfinished_answer,
)
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    TITLE,
    ResolvedAssistantModelProfile,
    resolve_assistant_model,
)
from baserow_enterprise.assistant.runs import (
    CHAT_TITLE_EVENT,
    NAVIGATION_EVENT,
    AssistantRunResult,
)
from baserow_enterprise.assistant.telemetry import (
    PosthogTracingCallback,
    setup_instrumentation,
)
from baserow_enterprise.assistant.tools.navigation.utils import (
    NAVIGATED,
    unsafe_navigate_to,
)
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
    AnyNavigationType,
    AssistantMessageUnion,
    ChatTitleMessage,
    HumanMessage,
    UIContext,
)

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal

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
    except Exception as exc:
        logger.warning(
            "Could not determine assistant license for workspace {} ({})",
            workspace.id,
            type(exc).__name__,
        )
        return None


@dataclass
class AgentRunContext:
    deps: AssistantDeps
    toolset: AbstractToolset
    model: Model


def build_agent_run_context(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: ToolHelpers,
    model: Model | None = None,
) -> AgentRunContext:
    """Build shared assistant and eval dependencies from one model profile.

    :param user: The user running the assistant.
    :param workspace: The workspace in which tools execute.
    :param tool_helpers: Callbacks and the resolved model profile for this run.
    :param model: An existing model, or None to create one from the profile.
    :return: Dependencies, manifests, toolset, and the concrete model for the run.
    """

    model_profile = tool_helpers.model_profile
    resolved_model = model if model is not None else model_profile.create_model()
    deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
        license_tier=_get_workspace_license_type(user, workspace),
    )
    toolset, deps.tool_catalog = assistant_tool_registry.build_toolset(
        user=user,
        workspace=workspace,
        model=resolved_model,
        model_profile=model_profile,
        deps=deps,
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


def to_assistant_message(message: AssistantChatMessage) -> HumanMessage | AiMessage:
    """
    Projects a saved chat message to the message the chat shows.

    :param message: The saved message, with `prediction` selected for AI messages.
    :return: The human or AI message.
    """

    if message.role == AssistantChatMessage.Role.HUMAN:
        return HumanMessage(
            content=message.content, id=message.id, timestamp=message.created_on
        )

    sentiment_data = {}
    if getattr(message, "prediction", None):
        sentiment_data = {
            "can_submit_feedback": True,
            "human_sentiment": message.prediction.get_human_sentiment_display(),
        }
    run_state = message.artifacts.get("run") or {}
    return AiMessage(
        content=message.content,
        id=message.id,
        timestamp=message.created_on,
        sources=message.artifacts.get("sources"),
        run_status=run_state.get("status"),
        error_code=run_state.get("error_code"),
        onboarding_target=message.artifacts.get("onboarding_target"),
        **sentiment_data,
    )


def assistant_message_payload(message: AssistantChatMessage) -> dict[str, Any]:
    """
    Projects a saved chat message to the JSON the chat run events carry, the same
    shape the chat messages API returns.

    :param message: The saved message, with `prediction` selected for AI messages.
    :return: The message as a JSON-serializable dict.
    """

    payload = to_assistant_message(message).model_dump(
        mode="json", exclude={"ui_context"}
    )
    if payload.get("onboarding_target") is None:
        payload.pop("onboarding_target", None)
    return payload


class Assistant:
    """Orchestrates a single assistant chat session.

    Wires together the pydantic-ai agent, toolsets, telemetry, event
    streaming, and message persistence for one ``AssistantChat``.
    """

    def __init__(
        self,
        chat: AssistantChat,
        model_profile: ResolvedAssistantModelProfile | None = None,
    ):
        """Initialize an assistant from one resolved model snapshot.

        :param chat: The persisted chat this assistant will serve.
        :param model_profile: The model profile already resolved for the request.
        :return: None.
        """

        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace
        self._model_profile = model_profile or resolve_assistant_model(
            workspace=self._workspace
        )
        self._model = self._model_profile.create_model()
        self._event_bus = EventBus()
        self._agent_messages: list[ModelMessage] = []
        self._tool_helpers = self._build_tool_helpers()
        self._telemetry = PosthogTracingCallback()

        ctx = build_agent_run_context(
            self._user, self._workspace, self._tool_helpers, model=self._model
        )
        self._deps = ctx.deps
        self._toolset = ctx.toolset

        setup_instrumentation()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_tool_helpers(self) -> ToolHelpers:
        """Create the helpers shared by every tool in this assistant run.

        :return: Helpers carrying the request's callbacks and resolved model profile.
        """

        def update_status(status: str) -> None:
            """Emit a localized assistant status update.

            :param status: The translated status template to emit.
            :return: None.
            """

            with translation.override(self._user.profile.language):
                self._event_bus.emit(AiThinkingMessage(content=status))

        return ToolHelpers(
            update_status=update_status,
            navigate_to=lambda loc: unsafe_navigate_to(loc, self._event_bus),
            model_profile=self._model_profile,
            event_bus=self._event_bus,
        )

    def _cancelled_by_user(self) -> bool:
        """
        :return: Whether the user asked to stop, which the trace tells apart from
            an answer that was cut off.
        """

        return self._tool_helpers.is_cancelled

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
        """Return this chat's recent persisted messages, oldest-first.

        :param last_message_id: An exclusive message-ID pagination cursor.
        :param limit: The maximum number of messages to return.
        :return: The projected assistant messages in chronological order.
        """

        return self.list_chat_messages_for_chat(
            self._chat, last_message_id=last_message_id, limit=limit
        )

    @staticmethod
    def list_chat_messages_for_chat(
        chat: AssistantChat,
        last_message_id: int | None = None,
        limit: int = 100,
    ) -> list[AssistantMessageUnion]:
        """Return recent chat messages, oldest-first.

        This projection deliberately does not construct an ``Assistant`` or an
        AI model, so loading chat history never allocates a provider client.

        :param chat: The chat whose persisted messages should be projected.
        :param last_message_id: If set, only return messages with ``id``
            below this value (cursor-based pagination).
        :param limit: Maximum number of messages to return.
        :return: The projected assistant messages in chronological order.
        """

        queryset = (
            chat.messages.all().select_related("prediction").order_by("-created_on")
        )
        if last_message_id is not None:
            queryset = queryset.filter(id__lt=last_message_id)

        messages = [to_assistant_message(message) for message in queryset[:limit]]
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
            prediction={
                "answer": answer,
                "posthog_trace_id": self._telemetry.trace_id,
            },
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
        except Exception as exc:
            logger.warning(
                "Could not load history for chat {}, starting fresh ({})",
                self._chat.pk,
                type(exc).__name__,
            )
            return None

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def _generate_chat_title(self, user_message: str) -> str:
        """Ask the title agent to summarize a user message into a short title.

        :param user_message: The user message to summarize.
        :return: The generated chat title.
        """

        result = await title_agent.run(
            user_message,
            model=self._model,
            model_settings=self._model_profile.get_settings(TITLE),
        )
        return result.output

    async def _emit_answer(
        self,
        answer: str,
        messages_json: bytes,
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
                messages_json=messages_json,
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
            with capture_run_messages() as run_messages:
                self._agent_messages = run_messages
                try:
                    with self._telemetry.trace(
                        self._chat,
                        user_prompt,
                        cancelled_by_user=self._cancelled_by_user,
                    ) as tracer:
                        result = await self._stream_agent_run(
                            user_prompt, message_history, queue
                        )
                        if result is None:
                            raise RuntimeError(
                                "Agent stream ended without a result event"
                            )
                        answer, run_result = result
                        tracer.set_trace_output(answer)
                        await self._emit_answer(
                            answer, run_result.all_messages_json(), queue
                        )
                except UnexpectedModelBehavior as exc:
                    # Tools may have changed data, so keep the turn instead of failing it.
                    logger.warning(
                        "Main agent ended without an accepted answer for chat {} ({})",
                        self._chat.id,
                        type(exc).__name__,
                    )
                    history = [
                        *run_messages,
                        ModelResponse(parts=[TextPart(content=UNFINISHED_ANSWER)]),
                    ]
                    await self._emit_answer(
                        UNFINISHED_ANSWER,
                        ModelMessagesTypeAdapter.dump_json(history),
                        queue,
                    )
        except Exception as exc:
            # Provider errors and diagnostic tracebacks can contain private inputs.
            logger.warning(
                "Main agent failed for chat {} ({})",
                self._chat.id,
                type(exc).__name__,
            )
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

        Streams reasoning/text chunks to *queue* and returns
        ``(answer, run_result)`` when an ``AgentRunResultEvent`` is
        received, or ``None`` if the stream ends without one.

        :param user_prompt: The prompt for this agent pass.
        :param message_history: The compacted prior model messages, if any.
        :param queue: The queue that receives streamed assistant events.
        :return: The final answer and run result, or ``None`` if no result arrives.
        """

        with ToolManager.parallel_execution_mode("sequential"):
            async with main_agent.run_stream_events(
                user_prompt=user_prompt,
                deps=self._deps,
                model=self._model,
                message_history=message_history,
                usage_limits=UsageLimits(request_limit=200),
                toolsets=[self._toolset],
                model_settings=self._model_profile.get_settings(ORCHESTRATOR),
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

            # A rejected text answer emits no event, so the next response resets it.
            if isinstance(event, PartStartEvent) and event.index == 0 and reasoning:
                reasoning = ""
                await self._enqueue_reasoning(queue, "")

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
        except Exception as exc:
            logger.warning(
                "Could not generate title for chat {} ({})",
                self._chat.id,
                type(exc).__name__,
            )
            return None

    # ------------------------------------------------------------------
    # Public streaming API
    # ------------------------------------------------------------------

    async def astream_messages(
        self, message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """Stream one assistant run and close its provider-owned client.

        :param message: The new human message and its UI context.
        :yield: Assistant events in response order.
        """

        async with self._model:
            async with aclosing(
                self._astream_messages_in_model_context(message)
            ) as events:
                async for event in events:
                    yield event

    async def _astream_messages_in_model_context(
        self, message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """Stream the full response lifecycle for a user message.

        Yields events in order: ``AiStartedMessage``, zero or more
        streaming chunks (``AiMessageChunk`` / ``AiReasoningChunk`` /
        ``AiThinkingMessage``), and finally an ``AiMessage`` with the
        persisted answer. A ``ChatTitleMessage`` is appended on the first
        message in a chat.

        :param message: The new human message and its UI context.
        :yield: Assistant events in response order.
        :return: An async generator of assistant events in response order.
        :raises Exception: If the agent reports an execution error.
        :raises AssistantMessageCancelled: If the assistant run is cancelled.
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


_STOPPED_RUN_OUTCOMES = {
    STOP_CANCELLED: (ChatRunStatus.CANCELLED, ""),
    STOP_TIMEOUT: (ChatRunStatus.FAILED, ERROR_TIMEOUT),
    STOP_LOST: (ChatRunStatus.FAILED, ERROR_INTERRUPTED),
}


class BackgroundAssistant(Assistant):
    """
    Answers the message of one chat run. It reports to the run's journal instead
    of streaming, and saves nothing: the run type saves the outcome it returns.
    """

    def __init__(
        self,
        chat: AssistantChat,
        model_profile: ResolvedAssistantModelProfile,
        journal: "ChatRunJournal",
        origin_tab_id: str,
    ) -> None:
        """
        :param chat: The chat of the run.
        :param model_profile: The model profile resolved for the run.
        :param journal: The run's journal.
        :param origin_tab_id: The tab that sent the message, the only one that
            follows Kuma's navigation.
        """

        self._journal = journal
        self._origin_tab_id = origin_tab_id
        self._latest_text = ""
        self._loaded_history: list[ModelMessage] = []
        self._answer: str | None = None
        self._answer_history = b""
        self._title: str | None = None
        self._onboarding_target: dict | None = None
        self._tool_executor = ToolExecutor()
        super().__init__(chat, model_profile=model_profile)
        self._toolset = ShieldedToolset(self._toolset, self._tool_executor)

    def _build_tool_helpers(self) -> ToolHelpers:
        """
        :return: Helpers that report to the journal, which tool threads may call.
        """

        return ToolHelpers(
            update_status=self._report_progress,
            navigate_to=self._report_navigation,
            model_profile=self._model_profile,
        )

    def _cancelled_by_user(self) -> bool:
        """
        :return: Whether the run stops because the user pressed Stop, not because
            of its deadline or a lost lease.
        """

        return self._journal.stop_reason == STOP_CANCELLED

    async def _stream_agent_run(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> tuple[str, Any] | None:
        """
        Runs the agent pass with the run's tool helpers bound, so no model call of
        the pass starts once the run is cancelled, and with its sync tools in the
        run's tracked executor, so a stop can wait for them.

        :param user_prompt: The prompt for this agent pass.
        :param message_history: The compacted prior model messages, if any.
        :param queue: The queue that receives streamed assistant events.
        :return: The final answer and run result, or ``None`` if no result arrives.
        """

        with (
            bind_tool_helpers(self._tool_helpers),
            Agent.using_thread_executor(self._tool_executor),
        ):
            return await super()._stream_agent_run(user_prompt, message_history, queue)

    async def answer(
        self, prompt: str, ui_context: UIContext | None, generate_title: bool
    ) -> ChatRunOutcome:
        """
        Answers the prompt until it is done or the journal asks the run to stop.
        It returns only once every tool call it started has ended.

        :param prompt: The human message the run answers.
        :param ui_context: What the user was looking at when sending it.
        :param generate_title: Whether to replace the chat's provisional title.
        :return: How the run ended, with an `AssistantRunResult`.
        """

        work = asyncio.create_task(self._produce(prompt, ui_context, generate_title))
        stop = asyncio.create_task(self._journal.wait_for_stop())
        try:
            await asyncio.wait({work, stop}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stop.cancel()
            await asyncio.gather(stop, return_exceptions=True)

        if work.done():
            await self._tool_executor.drain()
        else:
            await self._wind_down(work)
        if not work.cancelled() and work.exception() is not None:
            logger.warning(
                "Kuma could not answer in chat {} ({})",
                self._chat.id,
                type(work.exception()).__name__,
            )
        return self._outcome(prompt)

    async def _wind_down(self, work: asyncio.Task) -> None:
        """
        Stops the agent: tools see the cancel flag and the agent task is
        cancelled. Then it waits for every tool call the agent started, with no
        time limit, so the run never reports that it stopped while a tool can
        still write. The worker's hard time limit is the backstop.

        :param work: The task producing the answer.
        """

        self._tool_helpers.cancel()
        work.cancel()
        stop_started = time.monotonic()
        await self._tool_executor.drain()
        await asyncio.gather(work, return_exceptions=True)
        logger.info(
            "The tools of chat run {} stopped {:.2f}s after the run was asked to stop",
            self._journal.run.id,
            time.monotonic() - stop_started,
        )

    async def _produce(
        self, prompt: str, ui_context: UIContext | None, generate_title: bool
    ) -> None:
        """
        Streams the answer, then the chat title, inside the model's client scope.

        :param prompt: The human message.
        :param ui_context: What the user was looking at.
        :param generate_title: Whether to generate the chat's title.
        """

        async with self._model:
            await self._stream_answer(prompt, ui_context)
            if generate_title:
                await self._report_title(prompt)

    async def _stream_answer(self, prompt: str, ui_context: UIContext | None) -> None:
        """
        Runs the main agent and reports its text as it streams.

        :param prompt: The human message.
        :param ui_context: What the user was looking at.
        """

        if mode := _mode_for_ui_context(ui_context):
            self._deps.mode = mode
        self._tool_helpers.request_context["ui_context"] = (
            ui_context.format() if ui_context else None
        )
        self._loaded_history = await self._load_message_history() or []

        queue: asyncio.Queue[QueueEvent] = asyncio.Queue()
        agent_task = asyncio.create_task(
            self._run_agent(prompt, self._loaded_history or None, queue)
        )
        result = _QueuedRunResult()
        try:
            async for message in self._stream_queue(queue, result):
                self._report_message(message)
        finally:
            agent_task.cancel()
            await asyncio.gather(agent_task, return_exceptions=True)
        self._answer = result.answer
        self._answer_history = result.messages_json

    def _report_message(self, message: AssistantMessageUnion) -> None:
        """
        Reports the agent's cumulative text; the journal saves only what changed.

        :param message: A message the agent streamed.
        """

        if isinstance(message, (AiReasoningChunk, AiMessageChunk)):
            self._latest_text = message.content
            self._journal.emit_text(message.content, variant=message.type)

    def _report_progress(self, progress: str) -> None:
        """
        Reports what a tool is doing. Safe to call from tool threads.

        :param progress: What the tool is doing, translated.
        """

        # str() resolves a lazy translation here, where the run's language is active.
        self._journal.emit(PROGRESS, {"text": str(progress)})

    def _report_navigation(self, location: AnyNavigationType) -> str:
        """
        Asks the sending tab to open a location, unless the run is stopping: a
        tool that ends after Stop must not move the user. Safe to call from tool
        threads.

        :param location: Where to navigate.
        :return: The confirmation the navigation tool gives the model.
        """

        if not self._tool_helpers.is_cancelled:
            if self._onboarding_target is None and location.type == "database-table":
                self._onboarding_target = location.model_dump(mode="json")
            self._journal.emit(
                NAVIGATION_EVENT,
                {
                    "location": location.model_dump(mode="json"),
                    "origin_tab_id": self._origin_tab_id,
                },
                flush_now=True,
            )
        return NAVIGATED

    async def _report_title(self, prompt: str) -> None:
        """
        Generates the chat's title and reports it. On failure the provisional
        title stays.

        :param prompt: The chat's first message.
        """

        try:
            title = await self._generate_chat_title(prompt)
        except Exception as exc:
            logger.warning(
                "Could not generate title for chat {} ({})",
                self._chat.id,
                type(exc).__name__,
            )
            return
        self._title = title[: AssistantChat.TITLE_MAX_LENGTH]
        self._journal.emit(CHAT_TITLE_EVENT, {"title": self._title}, flush_now=True)

    def _outcome(self, prompt: str) -> ChatRunOutcome:
        """
        :param prompt: The human message.
        :return: Completed when the agent answered, even if a stop came later;
            otherwise how the run stopped, with what the user saw.
        """

        if self._answer is not None:
            return ChatRunOutcome(
                status=ChatRunStatus.COMPLETED,
                result=self._result(self._answer, self._answer_history),
            )
        status, error_code = _STOPPED_RUN_OUTCOMES.get(
            self._journal.stop_reason, (ChatRunStatus.FAILED, ERROR_FAILED)
        )
        return ChatRunOutcome(
            status=status,
            error_code=error_code,
            result=self._result(self._latest_text, self._unfinished_history(prompt)),
        )

    def _unfinished_history(self, prompt: str) -> bytes:
        """
        Keeps the agent's own messages when the prompt reached the model, closed
        with a text answer so the next message is never rejected for an unanswered
        tool call. Otherwise records the prompt with a note that nothing was done.

        :param prompt: The human message.
        :return: The chat's new history, serialized.
        """

        if count_user_prompts(self._agent_messages) > count_user_prompts(
            self._loaded_history
        ):
            closing = ModelResponse(
                parts=[TextPart(content=unfinished_answer(self._latest_text))]
            )
            return ModelMessagesTypeAdapter.dump_json([*self._agent_messages, closing])
        return append_turn(self._chat.message_history, prompt, unfinished_answer(""))

    def _result(self, text: str, message_history: bytes) -> AssistantRunResult:
        """
        :param text: The answer, or what the user saw of it.
        :param message_history: The chat's new history, serialized.
        :return: What the run type saves.
        """

        return AssistantRunResult(
            text=text,
            message_history=message_history,
            sources=list(self._deps.sources),
            trace_id=self._telemetry.trace_id,
            title=self._title,
            onboarding_target=self._onboarding_target,
        )
