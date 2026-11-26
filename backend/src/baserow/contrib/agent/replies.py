import asyncio
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from functools import cached_property, partial
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    ConversationTypeAdapter,
    DeferredToolRequests,
    ModelRetry,
    RunContext,
    WebSearchTool,
)
from pydantic_ai.capabilities import WebSearch
from pydantic_ai.exceptions import ApprovalRequired, ModelHTTPError
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResult
from pydantic_ai.toolsets import (
    AbstractToolset,
    FunctionToolset,
    WrapperToolset,
)
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.usage import UsageLimits
from pydantic_core import to_jsonable_python

from baserow.contrib.integrations.mcp.toolset import (
    MCPServerToolset,
    MCPToolSnapshot,
)
from baserow.core.chat_runs.constants import (
    ChatRunErrorCode,
    ChatRunStepStatus,
    ChatRunStopReason,
)
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.steps import (
    ChatRunSteps,
    ToolCallDiagnosticEvent,
    ToolCallInputEvent,
    ToolFailureWithDiagnostic,
)
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.generative_ai.constants import WEB_SEARCH_MAX_PER_REPLY
from baserow.core.generative_ai.model_profiles import AGENT
from baserow.core.generative_ai.output_validation import ModelOutputValidator
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.generative_ai.usage import (
    AIUsageLimitExceeded,
    AIUsageScope,
    UsageReportingModel,
)
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolErrorCode, describe_failure
from baserow.core.utils import remove_null_characters, remove_unstorable_characters

from .action_tools.tools import BoundActionTool
from .constants import (
    AGENT_MESSAGE_USAGE_REFERENCE,
    AGENT_USAGE_FEATURE,
    AGENT_USAGE_LIMIT_EXCEEDED,
    ASK_FIRST_INSTRUCTIONS,
    ASK_PERSON_DISMISSED_HISTORY,
    ASK_PERSON_TOOL_NAME,
    CONVERSATION_USER_INSTRUCTIONS,
    DELETED_SENDER_NAME,
    INTERRUPTED_CHANGES_NOTE,
    INTERRUPTED_REPLY_NOTE,
    OUTPUT_RETRIES,
    REPLY_REQUEST_LIMIT,
    RUN_AS_IDENTITY_INSTRUCTIONS,
    SHARED_CONVERSATION_INSTRUCTIONS,
    TOOL_RETRIES,
    TRIGGER_CONVERSATION_INSTRUCTIONS,
    UNATTENDED_ASK_PERSON_INSTRUCTIONS,
    UNATTENDED_NO_PERSON_INSTRUCTIONS,
    UNATTENDED_REPLY_INSTRUCTIONS,
    UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS,
    VISITOR_ASK_FIRST_INSTRUCTIONS,
    VISITOR_CONVERSATION_INSTRUCTIONS,
    VISITOR_UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS,
    WEB_FETCH_INSTRUCTIONS,
    WEB_SEARCH_FAILED_INSTRUCTIONS,
    WEB_SEARCH_INSTRUCTIONS,
    WEB_SEARCH_STEP_MAX_QUERIES,
    WEB_SEARCH_STEP_QUERY_MAX_LENGTH,
    WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS,
)
from .models import AgentMessage, AgentToolApproval
from .previews import arguments_preview
from .registries import AgentToolType, agent_tool_type_registry, input_shower
from .tools import ask_person_tool
from .types import (
    AgentConversationUser,
    AgentPausedRun,
    AgentReplyRequest,
    AgentReplyResult,
    one_line_name,
)
from .web_fetch import web_fetch_tool

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
        if isinstance(step, dict)
        and step.get("changes_data") is True
        and step.get("status") != ChatRunStepStatus.REJECTED
        and step.get("error_code") != ToolErrorCode.NOT_RUN
    )
    if not changes:
        return INTERRUPTED_REPLY_NOTE
    return (
        f"{INTERRUPTED_REPLY_NOTE}\n{INTERRUPTED_CHANGES_NOTE.format(changes=changes)}"
    )


def name_sender(content: str, sender: AgentConversationUser | None) -> str:
    """
    :param content: What a person wrote in a shared conversation.
    :param sender: Who wrote it, or None for a deleted user.
    :return: A JSON object naming who wrote the content, which neither the
        content nor the name can end early to pass for another sender.
    """

    return json.dumps(
        {
            "sender": sender.name if sender else DELETED_SENDER_NAME,
            "user_id": sender.id if sender else None,
            "message": content,
        },
        ensure_ascii=False,
    )


