import asyncio
from typing import TYPE_CHECKING

from loguru import logger
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from baserow.core.chat_runs.constants import ChatRunErrorCode, ChatRunStopReason
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.generative_ai.registries import generative_ai_model_type_registry

from .constants import INTERRUPTED_REPLY_NOTE, REPLY_REQUEST_LIMIT
from .models import AgentMessage, AgentTurn
from .types import AgentReplyRequest

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


def build_history(messages: list[AgentMessage]) -> list[ModelMessage]:
    """
    Pair earlier prompts and replies as model history, marking unfinished ones.

    :param messages: Earlier messages of the conversation, oldest first.
    :return: The history; a reply whose prompt fell outside the window is left
        out, so it always starts with a prompt.
    """

    pairs: list[list[AgentMessage | None]] = []
    for message in messages:
        if message.role == AgentMessage.Role.USER:
            pairs.append([message, None])
        elif pairs and pairs[-1][1] is None and pairs[-1][0].turn_id == message.turn_id:
            pairs[-1][1] = message
    history: list[ModelMessage] = []
    for prompt, reply in pairs:
        history.append(ModelRequest(parts=[UserPromptPart(content=prompt.content)]))
        text = reply.content if reply else ""
        if prompt.turn is not None and prompt.turn.status != AgentTurn.Status.COMPLETED:
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
        self._result: str | None = None

    async def answer(self) -> ChatRunOutcome:
        """
        Answer until the model finishes or the journal asks the run to stop.

        :return: How the reply ended, with the complete or partial reply text.
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
        agent = Agent(instructions=self._request.instructions)
        # Kuma enables content tracing for every Agent; conversations are private.
        agent.instrument = False
        async with self._model:
            async with agent.run_stream(
                self._request.prompt,
                message_history=build_history(self._request.history),
                model=self._model,
                model_settings=self._model_settings,
                usage_limits=UsageLimits(request_limit=REPLY_REQUEST_LIMIT),
            ) as result:
                async for text in result.stream_text(debounce_by=None):
                    self._text = text
                    self._journal.emit_text(text)
                self._result = await result.get_output()

    def _outcome(self, work: asyncio.Task) -> ChatRunOutcome:
        if self._result is not None:
            return ChatRunOutcome(ChatRunStatus.COMPLETED, result=self._result)
        if self._journal.stop_reason == ChatRunStopReason.CANCELLED:
            return ChatRunOutcome(ChatRunStatus.CANCELLED, result=self._text)
        if self._journal.stop_reason == ChatRunStopReason.TIMEOUT:
            return ChatRunOutcome(
                ChatRunStatus.FAILED, ChatRunErrorCode.TIMEOUT, self._text
            )
        if not work.cancelled() and work.exception() is not None:
            logger.error(
                "Agent turn {} could not be answered ({})",
                self._request.turn_id,
                _describe_failure(work.exception()),
            )
        return ChatRunOutcome(ChatRunStatus.FAILED, ChatRunErrorCode.FAILED, self._text)
