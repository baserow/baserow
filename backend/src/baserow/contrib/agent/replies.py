import asyncio
from typing import TYPE_CHECKING

from loguru import logger
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResult
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits
from pydantic_core import to_jsonable_python

from baserow.core.chat_runs.constants import ChatRunErrorCode, ChatRunStopReason
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.tools import ToolContext
from baserow.core.utils import remove_null_characters

from .constants import INTERRUPTED_REPLY_NOTE, REPLY_REQUEST_LIMIT, TOOL_RETRIES
from .models import AgentMessage
from .registries import agent_tool_type_registry
from .types import AgentReplyRequest, AgentReplyResult

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


def build_history(messages: list[AgentMessage]) -> list[ModelMessage]:
    """
    Turn earlier prompts and replies into model history, marking replies that did
    not complete.

    :param messages: Earlier messages of the conversation, oldest first.
    :return: The history; replies before the first prompt in the window are left
        out, so it always starts with a prompt.
    """

    history: list[ModelMessage] = []
    for message in messages:
        if message.role == AgentMessage.Role.USER:
            history.append(
                ModelRequest(parts=[UserPromptPart(content=message.content)])
            )
        elif history:
            text = message.content
            if message.status != ChatRunStatus.COMPLETED:
                text = f"{text}\n\n{INTERRUPTED_REPLY_NOTE}".strip()
            if text:
                history.append(ModelResponse(parts=[TextPart(content=text)]))
    return history


def create_reply_model(request: AgentReplyRequest) -> tuple[Model, dict]:
    """
    Build the configured model and its request settings, outside the event loop.

    :param request: What the run answers.
    :return: The model, whose client opens when it is entered, and its settings.
    """

    model_type = generative_ai_model_type_registry.get(request.provider_type)
    model_settings = model_type.sanitize_model_settings(
        request.model_identifier,
        model_type.prepare_model_settings(request.model_identifier),
    )
    settings_override = model_type.get_model_settings_override(
        request.model_identifier, request.workspace
    )
    model = model_type.get_ai_model(
        request.model_identifier, request.workspace, settings_override
    )
    return model, model_settings


def _describe_failure(error: BaseException) -> str:
    """
    Name a provider failure without its message, which can echo the request.

    :param error: What the model raised.
    :return: The exception class and, when present, its HTTP status code.
    """

    status_code = getattr(error, "status_code", None)
    name = type(error).__name__
    return f"{name}, status {status_code}" if status_code else name


class AgentResponder:
    """Stream one reply into a run's journal until it ends or a stop is requested."""

    def __init__(
        self,
        request: AgentReplyRequest,
        journal: "ChatRunJournal",
        model: Model,
        model_settings: dict,
    ) -> None:
        """
        :param request: What the run answers.
        :param journal: Receives the streamed text and signals a stop.
        :param model: The configured model, not entered yet.
        :param model_settings: Its request settings.
        """

        self._request = request
        self._journal = journal
        self._model = model
        self._model_settings = model_settings
        self._text = ""
        self._parts: dict[int, str] = {}
        self._result: AgentRunResult[str] | None = None

    async def answer(self) -> ChatRunOutcome:
        """
        Answer until the model finishes or the journal asks the run to stop.

        :return: How the reply ended, with its text and the model's transcript.
        """

        work = asyncio.create_task(self._stream())
        stop = asyncio.create_task(self._journal.wait_for_stop())
        try:
            await asyncio.wait({work, stop}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            work.cancel()
            stop.cancel()
            await asyncio.gather(work, stop, return_exceptions=True)
        return self._outcome(work)

    async def _stream(self) -> None:
        agent = Agent(
            instructions=self._request.instructions,
            retries={"tools": TOOL_RETRIES},
        )
        # Kuma enables content tracing for every Agent; conversations are private.
        agent.instrument = False
        async with self._model:
            async with agent.run_stream_events(
                self._request.prompt,
                message_history=build_history(self._request.history),
                model=self._model,
                model_settings=self._model_settings,
                usage_limits=UsageLimits(request_limit=REPLY_REQUEST_LIMIT),
                toolsets=self._toolsets(),
            ) as events:
                async for event in events:
                    self._on_event(event)

    def _toolsets(self) -> list[FunctionToolset]:
        """
        The tools the reply may call, acting as the Agent's identity.

        :return: One toolset, or none when the reply may call no tool.
        """

        request = self._request
        if not request.allowed_tool_names:
            return []
        ctx = ToolContext(
            user=request.acting_subject,
            workspace=request.workspace,
            timezone=request.timezone,
        )
        return [
            FunctionToolset(
                [
                    agent_tool_type_registry.get(name).get_tool(ctx)
                    for name in request.allowed_tool_names
                ]
            )
        ]

    def _on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """
        Stream the text of the model's latest response and keep the final result.

        :param event: An event of the run.
        """

        if isinstance(event, AgentRunResultEvent):
            self._result = event.result
            return
        if isinstance(event, FunctionToolCallEvent):
            # The next response replaces what the model wrote before calling a tool.
            self._parts = {}
            return
        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
            self._parts[event.index] = event.part.content
        elif isinstance(event, PartDeltaEvent) and isinstance(
            event.delta, TextPartDelta
        ):
            self._parts[event.index] = (
                self._parts.get(event.index, "") + event.delta.content_delta
            )
        else:
            return
        self._text = "".join(self._parts[index] for index in sorted(self._parts))
        self._journal.emit_text(self._text)

    def _outcome(self, work: asyncio.Task) -> ChatRunOutcome:
        result = self._reply_result()
        # A blank answer is no reply, and some providers reject it in the history.
        if self._result is not None and result.text.strip():
            return ChatRunOutcome(ChatRunStatus.COMPLETED, result=result)
        if self._journal.stop_reason == ChatRunStopReason.CANCELLED:
            return ChatRunOutcome(ChatRunStatus.CANCELLED, result=result)
        if self._journal.stop_reason == ChatRunStopReason.TIMEOUT:
            return ChatRunOutcome(
                ChatRunStatus.FAILED, ChatRunErrorCode.TIMEOUT, result
            )
        if not work.cancelled() and work.exception() is not None:
            logger.error(
                "Agent reply {} could not be written ({})",
                self._request.reply_id,
                _describe_failure(work.exception()),
            )
        return ChatRunOutcome(ChatRunStatus.FAILED, ChatRunErrorCode.FAILED, result)

    def _reply_result(self) -> AgentReplyResult:
        """
        Collect what the reply produced: its text, the provider and model, and once
        the model finished, its messages and usage.

        :return: The text and the execution details of the reply.
        """

        if self._result is None:
            return AgentReplyResult(
                text=self._text,
                provider_type=self._request.provider_type,
                model_identifier=self._request.model_identifier,
            )
        return AgentReplyResult(
            text=remove_null_characters(self._result.output),
            provider_type=self._request.provider_type,
            model_identifier=self._request.model_identifier,
            model_messages=ModelMessagesTypeAdapter.dump_python(
                self._result.new_messages(), mode="json"
            ),
            usage=to_jsonable_python(self._result.usage),
        )