def get_prompt_content(message: AgentMessage, names_senders: bool) -> str:
    """
    :param message: A prompt, sent by a person or a trigger, with its sender.
    :param names_senders: Whether people's messages name who wrote them.
    :return: The content as the model reads it. Only a person's message names
        its sender, so only one of those can come from a deleted user.
    """

    if not names_senders or message.role != AgentMessage.Role.USER:
        return message.content
    sender = message.sender
    return name_sender(message.content, sender and AgentConversationUser.of(sender))


def _question_turns(
    reply: AgentMessage, names_senders: bool = False
) -> list[ModelMessage]:
    """
    Replay the decided questions of a reply as the agent asking and a person
    answering, in the order the calls were held.

    :param reply: An earlier reply with its decided questions and their deciders
        prefetched.
    :param names_senders: Whether each answer names who gave it.
    :return: A response with each question followed by a request with its answer,
        or the dismissal; questions without a saved step are left out.
    """

    questions = {
        step.get("id"): (step.get("input") or {}).get("question")
        for step in reply.steps or []
        if isinstance(step, dict) and step.get("tool") == ASK_PERSON_TOOL_NAME
    }
    if not questions:
        return []
    turns: list[ModelMessage] = []
    for approval in reply.decided_questions:
        if not (question := questions.get(approval.step_id)):
            continue
        answer = (
            approval.answer
            if approval.status == AgentToolApproval.Status.APPROVED
            else ASK_PERSON_DISMISSED_HISTORY
        )
        if names_senders and approval.status == AgentToolApproval.Status.APPROVED:
            decider = approval.decided_by
            answer = name_sender(answer, decider and AgentConversationUser.of(decider))
        turns.append(ModelResponse(parts=[TextPart(content=question)]))
        turns.append(ModelRequest(parts=[UserPromptPart(content=answer)]))
    return turns


