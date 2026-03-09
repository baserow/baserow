import asyncio
from typing import Any, AsyncGenerator

from django.core.cache import cache
from django.utils import translation

from loguru import logger
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
)
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

    _JSON_TOOL_CALL_MAX_RETRIES = 3

    async def _run_agent(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> None:
        """Execute the main agent and push streaming events onto *queue*.

        On success a ``RESULT`` event carries the final answer and
        serialised message history. On failure an ``ERROR`` event carries
        the exception. A ``DONE`` sentinel is always sent last.
        """

        try:
            with self._telemetry.trace(self._chat, user_prompt) as tracer:
                answer, messages_json = await self._run_agent_with_json_retry(
                    user_prompt, message_history, queue
                )
                tracer.set_trace_output(answer)
                queue.put_nowait(
                    QueueEvent(
                        kind=QueueEventKind.RESULT,
                        answer=answer,
                        messages_json=messages_json,
                    )
                )
        except Exception as exc:
            logger.exception("Error running main agent")
            queue.put_nowait(QueueEvent(kind=QueueEventKind.ERROR, error=exc))
        finally:
            queue.put_nowait(QueueEvent(kind=QueueEventKind.DONE))

    async def _run_agent_with_json_retry(
        self,
        user_prompt: str,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
    ) -> tuple[str, bytes]:
        """Run the agent, retrying if the model outputs a tool call as text.

        Some providers occasionally return tool calls in the text/content
        field instead of the structured tool_calls field. When detected,
        we re-run the agent with the accumulated message history so the
        model can make the proper tool call.
        """

        for attempt in range(self._JSON_TOOL_CALL_MAX_RETRIES):
            async with main_agent.run_stream(
                user_prompt=user_prompt,
                deps=self._deps,
                model=self._model,
                message_history=message_history,
                usage_limits=UsageLimits(request_limit=200),
                toolsets=[self._toolset],
                model_settings=get_model_settings(self._model_string, ORCHESTRATOR),
                event_stream_handler=lambda ctx, events: self._relay_tool_events(
                    events, queue
                ),
            ) as result:
                answer = await self._stream_answer(result, queue)
                if not self._looks_like_json_tool_call(answer):
                    return answer, result.all_messages_json()

                # The model dumped a tool call as text — retry with the
                # conversation so far plus a correction prompt.
                logger.warning(
                    "[assistant] Model output tool call as text (attempt {}/{}), "
                    "retrying: {}",
                    attempt + 1,
                    self._JSON_TOOL_CALL_MAX_RETRIES,
                    answer[:200],
                )
                message_history = result.all_messages()
                user_prompt = (
                    "You returned a tool call as text instead of calling the "
                    "tool. Please call the tool directly with valid JSON. ",
                    "Here's your last incorrect output:\n\n" + answer,
                )

        # Exhausted retries — return fallback
        answer = (
            "I ran into a temporary issue processing your request. "
            "Could you please try again?"
        )
        await queue.put(
            QueueEvent(
                kind=QueueEventKind.STREAM,
                message=AiMessageChunk(content=answer, sources=self._deps.sources),
            )
        )
        return answer, result.all_messages_json()

    @staticmethod
    async def _relay_tool_events(events, queue: asyncio.Queue[QueueEvent]) -> None:
        """Forward chain-of-thought ``thought`` arguments from tool calls
        to the stream as reasoning chunks."""

        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                thought = _extract_tool_thought(event)
                if thought:
                    await queue.put(
                        QueueEvent(
                            kind=QueueEventKind.STREAM,
                            message=AiReasoningChunk(content=thought),
                        )
                    )

    async def _stream_answer(self, result, queue: asyncio.Queue[QueueEvent]) -> str:
        """Stream the agent's text output as ``AiMessageChunk`` events and
        return the final accumulated answer.

        Buffers output that starts with ``{`` or ``[`` to avoid streaming
        raw JSON to the user. If the entire output looks like a JSON tool
        call, it is returned un-streamed so the caller can decide to retry.
        """

        answer = ""
        # True while we suspect the output might be raw JSON; once the first
        # non-whitespace character is not ``{``/``[`` we flush and stop.
        json_buffering = True

        async for full_text in result.stream_text():
            answer = full_text

            if json_buffering:
                stripped = full_text.strip()
                if not stripped:
                    continue  # still empty, keep buffering
                if stripped[0] in "{[":
                    continue  # looks like JSON, keep buffering
                # First real char is not JSON — flush the buffer and stream
                json_buffering = False

            await queue.put(
                QueueEvent(
                    kind=QueueEventKind.STREAM,
                    message=AiMessageChunk(
                        content=full_text, sources=self._deps.sources
                    ),
                )
            )

        return answer

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
            title = await self._generate_chat_title(human_msg.content)
            self._chat.title = title[: AssistantChat.TITLE_MAX_LENGTH]
            await self._chat.asave(update_fields=["title", "updated_on"])
            yield ChatTitleMessage(content=title)
