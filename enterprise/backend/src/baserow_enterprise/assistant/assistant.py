import asyncio
from typing import Any, AsyncGenerator

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
from pydantic_ai.usage import UsageLimits

from baserow.api.sessions import get_client_undo_redo_action_group_id
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
)

_CANCELLATION_KEY_TTL = 300  # seconds
_THINKING_TAGS = ("<think>", "</think>")


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


def _extract_tool_thought(event: FunctionToolCallEvent) -> str | None:
    """Extract the chain-of-thought ``thought`` argument from a tool call
    event, if present and non-empty."""

    try:
        args = event.part.args_as_dict()
    except Exception:
        return None
    thought = args.get("thought")
    return thought if isinstance(thought, str) and thought.strip() else None


class Assistant:
    """Orchestrates a single assistant chat session.

    Wires together the pydantic-ai agent, toolsets, telemetry, event
    streaming, and message persistence for one ``AssistantChat``.
    """

    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace
        self._model_string = get_model_string()
        self._model = RetryingModel(self._model_string)
        self._event_bus = EventBus()
        self._tool_helpers = self._build_tool_helpers()
        self._telemetry = PosthogTracingCallback()

        self._deps = AssistantDeps(
            user=self._user,
            workspace=self._workspace,
            tool_helpers=self._tool_helpers,
        )
        self._toolset, db_m, app_m, auto_m, explain_m = (
            assistant_tool_registry.build_toolset(
                user=self._user,
                workspace=self._workspace,
                model=self._model_string,
                deps=self._deps,
            )
        )
        self._deps.database_manifest = db_m
        self._deps.application_manifest = app_m
        self._deps.automation_manifest = auto_m
        self._deps.explain_manifest = explain_m

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
        """Deserialise and compact the stored message history, returning
        ``None`` if absent or corrupt."""

        raw = self._chat.message_history
        if not raw:
            return None
        try:
            messages = ModelMessagesTypeAdapter.validate_json(bytes(raw))
            return compact_message_history(messages)
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

    _MAX_TOOL_CALL_AS_TEXT_RETRIES = 2

    _TOOL_CALL_CORRECTION_PROMPT = (
        "Your previous response contained a raw JSON tool call instead of "
        "actually invoking the tool. The malformed output was:\n\n"
        "{malformed_output}\n\n"
        "Please call the tool directly using the proper tool-calling "
        "mechanism instead of outputting JSON text. Make sure the "
        "arguments conform to the tool's schema."
    )

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
        """Execute the main agent, retrying if it outputs tool calls as text.

        Delegates each streaming pass to ``_stream_agent_run``.  If the
        final output looks like a raw JSON tool call, re-runs the agent
        with the conversation history and a corrective prompt (up to
        ``_MAX_TOOL_CALL_AS_TEXT_RETRIES`` times) so the model can
        self-correct and invoke the tool properly.

        Pushes ``STREAM``, ``RESULT``, ``ERROR``, and ``DONE`` events
        onto *queue* for the consumer in ``astream_messages``.
        """

        try:
            with self._telemetry.trace(self._chat, user_prompt) as tracer:
                answer, run_result = await self._run_agent_with_retries(
                    user_prompt, message_history, queue
                )
                tracer.set_trace_output(answer)
                await self._emit_answer(answer, run_result, queue)
        except Exception as exc:
            logger.exception("Error running main agent")
            queue.put_nowait(QueueEvent(kind=QueueEventKind.ERROR, error=exc))
        finally:
            queue.put_nowait(QueueEvent(kind=QueueEventKind.DONE))

    async def _run_agent_with_retries(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> tuple[str, Any]:
        """Stream the agent, retrying on tool-call-as-text outputs.

        Returns ``(answer, run_result)`` — either the model's valid
        answer or a fallback message after exhausting retries.

        :raises RuntimeError: if the stream ends without a result event.
        """

        current_prompt = user_prompt
        current_history = message_history

        for attempt in range(1 + self._MAX_TOOL_CALL_AS_TEXT_RETRIES):
            result = await self._stream_agent_run(
                current_prompt, current_history, queue
            )
            if result is None:
                raise RuntimeError("Agent stream ended without a result event")

            answer, run_result = result

            if not self._looks_like_json_tool_call(answer):
                return answer, run_result

            logger.warning(
                "[assistant] Model output tool call as text (attempt {}/{}): {}",
                attempt + 1,
                1 + self._MAX_TOOL_CALL_AS_TEXT_RETRIES,
                answer[:200],
            )

            if attempt < self._MAX_TOOL_CALL_AS_TEXT_RETRIES:
                # Replace the malformed JSON visible in the UI with a
                # reasoning indicator so the user doesn't see garbage.
                await queue.put(
                    QueueEvent(
                        kind=QueueEventKind.STREAM,
                        message=AiReasoningChunk(content=""),
                    )
                )
                current_history = run_result.all_messages()
                current_prompt = self._TOOL_CALL_CORRECTION_PROMPT.format(
                    malformed_output=answer[:500]
                )

        # Exhausted retries — give up gracefully.
        logger.error(
            "[assistant] Model persisted outputting tool "
            "calls as text after {} retries",
            self._MAX_TOOL_CALL_AS_TEXT_RETRIES,
        )
        fallback = (
            "I ran into a temporary issue processing "
            "your request. Could you please try again?"
        )
        return fallback, run_result

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
        """

        reasoning_so_far = ""

        async for event in main_agent.run_stream_events(
            user_prompt=user_prompt,
            deps=self._deps,
            model=self._model,
            message_history=message_history,
            usage_limits=UsageLimits(request_limit=200),
            toolsets=[self._toolset],
            model_settings=get_model_settings(self._model_string, ORCHESTRATOR),
        ):
            if isinstance(event, AgentRunResultEvent):
                answer = event.result.output
                if isinstance(answer, str):
                    answer = _strip_think_tags(answer)
                return (answer, event.result)

            if isinstance(event, FunctionToolCallEvent):
                thought = _extract_tool_thought(event)
                if thought:
                    reasoning_so_far += thought
                    cleaned = _strip_think_tags(reasoning_so_far)
                    await self._enqueue_reasoning(queue, cleaned)
                continue

            if isinstance(event, FunctionToolResultEvent):
                reasoning_so_far = ""  # reset on tool results, to show the reasoning leading up to the next tool call
                continue

            # Accumulate text/thinking deltas and send full reasoning.
            # The frontend replaces content on each chunk, so we must
            # send the complete text every time.
            content = self._get_content_delta(event)
            if content:
                reasoning_so_far += content
                cleaned = _strip_think_tags(reasoning_so_far)
                if cleaned:
                    await self._enqueue_reasoning(queue, cleaned)

        return None

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

    @staticmethod
    def _looks_like_json_tool_call(text: str) -> bool:
        """Return True if *text* looks like a tool call dumped as JSON.

        Checks for ``{"name": ..., "arguments": ...}`` pattern in the first
        200 chars. Does not require valid JSON (the output may be truncated).
        """

        stripped = text.strip()
        return (
            bool(stripped)
            and stripped[0] == "{"
            and '"name"' in stripped[:200]
            and '"arguments"' in stripped[:200]
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

    # ------------------------------------------------------------------
    # Public streaming API
    # ------------------------------------------------------------------

    async def astream_messages(
        self, message: HumanMessage
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """Stream the full response lifecycle for a user message.

        Yields events in order: ``AiStartedMessage``, zero or more
        streaming chunks (``AiMessageChunk`` / ``AiReasoningChunk`` /
        ``AiThinkingMessage``), and finally an ``AiMessage`` with the
        persisted answer. A ``ChatTitleMessage`` is appended on the first
        message in a chat.
        """

        # Sticky task: capture on first message of the session
        if not self._deps.original_request:
            self._deps.original_request = message.content

            # Auto-detect starting mode from UI context (only on first message)
            if message.ui_context:
                if message.ui_context.application or message.ui_context.page:
                    self._deps.mode = AgentMode.APPLICATION
                elif message.ui_context.automation or message.ui_context.workflow:
                    self._deps.mode = AgentMode.AUTOMATION
                # else stays DATABASE (default)

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

        try:
            answer = None
            messages_json = None

            while True:
                event = await queue.get()
                if event.kind == QueueEventKind.DONE:
                    break
                elif event.kind == QueueEventKind.RESULT:
                    answer, messages_json = event.answer, event.messages_json
                elif event.kind == QueueEventKind.ERROR:
                    raise event.error
                else:
                    yield event.message

            if agent_task.cancelled():
                raise AssistantMessageCancelled(message_id=message_id)

            if answer is not None:
                yield await self._save_ai_response(human_msg, answer)
                if messages_json:
                    await self._save_message_history(messages_json)
        finally:
            monitor_task.cancel()
            if not agent_task.done():
                agent_task.cancel()
            await asyncio.gather(monitor_task, agent_task, return_exceptions=True)
            self._event_bus.set_queue(None)

        if not self._chat.title:
            try:
                title = await self._generate_chat_title(human_msg.content)
                self._chat.title = title[: AssistantChat.TITLE_MAX_LENGTH]
                await self._chat.asave(update_fields=["title", "updated_on"])
                yield ChatTitleMessage(content=self._chat.title)
            except Exception:
                logger.exception("Failed to generate chat title")