def build_history(
    messages: list[AgentMessage], names_senders: bool = False
) -> list[ModelMessage]:
    """
    Turn earlier prompts, sent by a person, a trigger or a visitor, and replies
    into model history, marking replies that did not complete. Questions a reply
    asked a person come before its text, as the agent asking and the person
    answering.

    :param messages: Earlier messages of the conversation, oldest first, with
        their senders and the replies' decided questions prefetched.
    :param names_senders: Whether each person's message and answer names who
        wrote it.
    :return: The history; replies before the first prompt in the window are left
        out, so it always starts with a prompt.
    """

    prompt_roles = {
        AgentMessage.Role.USER,
        AgentMessage.Role.TRIGGER,
        AgentMessage.Role.VISITOR,
    }
    history: list[ModelMessage] = []
    for message in messages:
        if message.role in prompt_roles:
            content = get_prompt_content(message, names_senders)
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif history:
            history.extend(_question_turns(message, names_senders))
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
    :return: The model, whose client opens when it is entered and which reports
        the usage of every request, and its settings.
    """

    model_type = generative_ai_model_type_registry.get(request.provider_type)
    resolved = model_type.resolve_model_settings(
        request.model_identifier, request.workspace
    )
    model = model_type.get_ai_model(
        request.model_identifier, request.workspace, resolved.settings
    )
    model_settings = model_type.get_model_settings(request.model_identifier, AGENT)
    model_settings.update(
        model_type.prepare_model_settings(
            request.model_identifier, model_settings.get("temperature")
        )
    )
    thinking = model_type.get_thinking_level(
        request.model_identifier, model, request.reasoning_effort
    )
    if thinking is not None:
        model_settings["thinking"] = thinking
    # The provider removes what this model cannot accept, thinking included.
    model_settings = model_type.sanitize_model_settings(
        request.model_identifier, model_settings
    )
    usage_scope = AIUsageScope(
        provider_type=model_type.type,
        model=request.model_identifier,
        uses_shared_key=resolved.uses_shared_key,
        feature=AGENT_USAGE_FEATURE,
        workspace=request.workspace,
        reference_type=AGENT_MESSAGE_USAGE_REFERENCE,
        reference_id=str(request.reply_id),
    )
    return UsageReportingModel(model, usage_scope), model_settings


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


@dataclass
class _HeldCallsToolset(WrapperToolset[None]):
    """Holds the calls a reply waits on for approval, with their readable request."""

    is_held: Callable[[RunContext[None]], bool]
    tool_ctx: ToolContext
    tools: dict[str, AgentToolType | BoundActionTool]

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[None],
        tool: ToolsetTool[None],
    ) -> Any:
        if not ctx.tool_call_approved and self.is_held(ctx):
            result = await sync_to_async(self.tools[name].hold_call)(
                self.tool_ctx,
                tool_args,
                input_shower(ctx),
            )
        else:
            result = await super().call_tool(name, tool_args, ctx, tool)
        if isinstance(result, ToolFailureWithDiagnostic):
            return await result.report(ctx)
        return result


@dataclass
class _StopCheckedToolset(WrapperToolset[None]):
    """
    Checks the run is still going before each call, so no tool starts after Stop
    or a lost lease, which the lease renewal alone notices only seconds later. A
    refused call is recorded as not run.
    """

    raise_if_stopping: Callable[[], Awaitable[None]]
    not_run: Callable[[str], None]

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[None],
        tool: ToolsetTool[None],
    ) -> Any:
        try:
            await self.raise_if_stopping()
        except asyncio.CancelledError:
            self.not_run(ctx.tool_call_id)
            raise
        return await super().call_tool(name, tool_args, ctx, tool)


@dataclass
class _HeldMCPCallsToolset(WrapperToolset[None]):
    """
    Holds the calls to an MCP server's tools that wait for approval. The owner
    decides on the call's arguments, credentials masked: the server's tools are
    only known by the description it gave.
    """

    is_held: Callable[[RunContext[None]], bool]

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[None],
        tool: ToolsetTool[None],
    ) -> Any:
        if not ctx.tool_call_approved and self.is_held(ctx):
            if preview := arguments_preview(tool_args):
                await ctx.emit(ToolCallInputEvent(input=preview))
            raise ApprovalRequired()
        result = await super().call_tool(name, tool_args, ctx, tool)
        if isinstance(result, ToolFailureWithDiagnostic):
            return await result.report(ctx)
        return result


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
        self._result: AgentRunResult[str | DeferredToolRequests] | None = None
        self._web_search_tool: WebSearchTool | None = None
        # Fetched by Baserow rather than the provider, so every model can use it.
        self._web_fetch_tool = web_fetch_tool() if request.web_fetch_enabled else None
        self._ask_person_tool = ask_person_tool() if request.may_ask_person else None
        self._response_calls: list[ToolCallPart] = []
        self._tool_errors: dict[str, str] = {}
        self._invalid_call_ids: set[str] = set()
        self._mcp_toolsets = [
            MCPServerToolset(server) for server in request.mcp_servers
        ]
        resume = request.resume
        self._tools = {
            name: agent_tool_type_registry.get(name)
            for name in request.allowed_tool_names
        }
        self._tools.update({tool.type: tool for tool in request.action_tools})
        self._steps = (
            ChatRunSteps(journal, self._describe_call)
            if resume is None
            else ChatRunSteps(
                journal,
                self._describe_call,
                resume.saved_steps,
                resume.held_step_ids,
                resume.approved_ids,
            )
        )

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
        if name == WebSearchTool.kind or (
            self._web_fetch_tool is not None and name == self._web_fetch_tool.name
        ):
            return {"changes_data": False, "input": _web_search_step_input(arguments)}
        if name == ASK_PERSON_TOOL_NAME and self._ask_person_tool is not None:
            question = arguments.get("question")
            # Its step is where a person reads the question, so it's kept whole.
            return {
                "changes_data": False,
                "input": {
                    "question": remove_unstorable_characters(question)
                    if isinstance(question, str)
                    else None
                },
            }
        if name not in self._tools:
            return None
        tool = self._tools[name]
        try:
            summary = tool.get_step_input(arguments)
        except Exception as exc:
            logger.error(
                "Agent tool {} step input failed ({})", tool.type, describe_failure(exc)
            )
            summary = {}
        description = {"changes_data": tool.changes_data, "input": summary}
        if isinstance(tool, BoundActionTool):
            description["presentation_type"] = tool.presentation_type
        return description

    async def answer(self) -> ChatRunOutcome:
        """
        Answer until the model finishes or the journal asks the run to stop.

        :return: How the reply ended, with its text and the model's transcript.
        """

        self._steps.start()
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
        Combine saved instructions with who this reply answers and acts as, its
        workspace access, trigger or channel, whether anyone reads it as it's
        written, and web context.

        :param web_search_tool: The web search this attempt offers, if any.
        :return: The instructions.
        """

        request = self._request
        instructions = request.instructions
        if request.conversation_user is not None:
            instructions += "\n\n" + CONVERSATION_USER_INSTRUCTIONS.format(
                name=request.conversation_user.name,
                user_id=request.conversation_user.id,
            )
        if request.acting_subject is not None:
            instructions += "\n\n" + RUN_AS_IDENTITY_INSTRUCTIONS.format(
                name=one_line_name(request.acting_subject),
                user_id=request.acting_subject.id,
            )
        if request.names_senders:
            instructions += f"\n\n{SHARED_CONVERSATION_INSTRUCTIONS}"
        if request.run_as_unavailable:
            instructions += "\n\n" + (
                VISITOR_UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS
                if request.started_by_channel
                else UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS
            )
        if request.started_by_trigger:
            instructions += f"\n\n{TRIGGER_CONVERSATION_INSTRUCTIONS}"
        if request.started_by_channel:
            instructions += f"\n\n{VISITOR_CONVERSATION_INSTRUCTIONS}"
        if request.unattended:
            trigger = (
                f'The trigger "{request.trigger_name}"'
                if request.trigger_name
                else "A trigger"
            )
            instructions += "\n\n" + UNATTENDED_REPLY_INSTRUCTIONS.format(
                trigger=trigger
            )
            instructions += "\n\n" + (
                UNATTENDED_ASK_PERSON_INSTRUCTIONS
                if request.may_ask_person
                else UNATTENDED_NO_PERSON_INSTRUCTIONS
            )
        if (
            request.resume is not None
            or (request.allowed_tool_names and request.ask_first_tool_names)
            or any(tool.ask_first for tool in request.action_tools)
            or any(
                tool.ask_first
                for server in request.mcp_servers
                for tool in server.tools
            )
        ):
            instructions += "\n\n" + (
                VISITOR_ASK_FIRST_INSTRUCTIONS
                if request.started_by_channel
                else ASK_FIRST_INSTRUCTIONS
            )
        if web_search_tool is not None:
            instructions += f"\n\n{WEB_SEARCH_INSTRUCTIONS}"
        elif request.web_search_tool is not None:
            instructions += f"\n\n{WEB_SEARCH_FAILED_INSTRUCTIONS}"
        elif request.web_search_enabled:
            instructions += f"\n\n{WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS}"
        if self._web_fetch_tool is not None:
            instructions += f"\n\n{WEB_FETCH_INSTRUCTIONS}"
        return "\n\n".join(
            filter(None, [instructions, *request.unavailable_tool_messages])
        )

    @cached_property
    def _model_type(self) -> GenerativeAIModelType:
        return generative_ai_model_type_registry.get(self._request.provider_type)

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
                    or self._model_type.get_provider_failure(exc) is not None
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

        self._web_search_tool = web_search_tool
        request = self._request
        validator = self._model_type.get_output_validator(request.model_identifier)
        retries = {"tools": TOOL_RETRIES}
        if validator is not None:
            retries["output"] = OUTPUT_RETRIES
        agent = Agent(
            instructions=self._get_instructions(web_search_tool),
            output_type=[str, DeferredToolRequests],
            retries=retries,
            capabilities=[
                WebSearch(native=partial(self._offered_web_search, web_search_tool))
            ]
            if web_search_tool
            else [],
        )
        # Kuma enables content tracing for every Agent; conversations are private.
        agent.instrument = False
        if validator is not None:
            agent.output_validator(partial(self._validate_output, validator))
        resume = request.resume
        # A paused run carries its own history, and pydantic-ai refuses both.
        history = (
            build_history(request.history, request.names_senders)
            if resume is None
            else None
        )
        prompt = (
            None
            if request.prompt is None
            else get_prompt_content(request.prompt, request.names_senders)
        )
        async with agent.run_stream_events(
            prompt,
            conversation=resume.paused_conversation if resume else None,
            message_history=history,
            deferred_tool_results=resume.deferred_tool_results if resume else None,
            model=self._model,
            model_settings=self._model_settings,
            usage_limits=UsageLimits(request_limit=REPLY_REQUEST_LIMIT),
            toolsets=self._toolsets(),
        ) as events:
            async for event in events:
                self._on_event(event)

    async def _validate_output(
        self,
        validator: ModelOutputValidator,
        ctx: RunContext,
        output: str | DeferredToolRequests,
    ) -> str | DeferredToolRequests:
        """Correct printed tool calls within the run and discard rejected text."""

        if not isinstance(output, str):
            return output
        try:
            return validator(ctx, output)
        except ModelRetry:
            # This text already streamed, but is not an answer. Clear it even
            # when retries are exhausted; completed tool steps stay visible.
            self._parts = {}
            self._text = ""
            self._text_is_commentary = False
            self._stream_text()
            raise

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

    def _toolsets(self) -> list[AbstractToolset[None]]:
        """
        The tools the reply may call: Baserow's, acting as the Agent's identity,
        web fetch when it's turned on, the question to a person when the reply may
        ask one, and those turned on for its MCP servers.

        :return: The toolsets, none when the reply may call no tool.
        """

        request = self._request
        toolsets: list[AbstractToolset[None]] = []
        if self._tools:
            ctx = ToolContext(
                user=request.acting_subject,
                workspace=request.workspace,
                timezone=request.timezone,
            )
            toolsets.append(
                _HeldCallsToolset(
                    FunctionToolset(
                        [tool.get_tool(ctx) for tool in self._tools.values()]
                    ),
                    self._is_held,
                    ctx,
                    self._tools,
                )
            )
        if self._web_fetch_tool is not None:
            toolsets.append(FunctionToolset([self._web_fetch_tool]))
        if self._ask_person_tool is not None:
            toolsets.append(FunctionToolset([self._ask_person_tool]))
        return [
            _StopCheckedToolset(
                toolset, self._journal.raise_if_stopping, self._steps.not_run
            )
            for toolset in [
                *toolsets,
                *(
                    _HeldMCPCallsToolset(toolset, self._is_held)
                    for toolset in self._mcp_toolsets
                ),
            ]
        ]

    def _is_held(self, ctx: RunContext[None]) -> bool:
        """
        Decide whether a call waits for the owner's approval.

        :param ctx: The run, with the response that made the call.
        :return: Whether the call is held.
        """

        response = next(
            message
            for message in reversed(ctx.messages)
            if isinstance(message, ModelResponse)
        )
        return ctx.tool_call_id in self._held_call_ids(response.tool_calls)

    def _held_call_ids(self, calls: Iterable[ToolCallPart]) -> set[str]:
        """
        Hold the ask first calls and questions of a model response, and the changes
        after a held call, so that changes still run in the order the model asked
        for them. A call with invalid arguments is retried instead, so it holds
        nothing.

        :param calls: The calls of one model response, in order.
        :return: The ids of its held calls.
        """

        request = self._request
        held: set[str] = set()
        for call in calls:
            if call.tool_call_id in self._invalid_call_ids:
                continue
            if tool := self._tools.get(call.tool_name):
                changes_data = tool.changes_data
                ask_first = call.tool_name in request.ask_first_tool_names or (
                    isinstance(tool, BoundActionTool) and tool.ask_first
                )
            elif snapshot := self._mcp_tool(call.tool_name):
                changes_data, ask_first = snapshot.changes_data, snapshot.ask_first
            elif (
                call.tool_name == ASK_PERSON_TOOL_NAME
                and self._ask_person_tool is not None
            ):
                changes_data, ask_first = False, True
            else:
                continue
            if ask_first or (held and changes_data):
                held.add(call.tool_call_id)
        return held

    def _mcp_tool(self, name: str) -> MCPToolSnapshot | None:
        """
        :param name: A called tool's name.
        :return: The MCP tool the reply offers under that name, if any.
        """

        for toolset in self._mcp_toolsets:
            if snapshot := toolset.get_tool_snapshot(name):
                return snapshot
        return None

    def _action_tool(self, name: str) -> BoundActionTool | None:
        """
        :param name: A called tool's name.
        :return: The action the reply offers under that name, if any.
        """

        tool = self._tools.get(name)
        return tool if isinstance(tool, BoundActionTool) else None

    def _on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """
        Stream the text of the model's latest response and keep the final result.

        :param event: An event of the run.
        """

        if isinstance(event, PartStartEvent) and event.index == 0:
            self._response_calls = []
            self._invalid_call_ids = set()
        elif isinstance(event, PartEndEvent) and isinstance(event.part, ToolCallPart):
            self._response_calls.append(event.part)
        if isinstance(event, ToolCallDiagnosticEvent):
            if step_id := self._steps.pending_step_id(event.tool_call_id):
                self._tool_errors[step_id] = event.message
            return
        waiting = False
        if isinstance(event, FunctionToolCallEvent):
            # Each call is validated before its event, and none runs before the last.
            if event.args_valid is False:
                self._invalid_call_ids.add(event.tool_call_id)
            waiting = event.tool_call_id in self._held_call_ids(self._response_calls)
        self._steps.on_event(event, waiting=waiting)
        match event:
            case AgentRunResultEvent(result=result):
                self._result = result
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
        self._stream_text()

    @property
    def _holds_text(self) -> bool:
        """
        :return: Whether the text stays out of the stream until the reply ends. A
            visitor reads the stream, and what a reply writes before it calls a
            tool isn't its answer and can't be told from it while it arrives.
        """

        return self._request.started_by_channel and bool(
            self._tools
            or self._mcp_toolsets
            or self._web_fetch_tool
            or self._web_search_tool
        )

    def _stream_text(self) -> None:
        if not self._holds_text:
            self._journal.emit_text(self._text)

    def _outcome(self, work: asyncio.Task) -> ChatRunOutcome:
        result = self._reply_result()
        # A blank answer is no reply, and some providers reject it in the history.
        if result.paused or (self._result is not None and result.text.strip()):
            return ChatRunOutcome(ChatRunStatus.COMPLETED, result=result)
        if self._journal.stop_reason == ChatRunStopReason.CANCELLED:
            return ChatRunOutcome(ChatRunStatus.CANCELLED, result=result)
        if self._journal.stop_reason == ChatRunStopReason.TIMEOUT:
            return ChatRunOutcome(
                ChatRunStatus.FAILED, ChatRunErrorCode.TIMEOUT, result
            )
        error = None if work.cancelled() else work.exception()
        if isinstance(error, AIUsageLimitExceeded):
            return ChatRunOutcome(
                ChatRunStatus.FAILED, AGENT_USAGE_LIMIT_EXCEEDED, result
            )
        if error is not None:
            logger.error(
                "Agent reply {} failed: run_id={}, provider={!r}, model={!r}, {}",
                self._request.reply_id,
                self._journal.run.id,
                self._request.provider_type[:128],
                self._request.model_identifier[:128],
                describe_failure(error),
            )
        return ChatRunOutcome(
            ChatRunStatus.FAILED, self._failure_error_code(error), result
        )

    def _failure_error_code(self, error: BaseException | None) -> str:
        """
        :param error: What ended the reply, if anything was raised.
        :return: The provider's failure when it names one, else a plain failure.
        """

        if error is None:
            return ChatRunErrorCode.FAILED
        return self._model_type.get_provider_failure(error) or ChatRunErrorCode.FAILED

    def _reply_result(self) -> AgentReplyResult:
        """
        Collect what the reply produced: its text, the provider and model, and once
        the model finished or paused, its messages and usage. A paused reply keeps
        the text the owner saw, the held calls and the run to resume. A reply
        holding its text keeps only its final answer.

        :return: The text and the execution details of the reply.
        """

        paused = self._result is not None and isinstance(
            self._result.output, DeferredToolRequests
        )
        steps = self._steps.finish() or None
        waiting_calls = self._steps.waiting_calls() if paused else []
        unfinished_text = "" if self._holds_text else self._text
        if self._result is None:
            return AgentReplyResult(
                text=unfinished_text,
                provider_type=self._request.provider_type,
                model_identifier=self._request.model_identifier,
                steps=steps,
                tool_errors=self._tool_errors,
            )
        return AgentReplyResult(
            text=unfinished_text
            if paused
            else remove_null_characters(self._result.output),
            provider_type=self._request.provider_type,
            model_identifier=self._request.model_identifier,
            model_messages=ModelMessagesTypeAdapter.dump_python(
                self._result.new_messages(), mode="json"
            ),
            usage=to_jsonable_python(self._result.usage),
            steps=steps,
            tool_errors=self._tool_errors,
            waiting_calls=waiting_calls,
            tool_keys={
                call.tool_name: tool.approval_key
                for call in waiting_calls
                if (
                    tool := self._mcp_tool(call.tool_name)
                    or self._action_tool(call.tool_name)
                )
            },
            paused_run=AgentPausedRun(
                conversation=ConversationTypeAdapter.dump_python(
                    self._result.conversation, mode="json"
                ),
                web_search=self._web_search_tool is not None,
                web_fetch=self._web_fetch_tool is not None,
                run_as=self._request.acting_subject,
            )
            if paused
            else None,
        )
