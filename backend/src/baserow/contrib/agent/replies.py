import asyncio
from functools import partial
from typing import TYPE_CHECKING

from loguru import logger
from pydantic_ai import Agent, AgentRunResultEvent, RunContext, WebSearchTool
from pydantic_ai.capabilities import WebSearch
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset
from pydantic_ai.usage import UsageLimits

from baserow.contrib.integrations.mcp.toolset import MCPServerToolset
from baserow.core.chat_runs.constants import ChatRunErrorCode, ChatRunStopReason
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.steps import ChatRunSteps
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.generative_ai.constants import WEB_SEARCH_MAX_PER_REPLY
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.tools import ToolContext
from baserow.core.utils import remove_null_characters

from .constants import (
    INTERRUPTED_CHANGES_NOTE,
    INTERRUPTED_REPLY_NOTE,
    REPLY_REQUEST_LIMIT,
    TOOL_RETRIES,
    UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS,
    WEB_SEARCH_FAILED_INSTRUCTIONS,
    WEB_SEARCH_INSTRUCTIONS,
    WEB_SEARCH_STEP_MAX_QUERIES,
    WEB_SEARCH_STEP_QUERY_MAX_LENGTH,
    WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS,
)
from .models import AgentMessage
from .registries import agent_tool_type_registry
from .types import AgentReplyRequest, AgentReplyResult

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


