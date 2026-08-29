import asyncio
import json
import re
import time
from typing import Any

from django.core.cache import cache

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.usage import UsageLimits

from baserow_enterprise.assistant.agents import title_agent
from baserow_enterprise.assistant.assistant import _strip_think_tags
from baserow_enterprise.assistant.history import compact_message_history

from .agents import agent_run_agent
from .ai_models import AgentModelProfile, resolve_agent_model
from .chat_types import (
    AiAnswerChunk,
    AiCancelledMessage,
    AiErrorMessage,
    AiMessageChunk,
    AiReasoningChunk,
    AiStartedMessage,
    AiThinkingMessage,
    ApprovalRequestMessage,
    ChatTitleMessage,
    ToolCallMessage,
    ToolResultMessage,
)
from .deps import AgentRunDeps, EventBus, QueueEvent, QueueEventKind, ToolHelpers
from .exceptions import AgentChatRunCancelled
from .models import AgentChat, AgentChatMessage
from .realtime import broadcast_chat_event, broadcast_chat_updated

_CANCELLATION_KEY_TTL = 300  # seconds
_TOOL_RESULT_CONTENT_LIMIT = 4000
# Approvals are decided based on the exact arguments, so they keep far more
# of the payload than the streaming chips do.
_APPROVAL_ARGS_CONTENT_LIMIT = 50000
_REQUEST_LIMIT = 100
# Streaming text is broadcast often for a live typing feel, but persisted at a
# slower pace because every flush is an UPDATE on the message row.
_BROADCAST_INTERVAL = 0.2  # seconds between reasoning broadcasts
_FLUSH_INTERVAL = 1.0  # seconds between database writes


def get_agent_chat_cancellation_key(chat_uuid) -> str:
    return f"agent_application:chat:{chat_uuid}:cancelled"


def set_agent_chat_cancellation_key(
    chat_uuid, timeout: int = _CANCELLATION_KEY_TTL
) -> None:
    cache.set(get_agent_chat_cancellation_key(chat_uuid), True, timeout=timeout)


_THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _split_think_content(text: str) -> tuple[str, str]:
    """
    Splits streamed text into (thinking, answer): the content of any
    ``<think>`` blocks — including a trailing unclosed one while it is still
    streaming — versus everything else.
    """

    if "<think>" not in text:
        return "", text

    thinking_parts = [match.group(1) for match in _THINK_BLOCK_RE.finditer(text)]
    remainder = _THINK_BLOCK_RE.sub("", text)

    last_open = remainder.rfind("<think>")
    if last_open != -1:
        thinking_parts.append(remainder[last_open + len("<think>") :])
        remainder = remainder[:last_open]

    return "\n".join(part.strip() for part in thinking_parts if part.strip()), remainder


def _get_typed_content_delta(event: Any) -> tuple[str | None, bool]:
    """
    Extracts a streamed content delta and whether it is thinking content
    (reasoning models) or plain answer text.
    """

    if isinstance(event, PartStartEvent):
        if isinstance(event.part, ThinkingPart):
            return event.part.content or None, True
        if isinstance(event.part, TextPart):
            return event.part.content or None, False
    if isinstance(event, PartDeltaEvent):
        if isinstance(event.delta, ThinkingPartDelta):
            return event.delta.content_delta or None, True
        if isinstance(event.delta, TextPartDelta):
            return event.delta.content_delta or None, False
    return None, False


def _is_unsupported_native_tool_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "web_search" in text and ("not supported" in text or "unsupported" in text)


def _jsonable(content: Any, limit: int = _TOOL_RESULT_CONTENT_LIMIT) -> Any:
    """
    Tool results can contain anything; the persisted artifacts and the
    websocket payload must stay JSON serializable and reasonably small.
    """

    try:
        serialized = json.dumps(content, default=str)
    except (TypeError, ValueError):
        serialized = json.dumps(str(content))

    if len(serialized) > limit:
        return serialized[:limit] + "… (truncated)"

    return json.loads(serialized)