def _interruption_note(reply: AgentMessage) -> str:
    """
    Name the changes an interrupted reply started, since its text may not.

    :param reply: A reply that did not complete.
    :return: The interruption note, followed by the changes it started, if any.
    """

    changes = ", ".join(
        f"{step.get('tool')} ({step.get('status')})"
        for step in reply.steps or []
        if isinstance(step, dict) and step.get("changes_data") is True
    )
    if not changes:
        return INTERRUPTED_REPLY_NOTE
    return (
        f"{INTERRUPTED_REPLY_NOTE}\n{INTERRUPTED_CHANGES_NOTE.format(changes=changes)}"
    )


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
                text = f"{text}\n\n{_interruption_note(message)}".strip()
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
    settings_override = model_type.get_model_settings_override(
        request.model_identifier, request.workspace
    )
    model = model_type.get_ai_model(
        request.model_identifier, request.workspace, settings_override
    )
    model_settings = model_type.prepare_model_settings(request.model_identifier)
    thinking = model_type.get_thinking_level(
        request.model_identifier, model, request.reasoning_effort
    )
    if thinking is not None:
        model_settings["thinking"] = thinking
    # The provider removes what this model cannot accept, thinking included.
    model_settings = model_type.sanitize_model_settings(
        request.model_identifier, model_settings
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


def _step_text(value: object) -> str | None:
    """Validate and bound a value a provider reported before saving it in a step."""

    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    max_length = WEB_SEARCH_STEP_QUERY_MAX_LENGTH
    return value if len(value) <= max_length else value[: max_length - 1] + "…"


def _web_search_step_input(arguments: dict) -> dict:
    """
    Pick what a search looked for or opened, which providers report in different
    shapes. These steps are the only record of what left the workspace, so every
    query is kept.

    :param arguments: The arguments the provider reported.
    :return: The queries and the opened page, without unusable values.
    """

    reported = arguments.get("queries")
    candidates = [arguments.get("query")]
    if isinstance(reported, list):
        candidates.extend(reported)
    queries = []
    for candidate in candidates:
        query = _step_text(candidate)
        if query is not None and query not in queries:
            queries.append(query)
    step_input = {}
    if queries:
        step_input["queries"] = queries[:WEB_SEARCH_STEP_MAX_QUERIES]
    url = _step_text(arguments.get("url"))
    if url is not None:
        step_input["url"] = url
    return step_input


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
        self._text_is_commentary = False
        self._result: str | None = None
        self._mcp_toolsets = [
            MCPServerToolset(server) for server in request.mcp_servers
        ]
        self._steps = ChatRunSteps(journal, self._describe_call)

    def _describe_call(self, name: str, arguments: dict) -> dict | None:
        """
        Describe a call to one of the reply's tools from its arguments.

        :param name: The called tool's name.
        :param arguments: Its arguments.
        :return: Whether the tool changes data and its input summary, or None
            for a tool the reply doesn't offer, which the model can still name.
        """

        for toolset in self._mcp_toolsets:
            if snapshot := toolset.get_tool_snapshot(name):
                return {
                    "changes_data": snapshot.changes_data,
                    "input": toolset.get_step_input(name),
                }
        if name == WebSearchTool.kind:
            return {"changes_data": False, "input": _web_search_step_input(arguments)}
        if name not in self._request.allowed_tool_names:
            return None
        tool = agent_tool_type_registry.get(name)
        try:
            summary = tool.get_step_input(arguments)
        except Exception as exc:
            logger.error(
                "Agent tool {} step input failed ({})", tool.type, type(exc).__name__
            )
            summary = {}
        return {"changes_data": tool.changes_data, "input": summary}

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

    def _get_instructions(self, web_search_tool: WebSearchTool | None) -> str:
        """
        Combine saved instructions with this reply's workspace access and web search
        context.

        :param web_search_tool: The web search this attempt offers, if any.
        :return: The instructions.
        """

        instructions = self._request.instructions
        if self._request.run_as_unavailable:
            instructions += f"\n\n{UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS}"
        if web_search_tool is not None:
            instructions += f"\n\n{WEB_SEARCH_INSTRUCTIONS}"
        elif self._request.web_search_tool is not None:
            instructions += f"\n\n{WEB_SEARCH_FAILED_INSTRUCTIONS}"
        elif self._request.web_search_enabled:
            instructions += f"\n\n{WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS}"
        return instructions

    def _search_unavailable(self) -> None:
        """
        Show that this reply couldn't offer the web search it was meant to, so the
        user learns it from the reply itself rather than from the model.
        """

        self._steps.add_failed(WebSearchTool.kind, {"unavailable": True})

    async def _stream(self) -> None:
        web_search_tool = self._request.web_search_tool
        if web_search_tool is not None and WebSearchTool not in self._model.profile.get(
            "supported_native_tools", frozenset()
        ):
            # The SDK would refuse the whole request rather than leave search out.
            web_search_tool = None
            self._search_unavailable()
        async with self._model:
            try:
                await self._run_model(web_search_tool)
            except ModelHTTPError as exc:
                # Some models refuse the tool, which only the provider knows. A refused
                # request searched nothing and showed nothing, so it can run again.
                if (
                    web_search_tool is None
                    or exc.status_code != 400
                    or self._text
                    or self._steps.started
                ):
                    raise
                logger.warning(
                    "Agent reply {} got a 400 with web search, retrying without it",
                    self._request.reply_id,
                )
                self._search_unavailable()
                await self._run_model(None)

    async def _run_model(self, web_search_tool: WebSearchTool | None) -> None:
        """
        Run the model once, passing its events on.

        :param web_search_tool: The web search to offer, if any.
        """

        agent = Agent(
            instructions=self._get_instructions(web_search_tool),
            retries={"tools": TOOL_RETRIES},
            capabilities=[
                WebSearch(native=partial(self._offered_web_search, web_search_tool))
            ]
            if web_search_tool
            else [],
        )
        # Kuma enables content tracing for every Agent; conversations are private.
        agent.instrument = False
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

    def _offered_web_search(
        self, web_search_tool: WebSearchTool, ctx: RunContext
    ) -> WebSearchTool | None:
        """
        Offer web search to the next request while the reply has searches left.

        Anthropic counts the searches of every request in the reply against the
        tool's own cap, so this matters for the providers that don't.

        :param web_search_tool: The web search of this attempt.
        :param ctx: The run so far.
        :return: The tool, or None once the reply used its searches.
        """

        searches = [
            part
            for message in ctx.messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, NativeToolCallPart)
            and part.tool_name == WebSearchTool.kind
        ]
        # Anthropic runs a search emitted next to a function tool call in the next
        # request, and rejects that request when the search tool is missing.
        answered = {
            part.tool_call_id
            for message in ctx.messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, NativeToolReturnPart)
        }
        waiting = any(part.tool_call_id not in answered for part in searches)
        if len(searches) >= WEB_SEARCH_MAX_PER_REPLY and not waiting:
            return None
        return web_search_tool

    def _toolsets(self) -> list[AbstractToolset]:
        """
        The tools the reply may call: Baserow's, acting as the Agent's identity,
        and those turned on for its MCP servers.

        :return: The toolsets, none when the reply may call no tool.
        """

        request = self._request
        toolsets: list[AbstractToolset] = []
        if request.allowed_tool_names:
            ctx = ToolContext(
                user=request.acting_subject,
                workspace=request.workspace,
                timezone=request.timezone,
            )
            toolsets.append(
                FunctionToolset(
                    [
                        agent_tool_type_registry.get(name).get_tool(ctx)
                        for name in request.allowed_tool_names
                    ]
                )
            )
        return [*toolsets, *self._mcp_toolsets]

    def _on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """
        Stream the text of the model's latest response and keep the final result.

        :param event: An event of the run.
        """

        self._steps.on_event(event)
        match event:
            case AgentRunResultEvent(result=result):
                self._result = result.output
                return
            case FunctionToolCallEvent():
                # Text before a tool call is narration; the next response is the answer.
                self._parts = {}
            case PartStartEvent(part=NativeToolCallPart()):
                # Text before a search is narration too, but only once more text
                # follows, because Gemini reports its searches after the answer.
                self._text_is_commentary = True
                return
            case PartStartEvent(index=index, part=TextPart(content=content)):
                if self._text_is_commentary:
                    self._parts = {}
                    self._text_is_commentary = False
                self._parts[index] = content
            case PartDeltaEvent(index=index, delta=TextPartDelta(content_delta=delta)):
                self._parts[index] = self._parts.get(index, "") + delta
            case _:
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
        Collect what the reply produced: its text and its tool activity.

        :return: The final answer once the model finished, else the text so far.
        """

        steps = self._steps.finish() or None
        if self._result is None:
            return AgentReplyResult(text=self._text, steps=steps)
        return AgentReplyResult(text=remove_null_characters(self._result), steps=steps)