class AgentRunner:
    """
    Executes a single turn of an agent chat inside a celery task. Events are
    persisted incrementally on the AI message so history is complete without
    any watcher, and broadcast to the application's websocket page group so
    open browsers stream the run live.
    """

    def __init__(self, chat: AgentChat):
        self.chat = chat
        self.agent = chat.agent
        self.application = self.agent.application
        self.workspace = self.application.workspace
        self.actor = self.application.agent_identity or chat.user
        self.model, self.model_settings = resolve_agent_model(self.agent)

        self._event_bus = EventBus()
        self._tool_helpers = ToolHelpers(
            update_status=lambda status: self._event_bus.emit(
                AiThinkingMessage(content=status)
            ),
            navigate_to=lambda location: "",
            model_profile=AgentModelProfile(self.model, self.model_settings),
        )
        self._tool_helpers.event_bus = self._event_bus
        self.deps = AgentRunDeps(
            user=self.actor,
            workspace=self.workspace,
            agent=self.agent,
            chat=chat,
            tool_helpers=self._tool_helpers,
        )
        self._toolsets = self._build_toolsets()
        self._native_tools = self._build_native_tools()

    def _build_toolsets(self) -> list:
        from .tools.memory import build_memory_toolset
        from .tools.registries import agent_tool_type_registry
        from .tools.self_configure import build_self_configure_toolset

        toolsets = agent_tool_type_registry.build_toolsets(self.agent, self.deps)

        # The memory is the agent's own scratchpad and is available in every
        # run, including triggered ones, so automated runs can record what
        # they created or learned.
        toolsets.append(build_memory_toolset())

        # A human in the conversation may reconfigure the agent by chatting;
        # background triggered runs must not rewrite their own configuration.
        if (
            self.chat.source in (AgentChat.Source.MANUAL, AgentChat.Source.SETUP)
            and self.chat.user_id is not None
        ):
            toolsets.append(build_self_configure_toolset())

        return toolsets

    def _build_native_tools(self) -> list:
        from .tools.registries import agent_tool_type_registry

        return agent_tool_type_registry.build_builtin_tools(self.agent, self.deps)

    # ------------------------------------------------------------------
    # Message history
    # ------------------------------------------------------------------

    async def _load_message_history(
        self, compact: bool = True
    ) -> list[ModelMessage] | None:
        raw = self.chat.message_history
        if not raw:
            return None
        try:
            messages = ModelMessagesTypeAdapter.validate_json(bytes(raw))
            # A resumed turn must keep the trailing pending tool calls
            # verbatim; compaction would collapse them away.
            return compact_message_history(messages) if compact else messages
        except Exception:
            logger.opt(exception=True).warning(
                "Failed to load message history for agent chat {}, starting fresh",
                self.chat.pk,
            )
            return None

    async def _save_message_history(self, messages_json: bytes) -> None:
        self.chat.message_history = messages_json
        await self.chat.asave(update_fields=["message_history", "updated_on"])

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        user_prompt,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
        deferred_tool_results: DeferredToolResults | None = None,
    ) -> None:
        try:
            answer, run_result = await self._stream_agent_run(
                user_prompt, message_history, queue, deferred_tool_results
            )
            queue.put_nowait(
                QueueEvent(
                    kind=QueueEventKind.RESULT,
                    answer=answer,
                    messages_json=run_result.all_messages_json(),
                    message=run_result,
                )
            )
        except Exception as exc:
            logger.exception("Error running agent {}", self.agent.id)
            queue.put_nowait(QueueEvent(kind=QueueEventKind.ERROR, error=exc))
        finally:
            queue.put_nowait(QueueEvent(kind=QueueEventKind.DONE))

    async def _stream_agent_run(
        self,
        user_prompt,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
        deferred_tool_results: DeferredToolResults | None = None,
    ):
        if self._native_tools:
            try:
                with agent_run_agent.override(native_tools=self._native_tools):
                    return await self._consume_agent_events(
                        user_prompt, message_history, queue, deferred_tool_results
                    )
            except Exception as exc:
                # Whether a provider-native tool (web search) is available
                # depends on the exact model, which only the provider knows;
                # e.g. OpenAI rejects web_search_preview for the nano models.
                # The request fails before anything streamed, so the turn can
                # safely retry without the native tools instead of erroring.
                if not _is_unsupported_native_tool_error(exc):
                    raise
                logger.warning(
                    "Native tools unsupported by model for agent {}, retrying "
                    "without them: {}",
                    self.agent.id,
                    exc,
                )
                self.deps.system_notes.append(
                    "Web search is enabled but the configured model does not "
                    "support it, so you cannot search the web."
                )

        return await self._consume_agent_events(
            user_prompt, message_history, queue, deferred_tool_results
        )

    async def _consume_agent_events(
        self,
        user_prompt,
        message_history: list[ModelMessage] | None,
        queue: asyncio.Queue[QueueEvent],
        deferred_tool_results: DeferredToolResults | None = None,
    ):
        async with agent_run_agent.run_stream_events(
            user_prompt=user_prompt,
            deps=self.deps,
            model=self.model,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            # Write tool calls that require approval pause the run by ending
            # it with a DeferredToolRequests output.
            output_type=[str, DeferredToolRequests],
            usage_limits=UsageLimits(request_limit=_REQUEST_LIMIT),
            toolsets=self._toolsets,
            model_settings=self.model_settings or None,
        ) as events:
            thinking_so_far = ""
            text_so_far = ""
            tool_names_by_call_id: dict[str, str] = {}

            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    answer = event.result.output
                    if isinstance(answer, str):
                        answer = _strip_think_tags(answer)
                    return answer, event.result

                if isinstance(event, FunctionToolCallEvent):
                    # Display events must never take down the run itself; a
                    # payload that can't be serialized just loses its chip.
                    try:
                        try:
                            args = event.part.args_as_dict()
                        except Exception:
                            args = None
                        call_id = event.part.tool_call_id or ""
                        tool_names_by_call_id[call_id] = event.part.tool_name
                        queue.put_nowait(
                            QueueEvent(
                                kind=QueueEventKind.STREAM,
                                message=ToolCallMessage(
                                    id=call_id,
                                    tool_name=event.part.tool_name,
                                    args=_jsonable(args) if args else None,
                                ),
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Failed to emit tool call event for agent {}",
                            self.agent.id,
                        )
                    continue

                if isinstance(event, FunctionToolResultEvent):
                    thinking_so_far = ""
                    text_so_far = ""
                    try:
                        result_part = event.part
                        is_error = isinstance(result_part, RetryPromptPart)
                        call_id = getattr(result_part, "tool_call_id", "") or ""
                        if is_error:
                            result_content = result_part.model_response()
                        else:
                            result_content = getattr(result_part, "content", None)
                        queue.put_nowait(
                            QueueEvent(
                                kind=QueueEventKind.STREAM,
                                message=ToolResultMessage(
                                    id=call_id,
                                    tool_name=tool_names_by_call_id.get(call_id, ""),
                                    status="error" if is_error else "ok",
                                    content=_jsonable(result_content),
                                ),
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Failed to emit tool result event for agent {}",
                            self.agent.id,
                        )
                    continue

                delta, is_thinking = _get_typed_content_delta(event)
                if delta:
                    if is_thinking:
                        thinking_so_far += delta
                    else:
                        text_so_far += delta

                    # Reasoning models emit thinking parts; some others embed
                    # <think> tags in the text stream instead. Everything else
                    # in the text stream is the answer being typed, which must
                    # not be presented as reasoning.
                    inline_thinking, answer_text = _split_think_content(text_so_far)
                    reasoning = "\n".join(
                        part
                        for part in (thinking_so_far.strip(), inline_thinking)
                        if part
                    )
                    if reasoning:
                        queue.put_nowait(
                            QueueEvent(
                                kind=QueueEventKind.STREAM,
                                message=AiReasoningChunk(content=reasoning),
                            )
                        )
                    if answer_text.strip():
                        queue.put_nowait(
                            QueueEvent(
                                kind=QueueEventKind.STREAM,
                                message=AiAnswerChunk(content=answer_text),
                            )
                        )

        raise RuntimeError("Agent stream ended without a result event")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    async def _monitor_cancellation(self, task: asyncio.Task) -> None:
        cache_key = get_agent_chat_cancellation_key(self.chat.uuid)
        while not task.done():
            await asyncio.sleep(0.2)
            if cache.get(cache_key):
                cache.delete(cache_key)
                self._tool_helpers.cancel()
                task.cancel()
                return

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    #: Set when the turn ended paused on tool calls awaiting approval, so the
    #: task marks the chat as awaiting approval instead of idle.
    paused_for_approval: bool = False

    async def arun(self, prompt_message: AgentChatMessage) -> None:
        """
        Runs a single turn started by the given (human or system) message,
        persisting the AI response incrementally and broadcasting every event.

        :param prompt_message: The persisted message whose content is this
            turn's prompt.
        :raises AgentChatRunCancelled: When the run was cancelled.
        """

        user_prompt = await sync_to_async(self._build_user_prompt)(prompt_message)
        await self._execute_turn(user_prompt, prompt_message=prompt_message)

    async def arun_resume(self) -> None:
        """
        Resumes a turn that paused on tool calls awaiting approval, feeding
        the decisions from the approval queue back into the model run.

        :raises AgentChatRunCancelled: When the run was cancelled.
        """

        deferred_results = await sync_to_async(self._build_deferred_results)()
        await self._execute_turn(None, deferred_tool_results=deferred_results)

    def _build_user_prompt(self, prompt_message: AgentChatMessage):
        from .files import extract_payload_files, load_prompt_file_parts

        file_dicts = list(prompt_message.attachments or [])
        if (
            prompt_message.role == AgentChatMessage.Role.SYSTEM
            and self.chat.event_payload
        ):
            # Files attached to the triggering row (file field values) are
            # injected into the run directly.
            file_dicts += extract_payload_files(self.chat.event_payload)

        if not file_dicts:
            return prompt_message.content

        return [prompt_message.content, *load_prompt_file_parts(file_dicts)]

    def _build_deferred_results(self) -> DeferredToolResults:
        from pydantic_ai import ToolApproved, ToolDenied

        from .models import AgentChatToolApproval

        approvals = {}
        for approval in self.chat.tool_approvals.exclude(
            status=AgentChatToolApproval.Status.PENDING
        ).order_by("-id"):
            if approval.tool_call_id in approvals:
                # Only the latest pause's decision per call id counts.
                continue
            if approval.status == AgentChatToolApproval.Status.APPROVED:
                approvals[approval.tool_call_id] = ToolApproved()
            else:
                approvals[approval.tool_call_id] = ToolDenied(
                    message=approval.reason
                    or "The user rejected this action in the approval queue."
                )

        # Only the calls that are actually pending in the message history may
        # be answered; older decided approvals from previous pauses of this
        # chat must not leak into the resume payload.
        pending_ids = self._pending_call_ids_from_history()
        if pending_ids is not None:
            approvals = {k: v for k, v in approvals.items() if k in pending_ids}

        return DeferredToolResults(approvals=approvals)

    def _pending_call_ids_from_history(self) -> set[str] | None:
        raw = self.chat.message_history
        if not raw:
            return None
        try:
            messages = ModelMessagesTypeAdapter.validate_json(bytes(raw))
        except Exception:
            return None

        last_message = messages[-1] if messages else None
        if last_message is None or last_message.kind != "response":
            return None

        return {
            part.tool_call_id
            for part in last_message.parts
            if part.part_kind == "tool-call"
        }

    def _replay_loaded_row_tools(self, messages: list[ModelMessage]) -> None:
        from baserow_enterprise.assistant.tools.database import helpers
        from baserow_enterprise.assistant.tools.database.tools import _build_row_tools

        calls = []
        for message in messages:
            for part in getattr(message, "parts", []):
                if (
                    getattr(part, "part_kind", "") == "tool-call"
                    and part.tool_name == "load_row_tools"
                ):
                    try:
                        calls.append(part.args_as_dict())
                    except Exception:
                        continue

        for args in calls:
            try:
                tables = helpers.filter_tables(
                    self.deps.user, self.deps.workspace
                ).filter(id__in=args.get("table_ids") or [])
                operations = args.get("operations") or []
                loaded_names = {tool.name for tool in self.deps.dynamic_tools}
                for table in tables:
                    table_tools = _build_row_tools(
                        self.deps.user,
                        self.deps.workspace,
                        self.deps.tool_helpers,
                        table,
                    )
                    for operation in ("create", "update", "delete"):
                        tool = table_tools.get(operation)
                        if (
                            operation in operations
                            and tool is not None
                            and tool.name not in loaded_names
                        ):
                            self.deps.dynamic_tools.append(tool)
                            loaded_names.add(tool.name)
            except Exception:
                logger.exception(
                    "Failed to replay load_row_tools for agent chat {}",
                    self.chat.pk,
                )

    async def _execute_turn(
        self,
        user_prompt,
        prompt_message: AgentChatMessage | None = None,
        deferred_tool_results: DeferredToolResults | None = None,
    ) -> None:
        ai_message = await AgentChatMessage.objects.acreate(
            chat=self.chat, role=AgentChatMessage.Role.AI, content=""
        )
        self._broadcast(AiStartedMessage(message_id=str(ai_message.id)))

        message_history = await self._load_message_history(
            compact=deferred_tool_results is None
        )
        if deferred_tool_results is not None and message_history:
            # The paused turn may have loaded per-table row tools dynamically;
            # a resumed process starts empty, so an approved row write would
            # reference a tool that no longer exists. Replaying the history's
            # load_row_tools calls restores them.
            await sync_to_async(self._replay_loaded_row_tools)(message_history)
        queue: asyncio.Queue[QueueEvent] = asyncio.Queue()
        self._event_bus.set_queue(queue)

        agent_task = asyncio.create_task(
            self._run_agent(user_prompt, message_history, queue, deferred_tool_results)
        )
        monitor_task = asyncio.create_task(self._monitor_cancellation(agent_task))

        events_log: list[dict] = []
        answer = None
        messages_json = None
        run_result = None
        error: Exception | None = None
        dirty = False
        last_broadcast = 0.0
        last_flush = 0.0

        try:
            while True:
                event = await queue.get()
                if event.kind == QueueEventKind.DONE:
                    break
                elif event.kind == QueueEventKind.RESULT:
                    answer = event.answer
                    messages_json = event.messages_json
                    run_result = event.message
                elif event.kind == QueueEventKind.ERROR:
                    error = event.error
                else:
                    dirty = (
                        self._handle_stream_event(event.message, events_log) or dirty
                    )

                now = time.monotonic()
                if now - last_broadcast >= _BROADCAST_INTERVAL:
                    last_broadcast = now
                    self._broadcast_pending_reasoning()
                if dirty and now - last_flush >= _FLUSH_INTERVAL:
                    last_flush = now
                    await self._flush(ai_message, events_log)
                    dirty = False

            if agent_task.cancelled():
                await self._finalize_cancelled(ai_message, events_log)
                raise AgentChatRunCancelled()

            if error is not None:
                await self._finalize_error(ai_message, events_log, error)
                raise error

            if isinstance(answer, DeferredToolRequests):
                self.paused_for_approval = True
                await self._finalize_paused(
                    ai_message, events_log, answer, run_result, messages_json
                )
            else:
                await self._finalize_success(
                    ai_message, events_log, answer, run_result, messages_json
                )
        finally:
            monitor_task.cancel()
            if not agent_task.done():
                agent_task.cancel()
            await asyncio.gather(monitor_task, agent_task, return_exceptions=True)
            self._event_bus.set_queue(None)

        if prompt_message is not None:
            await self._maybe_generate_title(prompt_message)

    # ------------------------------------------------------------------
    # Event handling / persistence
    # ------------------------------------------------------------------

    def _handle_stream_event(self, message: Any, events_log: list[dict]) -> bool:
        """
        Broadcasts the event and updates the structured event log persisted in
        the AI message's artifacts. Returns whether the log changed.
        """

        if isinstance(message, AiThinkingMessage):
            # Pure status updates are ephemeral and not part of the history.
            self._broadcast(message)
            return False

        if isinstance(message, AiReasoningChunk):
            # The frontend replaces reasoning content on every chunk, so only
            # the latest content matters. Broadcasting is throttled by the
            # flush interval to avoid flooding the websocket.
            if events_log and events_log[-1]["type"] == "ai/reasoning":
                events_log[-1]["content"] = message.content
            else:
                events_log.append(message.model_dump())
            self._pending_reasoning = message
            return True

        if isinstance(message, AiAnswerChunk):
            # The streaming partial answer is ephemeral: the completed answer
            # is persisted on the message itself.
            self._pending_answer = message
            return False

        if isinstance(message, (ToolCallMessage, ToolResultMessage)):
            self._broadcast(message)
            if isinstance(message, ToolResultMessage):
                for event in reversed(events_log):
                    if event["type"] == "tool_call" and event["id"] == message.id:
                        event["result"] = {
                            "status": message.status,
                            "content": message.content,
                        }
                        return True
            events_log.append(message.model_dump())
            return True

        self._broadcast(message)
        return False

    _pending_reasoning: AiReasoningChunk | None = None
    _pending_answer: AiAnswerChunk | None = None

    def _broadcast_pending_reasoning(self):
        if self._pending_reasoning is not None:
            self._broadcast(self._pending_reasoning)
            self._pending_reasoning = None
        if self._pending_answer is not None:
            self._broadcast(self._pending_answer)
            self._pending_answer = None

    async def _flush(self, ai_message: AgentChatMessage, events_log: list[dict]):
        self._broadcast_pending_reasoning()
        ai_message.artifacts = {"events": events_log}
        await ai_message.asave(update_fields=["artifacts", "updated_on"])

    async def _record_usage(self, ai_message, run_result):
        if run_result is None:
            return
        usage = run_result.usage
        ai_message.input_tokens = usage.input_tokens
        ai_message.output_tokens = usage.output_tokens
        self.chat.total_input_tokens += usage.input_tokens or 0
        self.chat.total_output_tokens += usage.output_tokens or 0
        await self.chat.asave(
            update_fields=[
                "total_input_tokens",
                "total_output_tokens",
                "updated_on",
            ]
        )

    async def _finalize_success(
        self, ai_message, events_log, answer, run_result, messages_json
    ):
        ai_message.content = answer or ""
        ai_message.artifacts = {"events": events_log}

        await self._record_usage(ai_message, run_result)

        await ai_message.asave(
            update_fields=["content", "artifacts", "input_tokens", "output_tokens"]
        )

        if messages_json:
            await self._save_message_history(messages_json)

        self._broadcast(
            AiMessageChunk(content=answer or "", sources=self.deps.sources or None)
        )

    async def _finalize_paused(
        self,
        ai_message,
        events_log,
        deferred: DeferredToolRequests,
        run_result,
        messages_json,
    ):
        from .models import AgentChatToolApproval

        def create_approvals():
            approvals = []
            for part in deferred.approvals:
                try:
                    args = part.args_as_dict()
                except Exception:
                    args = None
                approvals.append(
                    AgentChatToolApproval.objects.create(
                        chat=self.chat,
                        message=ai_message,
                        tool_call_id=part.tool_call_id or "",
                        tool_name=part.tool_name,
                        tool_args=(
                            _jsonable(args, limit=_APPROVAL_ARGS_CONTENT_LIMIT)
                            if args is not None
                            else None
                        ),
                    )
                )
            return approvals

        approvals = await sync_to_async(create_approvals)()
        serialized = [
            {
                "id": approval.id,
                "tool_call_id": approval.tool_call_id,
                "tool_name": approval.tool_name,
                "tool_args": approval.tool_args,
                "status": approval.status,
            }
            for approval in approvals
        ]

        ai_message.artifacts = {"events": events_log, "approvals": serialized}
        await self._record_usage(ai_message, run_result)
        await ai_message.asave(
            update_fields=["artifacts", "input_tokens", "output_tokens", "updated_on"]
        )

        # The history contains the pending tool calls; the resume run matches
        # the queue decisions to them by tool call id.
        if messages_json:
            await self._save_message_history(messages_json)

        self._broadcast(ApprovalRequestMessage(approvals=serialized))

        from .realtime import broadcast_pending_approvals_updated

        # Also update the workspace-wide indicators (sidebar and header).
        await sync_to_async(broadcast_pending_approvals_updated)(self.application)

    async def _finalize_error(self, ai_message, events_log, error: Exception):
        ai_message.artifacts = {"events": events_log}
        await ai_message.asave(update_fields=["artifacts", "updated_on"])
        self._broadcast(AiErrorMessage(content=str(error)))

    async def _finalize_cancelled(self, ai_message, events_log):
        ai_message.artifacts = {"events": events_log, "cancelled": True}
        await ai_message.asave(update_fields=["artifacts", "updated_on"])
        self._broadcast(AiCancelledMessage(message_id=str(ai_message.id)))

    async def _maybe_generate_title(self, prompt_message: AgentChatMessage):
        if self.chat.title:
            return

        if self.chat.source != AgentChat.Source.MANUAL:
            # Deterministic titles for automated runs; no extra LLM call.
            title = f"{self.chat.get_source_display()}: {self.chat.trigger_type}"
        else:
            try:
                result = await title_agent.run(prompt_message.content, model=self.model)
                title = result.output
            except Exception:
                logger.exception("Failed to generate agent chat title")
                return

        self.chat.title = title[: AgentChat.TITLE_MAX_LENGTH]
        await self.chat.asave(update_fields=["title", "updated_on"])
        self._broadcast(ChatTitleMessage(content=self.chat.title))
        broadcast_chat_updated(self.chat)

    def _broadcast(self, event) -> None:
        broadcast_chat_event(self.chat, event.model_dump())
