from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, IntegrityError, transaction
from django.db.models import (
    Case,
    Count,
    Exists,
    Max,
    OuterRef,
    Prefetch,
    QuerySet,
    Value,
    When,
    prefetch_related_objects,
)
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from loguru import logger
from pydantic_ai import (
    Conversation,
    ConversationTypeAdapter,
    ToolApproved,
    ToolDenied,
    WebSearchTool,
)

from baserow.contrib.integrations.mcp.exceptions import MCPServerNotConnected
from baserow.contrib.integrations.mcp.handler import MCPServerHandler
from baserow.contrib.integrations.mcp.models import (
    MCPAuthType,
    MCPServerIntegration,
    MCPServerTool,
)
from baserow.contrib.integrations.mcp.toolset import MCPServerSnapshot
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.chat_runs.constants import ChatRunErrorCode, ChatRunStepStatus
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import (
    ACTIVE_CHAT_RUN_STATUSES,
    ChatRun,
    ChatRunStatus,
)
from baserow.core.chat_runs.steps import end_waiting_steps, stop_running_steps
from baserow.core.chat_runs.types import ChatRunStep
from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.generative_ai.exceptions import GenerativeAITypeDoesNotExist
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import subject_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.core.types import Subject
from baserow.core.utils import extract_allowed, remove_unstorable_characters

from .constants import (
    AGENT_RUN_TYPE,
    DISALLOWED_TOOL_CALL_NOTE,
    HISTORY_MESSAGE_LIMIT,
    MCP_TOOL_CHANGED_CALL_NOTE,
    REJECTED_TOOL_CALL_NOTE,
    RUN_AS_LOST_TOOL_CALL_NOTE,
    RUN_AS_SUBJECT_TYPES,
    AgentConfigurationErrorCode,
    AgentReadinessState,
    AgentRunAsState,
)
from .exceptions import (
    AgentConversationDoesNotExist,
    AgentMessageConflict,
    AgentRunAsSubjectDoesNotExist,
    AgentToolApprovalNotPending,
)
from .models import (
    AgentAllowedTool,
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyStatus,
    AgentReplyTranscript,
    AgentToolApproval,
)
from .registries import agent_tool_type_registry
from .types import (
    AgentConfiguration,
    AgentConfigurationUpdated,
    AgentConversationCursor,
    AgentConversationUpdated,
    AgentMessageCreated,
    AgentPausedRun,
    AgentReplyRequest,
    AgentReplyResult,
    AgentReplyResume,
    AgentRunAsResolution,
    AgentToolConfiguration,
    AgentToolDecision,
)


def normalize_title(text: str) -> str:
    """Collapse whitespace so a title fits on one line, cut to the stored length."""

    max_length = AgentConversation._meta.get_field("title").max_length
    return " ".join(text.split())[:max_length]


class AgentHandler:
    configuration_fields = ["instructions", "provider_type", "model_identifier"]
    conversation_fields = ["title", "pinned"]
    run_as_fields = ["run_as_subject_type", "run_as_subject_id"]
    option_fields = ["web_search_enabled", "reasoning_effort"]

    def get_agent(self, agent_id: int, for_update: bool = False) -> AgentApplication:
        """
        Fetch an Agent that belongs to a workspace.

        :param agent_id: The id of the Agent.
        :param for_update: Whether to lock the Agent until the transaction ends.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist, is trashed or
            has no workspace.
        :return: The Agent.
        """

        # Snapshots keep workspace-less copies of applications. Exclude them because
        # editor permissions need a workspace scope.
        queryset = AgentApplication.objects.filter(workspace__isnull=False)
        if for_update:
            # Lock the parent first to match normal application updates.
            CoreHandler().get_application(
                agent_id,
                base_queryset=queryset.select_for_update(of=("application_ptr",)),
            )
            queryset = queryset.select_for_update(of=("self",))
        return CoreHandler().get_application(agent_id, base_queryset=queryset)

    def get_configuration(
        self,
        agent: AgentApplication,
        provider_state: ScopedAIProviderState | None = None,
    ) -> AgentConfiguration:
        """
        Return the configuration, its readiness and each blocking field error.

        :param agent: The Agent to read.
        :param provider_state: The AI provider state of the Agent's workspace, when
            the caller already loaded it.
        :return: The configuration values, the readiness and the error of
            each field that keeps the Agent from being ready.
        """

        readiness, errors = self.get_configuration_readiness(agent, provider_state)
        run_as = self.resolve_run_as_subject(
            agent.run_as_subject_type, agent.run_as_subject_id, agent.workspace
        )
        tools = self.get_tool_configuration(agent)
        with_tools = (
            run_as.status == AgentRunAsState.ACTIVE and bool(tools["allowed_tools"])
        ) or self.has_mcp_tools(agent)
        web_search_tool = self._get_web_search_tool(agent, with_tools)
        return AgentConfiguration(
            readiness=readiness,
            instructions=agent.instructions,
            provider_type=agent.provider_type,
            model_identifier=agent.model_identifier,
            reasoning_effort=agent.reasoning_effort,
            applied_reasoning_effort=(
                None if errors else self.get_applied_reasoning_effort(agent)
            ),
            run_as=run_as,
            **tools,
            web_search_enabled=agent.web_search_enabled,
            web_search_available=web_search_tool is not None,
            web_search_blocked_by_tools=web_search_tool is None
            and with_tools
            and self._get_web_search_tool(agent, False) is not None,
            errors=errors,
        )

    def get_applied_reasoning_effort(self, agent: AgentApplication) -> str | None:
        """
        Find the reasoning effort replies use with the Agent's model, which can
        differ from the chosen one when the model doesn't accept it.

        :param agent: An Agent with an available provider and model.
        :return: The effort replies send, or None when they use the model's
            default.
        """

        if not agent.reasoning_effort:
            return None
        model_type = generative_ai_model_type_registry.get(agent.provider_type)
        try:
            settings_override = model_type.get_model_settings_override(
                agent.model_identifier, agent.workspace
            )
            model = model_type.get_ai_model(
                agent.model_identifier, agent.workspace, settings_override
            )
        except Exception as exc:
            # Each provider raises its own error for incomplete settings.
            logger.warning(
                "Agent {} model could not be built ({})", agent.id, type(exc).__name__
            )
            return None
        return model_type.get_reasoning_effort(
            agent.model_identifier, model, agent.reasoning_effort
        )

    def _get_web_search_tool(
        self, agent: AgentApplication, with_function_tools: bool
    ) -> WebSearchTool | None:
        """
        Find the web search of the Agent's model, whether or not it's turned on.

        :param agent: The Agent.
        :param with_function_tools: Whether the reply also offers workspace or MCP
            tools.
        :return: The tool, or None when the model can't search the web.
        """

        if not agent.provider_type or not agent.model_identifier:
            return None
        try:
            model_type = generative_ai_model_type_registry.get(agent.provider_type)
        except GenerativeAITypeDoesNotExist:
            return None
        return model_type.get_web_search_tool(
            agent.model_identifier, with_function_tools
        )

    def get_configuration_readiness(
        self,
        agent: AgentApplication,
        provider_state: ScopedAIProviderState | None = None,
    ) -> tuple[AgentReadinessState, dict[str, AgentConfigurationErrorCode]]:
        """
        Evaluate chat readiness without resolving the optional workspace identity.

        :param agent: The Agent whose required configuration is evaluated.
        :param provider_state: The already-loaded provider state, if available.
        :return: The readiness and errors for the required configuration fields.
        """

        errors = {}
        for field in self.configuration_fields:
            if not (getattr(agent, field) or "").strip():
                errors[field] = AgentConfigurationErrorCode.REQUIRED

        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            agent.workspace,
            feature_type=AI_PROVIDER_FEATURE_AI_AGENT,
            state=provider_state,
        )
        if agent.provider_type:
            if agent.provider_type not in models:
                errors["provider_type"] = AgentConfigurationErrorCode.UNAVAILABLE
            if agent.model_identifier and agent.model_identifier not in models.get(
                agent.provider_type, []
            ):
                errors["model_identifier"] = AgentConfigurationErrorCode.UNAVAILABLE

        if AgentConfigurationErrorCode.REQUIRED in errors.values():
            readiness = AgentReadinessState.INCOMPLETE
        elif errors:
            readiness = AgentReadinessState.UNAVAILABLE
        else:
            readiness = AgentReadinessState.READY
        return readiness, errors

    def get_tool_configuration(self, agent: AgentApplication) -> AgentToolConfiguration:
        """
        Return the tools the Agent may call and those that wait for the owner's
        approval, leaving out tools no longer registered.

        :param agent: The Agent to read.
        :return: The allowed tool names and the ask first tool names, in registry
            order. An unavailable selected identity retains its settings, but no
            selected identity means tools are off.
        """

        if not agent.run_as_subject_type or not agent.run_as_subject_id:
            return {"allowed_tools": [], "ask_first_tools": []}
        ask_first = dict(agent.allowed_tools.values_list("name", "ask_first"))
        allowed_tools = [
            name for name in agent_tool_type_registry.get_types() if name in ask_first
        ]
        return {
            "allowed_tools": allowed_tools,
            "ask_first_tools": [name for name in allowed_tools if ask_first[name]],
        }

    def set_allowed_tools(
        self,
        agent: AgentApplication,
        names: list[str],
        ask_first_names: list[str] | None = None,
    ) -> None:
        """
        Let the Agent call exactly these tools.

        :param agent: The Agent to update.
        :param names: Registered tool names.
        :param ask_first_names: The allowed tools that wait for the owner's
            approval. When None, tools that stay allowed keep their setting and
            newly allowed tools ask first when they change data.
        """

        agent.allowed_tools.exclude(name__in=names).delete()
        AgentAllowedTool.objects.bulk_create(
            [
                AgentAllowedTool(
                    agent=agent,
                    name=name,
                    ask_first=agent_tool_type_registry.get(name).changes_data,
                )
                for name in names
            ],
            ignore_conflicts=True,
        )
        if ask_first_names is not None:
            # A Q over an empty list makes Django skip the whole update.
            agent.allowed_tools.update(
                ask_first=Case(
                    When(name__in=ask_first_names, then=Value(True)),
                    default=Value(False),
                )
            )

    def stop_asking_first(
        self, agent: AgentApplication, tool_names: Iterable[str]
    ) -> list[str]:
        """
        Let allowed tools run without waiting for the owner's approval.

        :param agent: The Agent, locked like for a configuration update.
        :param tool_names: The tools to stop asking first. Those that aren't allowed
            or don't ask first are skipped.
        :return: The names of the tools that stopped asking first, in registry
            order.
        """

        requested = set(tool_names)
        stopped = [
            name
            for name in self.get_tool_configuration(agent)["ask_first_tools"]
            if name in requested
        ]
        if stopped:
            agent.allowed_tools.filter(name__in=stopped).update(ask_first=False)
            agent.save(update_fields=["updated_on"])
        return stopped

    def get_run_as_subject(
        self,
        subject_type: str | None,
        subject_id: int | None,
        include_trash: bool = False,
    ) -> Subject | None:
        """
        Resolve the subject an Agent runs as from its stored type and id.

        :param subject_type: The stored subject type, or None.
        :param subject_id: The stored subject id, or None.
        :param include_trash: Whether a trashed subject is returned, only to report
            why the Agent can't use it.
        :return: The subject, or None when none is set or it no longer exists.
        """

        if not subject_type or subject_id is None:
            return None
        try:
            return subject_type_registry.get_subject(
                subject_type, subject_id, include_trash=include_trash
            )
        except SubjectTypeNotExist:
            return None

    def resolve_run_as_subject(
        self,
        subject_type: str | None,
        subject_id: int | None,
        workspace: Workspace | None,
    ) -> AgentRunAsResolution:
        """
        Resolve a saved identity without confusing unavailable access with no access.

        :param subject_type: The saved subject type, or None.
        :param subject_id: The saved subject id, or None.
        :param workspace: The Agent's workspace.
        :return: The explicit availability state. Only allowed subjects from this
            workspace carry their object and name, including recoverable trash.
        """

        if subject_type is None and subject_id is None:
            return AgentRunAsResolution(AgentRunAsState.UNSET, subject_type, subject_id)
        missing = AgentRunAsResolution(
            AgentRunAsState.MISSING, subject_type, subject_id
        )
        if (
            subject_type not in RUN_AS_SUBJECT_TYPES
            or subject_id is None
            or workspace is None
            or workspace.trashed
        ):
            return missing
        subject = self.get_run_as_subject(subject_type, subject_id, include_trash=True)
        if subject is None:
            return missing
        registered_type = subject_type_registry.get(subject_type)
        if not registered_type.is_in_workspace(subject, workspace, include_trash=True):
            return missing
        return AgentRunAsResolution(
            AgentRunAsState.TRASHED
            if getattr(subject, "trashed", False)
            else AgentRunAsState.ACTIVE,
            subject_type,
            subject_id,
            subject,
            registered_type.get_display_name(subject),
        )

    def get_usable_run_as_subject(
        self, subject_type: str | None, subject_id: int | None, workspace: Workspace
    ) -> Subject | None:
        """
        Return the subject if an Agent in the workspace may act as it.

        :param subject_type: The subject type.
        :param subject_id: The subject id.
        :param workspace: The workspace of the Agent.
        :return: The subject, or None if its saved reference is not active.
        """

        resolution = self.resolve_run_as_subject(subject_type, subject_id, workspace)
        return (
            resolution.subject if resolution.status == AgentRunAsState.ACTIVE else None
        )

    def update_configuration(
        self, agent: AgentApplication, **values: str | int | list[str] | None
    ) -> AgentConfigurationUpdated:
        """
        Save part of the configuration, accepting blank values as a draft.

        :param agent: The Agent to update.
        :param values: The configuration values to set, by field name,
            ``allowed_tools``, the names of all the tools the Agent may call, and
            ``ask_first_tools``, those of them that wait for the owner's approval.
            The caller must validate their types, lengths and tool names
            beforehand, and pass the run-as type and id together and
            ``ask_first_tools`` only with ``allowed_tools``. Clearing the identity
            clears tools; without a selected identity, submitted tools remain off.
            Unknown field names are ignored.
        :raises AgentRunAsSubjectDoesNotExist: When the Agent can't act as the
            given subject.
        :return: The Agent, its original and new configuration values, and the
            resolved resulting configuration.
        """

        allowed_tools = values.get("allowed_tools")
        had_run_as = bool(agent.run_as_subject_type and agent.run_as_subject_id)
        ask_first_tools = values.get("ask_first_tools")
        allowed_fields = [
            *self.configuration_fields,
            *self.run_as_fields,
            *self.option_fields,
        ]
        values = extract_allowed(values, allowed_fields)
        run_as = [values.get(field) for field in self.run_as_fields]
        if any(run_as) and not self.get_usable_run_as_subject(*run_as, agent.workspace):
            raise AgentRunAsSubjectDoesNotExist()
        original_values = {
            **{field: getattr(agent, field) for field in allowed_fields},
            **self.get_tool_configuration(agent),
        }
        changed_fields = []
        for field, value in values.items():
            if field in ("provider_type", "model_identifier", "reasoning_effort"):
                value = (value or "").strip() or None
            if getattr(agent, field) != value:
                setattr(agent, field, value)
                changed_fields.append(field)
        has_run_as = bool(agent.run_as_subject_type and agent.run_as_subject_id)
        if not has_run_as or (not had_run_as and allowed_tools is None):
            # No workspace access deliberately turns tools off. Selecting an
            # identity later must not reactivate old default tool rows.
            allowed_tools, ask_first_tools = [], None
        tools_changed = allowed_tools is not None and (
            set(allowed_tools) != set(original_values["allowed_tools"])
            or (
                ask_first_tools is not None
                and set(ask_first_tools) != set(original_values["ask_first_tools"])
            )
        )
        if changed_fields or tools_changed:
            agent.save(update_fields=[*changed_fields, "updated_on"])
        if tools_changed or not has_run_as or not had_run_as:
            self.set_allowed_tools(agent, allowed_tools, ask_first_tools)
        configuration = self.get_configuration(agent)
        return AgentConfigurationUpdated(
            agent=agent,
            original_values=original_values,
            new_values={
                **{field: getattr(agent, field) for field in allowed_fields},
                "allowed_tools": configuration.allowed_tools,
                "ask_first_tools": configuration.ask_first_tools,
            },
            configuration=configuration,
        )

    def list_conversations(
        self,
        agent: AgentApplication,
        owner: AbstractUser,
        cursor: AgentConversationCursor | None = None,
        pinned: bool | None = None,
        has_pending_approvals: bool | None = None,
    ) -> QuerySet[AgentConversation]:
        """
        Return the owner's conversations with the agent.

        :param agent: The agent the conversations belong to.
        :param owner: The user whose conversations are returned.
        :param cursor: The last conversation of the previous page, to continue after.
        :param pinned: Only pinned or unpinned conversations, or both when omitted.
        :param has_pending_approvals: Only conversations with or without pending calls.
        :return: The owner's conversations, pinned first, then most recently active.
        """

        conversations = AgentConversation.objects.filter(agent=agent, owner_user=owner)
        if pinned is not None:
            conversations = conversations.filter(pinned=pinned)
        if has_pending_approvals is not None:
            pending = Exists(
                self._pending_approvals().filter(reply__conversation_id=OuterRef("pk"))
            )
            conversations = conversations.filter(
                pending if has_pending_approvals else ~pending
            )
        if cursor is not None:
            conversations = conversations.filter(cursor.get_filter("updated_on"))
        return conversations

    def get_conversation(
        self,
        agent: AgentApplication,
        owner: AbstractUser,
        uuid: UUID,
        for_update: bool = False,
    ) -> AgentConversation:
        """
        Return one of the owner's conversations with the agent.

        :param agent: The agent the conversation belongs to.
        :param owner: The user who owns the conversation.
        :param uuid: The uuid of the conversation.
        :param for_update: Whether to lock the conversation until the transaction ends.
        :raises AgentConversationDoesNotExist: When the conversation doesn't exist,
            also when it belongs to another owner or agent.
        :return: The conversation, with the agent and the owner it was found for.
        """

        queryset = AgentConversation.objects.all()
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            conversation = queryset.get(uuid=uuid, agent=agent, owner_user=owner)
        except AgentConversation.DoesNotExist as exc:
            raise AgentConversationDoesNotExist from exc
        conversation.agent, conversation.owner_user = agent, owner
        return conversation

    def update_conversation(
        self, conversation: AgentConversation, **values: str | bool
    ) -> AgentConversationUpdated:
        """
        Update a conversation's own values without changing its last activity time.

        :param conversation: The conversation to update.
        :param values: The values to set, by field name. A title is normalized like
            a first message's. Unknown field names are ignored.
        :return: The conversation with the original and new values of the fields
            that changed.
        """

        values = extract_allowed(values, self.conversation_fields)
        if "title" in values:
            values["title"] = normalize_title(values["title"])
        new_values = {
            field: value
            for field, value in values.items()
            if value != getattr(conversation, field)
        }
        original_values = {field: getattr(conversation, field) for field in new_values}
        for field, value in new_values.items():
            setattr(conversation, field, value)
        if new_values:
            conversation.save(update_fields=list(new_values))
        return AgentConversationUpdated(conversation, original_values, new_values)

    def delete_conversation(
        self, user: AbstractUser, conversation: AgentConversation
    ) -> None:
        """
        Trash a conversation and stop the reply still being written in it.

        :param user: The user deleting the conversation.
        :param conversation: The conversation, locked so no new reply can start.
        """

        agent = conversation.agent
        TrashHandler.trash(user, agent.workspace, agent, conversation)
        run = ChatRunHandler().get_active_run(AGENT_RUN_TYPE, conversation.id)
        if run is not None:
            # Runs are locked before their conversation, so stop it after commit.
            transaction.on_commit(
                lambda: ChatRunHandler().request_cancel(run.id), robust=True
            )

    def get_creation_retry(
        self,
        agent: AgentApplication,
        owner: AbstractUser,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated | None:
        """
        Return the first message already accepted for a conversation uuid.

        :param agent: The agent the conversation is created in.
        :param owner: The user creating the conversation.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :raises AgentConversationDoesNotExist: When the uuid belongs to another
            owner's or agent's conversation, or to a deleted one.
        :raises AgentMessageConflict: When the conversation was created with another
            first message.
        :return: The conversation, its first message, its reply and the run writing
            it, or None when nothing was accepted with this uuid before.
        """

        conversation = AgentConversation.objects_and_trash.filter(uuid=uuid).first()
        if conversation is None:
            return None
        return self._get_first_message_retry(
            conversation, agent, owner, message_uuid, content
        )

    def _get_first_message_retry(
        self,
        conversation: AgentConversation,
        agent: AgentApplication,
        owner: AbstractUser,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Validate an existing identifier, also one a racing request just created."""

        if (
            conversation.trashed
            or conversation.agent_id != agent.id
            or conversation.owner_user_id != owner.id
        ):
            raise AgentConversationDoesNotExist
        message = conversation.messages.order_by("id").first()
        if (
            message is None
            or message.uuid != message_uuid
            or message.content != content
        ):
            raise AgentMessageConflict
        return self._accepted(conversation, message)

    def _accepted(
        self, conversation: AgentConversation, message: AgentMessage
    ) -> AgentMessageCreated:
        """
        Return an already accepted message with the reply created right after it,
        and the run still writing that reply. The run is read first: a run's end
        saves its reply in the same transaction, so the reply read next is never
        still running without its run.

        :param conversation: The conversation of the message.
        :param message: The accepted message.
        :return: The conversation, the message, its reply, the run writing that reply
            and the conversation's current run.
        """

        runs = self.get_active_reply_runs(conversation)
        reply = conversation.messages.filter(id__gt=message.id).order_by("id").first()
        if reply is not None and reply.role != AgentMessage.Role.ASSISTANT:
            reply = None
        run_id = runs.get(reply.id) if reply else None
        return AgentMessageCreated(
            conversation,
            message,
            reply,
            run_id=run_id,
            conversation_run_id=next(iter(runs.values()), None),
            created=False,
        )

    def create_conversation(
        self,
        agent: AgentApplication,
        user: AbstractUser,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """
        Create a private conversation, titled after its first message.

        :param agent: The agent to create the conversation in.
        :param user: The user who owns the conversation.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :raises AgentConversationDoesNotExist: When a concurrent request created a
            conversation with this uuid for another owner or agent.
        :raises AgentMessageConflict: When a concurrent request created it with
            another first message.
        :return: The conversation, its first message and its reply, and whether they
            are new.
        """

        try:
            with transaction.atomic():
                conversation = AgentConversation.objects.create(
                    uuid=uuid,
                    agent=agent,
                    owner_user=user,
                    title=normalize_title(content),
                )
        except IntegrityError:
            # A concurrent request created this uuid after the retry check.
            return self._get_first_message_retry(
                AgentConversation.objects_and_trash.get(uuid=uuid),
                agent,
                user,
                message_uuid,
                content,
            )
        return self._add_message(conversation, message_uuid, content)

    def get_message_retry(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated | None:
        """
        Return the message already accepted for a message uuid.

        :param conversation: The conversation the message is sent to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :return: The conversation, the accepted message, its reply and the run
            writing it, or None when nothing was accepted with this uuid before.
        """

        message = conversation.messages.filter(uuid=uuid).first()
        if message is None:
            return None
        if message.content != content:
            raise AgentMessageConflict
        return self._accepted(conversation, message)

    def create_message(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated:
        """
        Add a user message with an empty reply, and start the run writing it.

        Call it in the transaction that checked the message, so a refused reply
        saves nothing.

        :param conversation: The conversation to add the message to.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :return: The conversation, the new message, its reply and the run writing
            it.
        """

        conversation.save(update_fields=["updated_on"])
        return self._add_message(conversation, uuid, content)

    def _add_message(
        self, conversation: AgentConversation, uuid: UUID, content: str
    ) -> AgentMessageCreated:
        """Add the message and its empty reply, and start the run writing it."""

        message = AgentMessage.objects.create(
            conversation=conversation, uuid=uuid, content=content
        )
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
            status=ChatRunStatus.RUNNING,
        )
        run = self._start_reply_run(conversation, reply)
        return AgentMessageCreated(
            conversation,
            message,
            reply,
            run_id=run.id,
            conversation_run_id=run.id,
            created=True,
        )

    def _start_reply_run(
        self, conversation: AgentConversation, reply: AgentMessage
    ) -> ChatRun:
        """Start the run writing the reply, for the conversation's owner."""

        return ChatRunHandler().start_run(
            AGENT_RUN_TYPE,
            conversation.id,
            conversation.agent.workspace,
            conversation.owner_user,
            context={"reply_id": reply.id},
            created_event_data={},
        )

    def get_waiting_reply(self, conversation: AgentConversation) -> AgentMessage | None:
        """
        Return the conversation's latest reply if it waits for the owner to decide
        its held calls.

        :param conversation: The conversation to look at.
        :return: The waiting reply, with its conversation, or None.
        """

        reply = conversation.messages.filter(role=AgentMessage.Role.ASSISTANT).first()
        if reply is None or reply.status != AgentReplyStatus.WAITING:
            return None
        return reply

    def _pending_approvals(self) -> QuerySet[AgentToolApproval]:
        """
        :return: The held calls waiting for their conversation owner's decision.
        """

        return AgentToolApproval.objects.filter(status=AgentToolApproval.Status.PENDING)

    def get_conversation_pending_approval_counts(
        self, conversation_ids: list[int]
    ) -> dict[int, int]:
        """
        :param conversation_ids: The ids of the conversations to count in.
        :return: The number of held calls waiting for the owner's decision by
            conversation id, leaving out conversations with none.
        """

        return dict(
            self._pending_approvals()
            .filter(reply__conversation_id__in=conversation_ids)
            .values("reply__conversation_id")
            .annotate(count=Count("id"))
            .values_list("reply__conversation_id", "count")
        )

    def conversation_has_pending_approvals(self, conversation_id: int) -> bool:
        """
        Check whether a conversation contributes to its owner's pending count.

        :param conversation_id: The conversation, including one being restored.
        :return: Whether any of its tool calls still needs a decision.
        """

        return (
            self._pending_approvals()
            .filter(reply__conversation_id=conversation_id)
            .exists()
        )

    def get_pending_approval_counts(
        self, user_ids: list[int], agent_ids: list[int]
    ) -> dict[int, dict[int, int]]:
        """
        Count the held calls waiting for each user's decision in their untrashed
        conversations with each Agent.

        :param user_ids: The ids of the users who own the conversations.
        :param agent_ids: The ids of the Agents to count in.
        :return: The number of pending approvals by Agent id, by user id, leaving
            out users and Agents with none.
        """

        counts: dict[int, dict[int, int]] = defaultdict(dict)
        for user_id, agent_id, count in (
            self._pending_approvals()
            .filter(
                reply__conversation__owner_user_id__in=user_ids,
                reply__conversation__agent_id__in=agent_ids,
                reply__conversation__trashed=False,
            )
            .values(
                "reply__conversation__owner_user_id", "reply__conversation__agent_id"
            )
            .annotate(count=Count("id"))
            .values_list(
                "reply__conversation__owner_user_id",
                "reply__conversation__agent_id",
                "count",
            )
        ):
            counts[user_id][agent_id] = count
        return dict(counts)

    def decide_approvals(
        self,
        conversation: AgentConversation,
        user: AbstractUser,
        decisions: list[AgentToolDecision],
    ) -> tuple[AgentMessage, list[AgentToolApproval], bool]:
        """
        Save the owner's decisions on held calls of the conversation's waiting reply.

        :param conversation: The conversation, locked so its reply can't change.
        :param user: The user deciding.
        :param decisions: Whether each held call may run, by approval id, with the
            reason for a rejection.
        :raises AgentToolApprovalNotPending: When an approval is decided already or
            isn't held by the reply waiting in the conversation.
        :return: The reply with its approvals, the approvals just decided, and
            whether all of them are decided.
        """

        reply = self.get_waiting_reply(conversation)
        if reply is None:
            raise AgentToolApprovalNotPending
        pending = {
            approval.id: approval
            for approval in AgentToolApproval.objects.select_for_update().filter(
                reply=reply, status=AgentToolApproval.Status.PENDING
            )
        }
        if not {decision["id"] for decision in decisions} <= pending.keys():
            raise AgentToolApprovalNotPending
        decided_on = timezone.now()
        decided = []
        for decision in decisions:
            approval = pending.pop(decision["id"])
            approval.status = (
                AgentToolApproval.Status.APPROVED
                if decision["approved"]
                else AgentToolApproval.Status.REJECTED
            )
            approval.reason = decision.get("reason", "")
            approval.decided_by = user
            approval.decided_on = decided_on
            decided.append(approval)
        AgentToolApproval.objects.bulk_update(
            decided, ["status", "reason", "decided_by", "decided_on"]
        )
        prefetch_related_objects([reply], "approvals")
        return reply, decided, not pending

    def resume_reply(self, reply: AgentMessage) -> ChatRun:
        """
        Start the run continuing a reply whose held calls are all decided.

        Call it in the transaction that saved the last decision, so a refused run
        leaves the decisions pending.

        :param reply: The waiting reply, with its conversation, agent and owner.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The run continuing the reply.
        """

        conversation = reply.conversation
        conversation.save(update_fields=["updated_on"])
        reply.status = AgentReplyStatus.RUNNING
        reply.save(update_fields=["status", "updated_on"])
        return self._start_reply_run(conversation, reply)

    def get_active_reply_runs(self, conversation: AgentConversation) -> dict[int, UUID]:
        """
        Return the run still writing a reply of the conversation, if any.

        :param conversation: The conversation to look at.
        :return: The id of the active run by the id of the reply it writes, empty
            when the agent isn't replying.
        """

        run = ChatRunHandler().get_active_run(AGENT_RUN_TYPE, conversation.id)
        return {run.context["reply_id"]: run.id} if run else {}

    def get_conversation_runs(self, conversation_ids: list[int]) -> dict[int, UUID]:
        """
        Return the runs writing a reply in the given conversations.

        :param conversation_ids: The ids of the conversations to look at.
        :return: The id of the active run by the id of its conversation, only for
            the conversations where the agent is replying.
        """

        return dict(
            ChatRunHandler()
            .runs.filter(
                run_type=AGENT_RUN_TYPE,
                chat_id__in=conversation_ids,
                status__in=ACTIVE_CHAT_RUN_STATUSES,
            )
            .values_list("chat_id", "id")
        )

    def get_accessible_conversations(
        self, owner: AbstractUser
    ) -> QuerySet[AgentConversation]:
        """
        Return the owner's conversations in untrashed Agents and workspaces, while
        the owner is still a member of the workspace.

        :param owner: The user who owns the conversations.
        :return: The conversations.
        """

        return AgentConversation.objects.filter(
            owner_user_id=owner.id,
            agent__trashed=False,
            agent__workspace__trashed=False,
            agent__workspace__workspaceuser__user_id=owner.id,
        )

    def get_reply(self, reply_id: int) -> AgentMessage:
        """
        Fetch a reply with its conversation, the conversation's owner and its agent.

        :param reply_id: The id of the reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists or its
            conversation is in the trash.
        :return: The reply.
        """

        reply = (
            AgentMessage.objects.select_related(
                "conversation__agent__workspace", "conversation__owner_user"
            )
            .filter(id=reply_id, conversation__trashed=False)
            .first()
        )
        if reply is None:
            raise AgentConversationDoesNotExist
        return reply

    def get_reply_request(self, reply: AgentMessage) -> AgentReplyRequest:
        """
        Collect what the model needs to write a reply, or to continue it once the
        owner decided the calls its paused run held.

        :param reply: The reply, with its conversation and agent.
        :return: The instructions, the model and the tools, with the prompt and the
            earlier messages, or with the paused run and the owner's decisions.
        """

        conversation = reply.conversation
        agent = conversation.agent
        run_as = self.resolve_run_as_subject(
            agent.run_as_subject_type, agent.run_as_subject_id, agent.workspace
        )
        transcript = self._get_paused_transcript(reply)
        acting_subject = (
            run_as.subject
            if run_as.status == AgentRunAsState.ACTIVE
            and (
                transcript is None
                or transcript.paused_as(run_as.subject_type, run_as.subject_id)
            )
            else None
        )
        # A generation keeps its selected identity and tools until it ends or is
        # stopped. Configuration edits apply when the next generation is prepared.
        tools: AgentToolConfiguration = (
            self.get_tool_configuration(agent)
            if acting_subject
            else {"allowed_tools": [], "ask_first_tools": []}
        )
        mcp_servers = self.get_mcp_servers(agent)
        resume = (
            None
            if transcript is None
            else self._get_reply_resume(
                reply,
                ConversationTypeAdapter.validate_python(transcript.paused_conversation),
                {
                    **{name: "" for name in tools["allowed_tools"]},
                    **{
                        name: tool.approval_key
                        for server in mcp_servers
                        for name, tool in server.model_tool_names().items()
                    },
                },
                DISALLOWED_TOOL_CALL_NOTE
                if acting_subject
                else RUN_AS_LOST_TOOL_CALL_NOTE,
            )
        )
        prompt, history = (
            (None, []) if resume is not None else self._get_reply_prompt(reply)
        )
        web_search_tool = (
            self._get_web_search_tool(
                agent, bool(tools["allowed_tools"]) or bool(mcp_servers)
            )
            if agent.web_search_enabled
            and (transcript is None or transcript.paused_web_search)
            else None
        )
        return AgentReplyRequest(
            reply_id=reply.id,
            workspace=agent.workspace,
            instructions=agent.instructions,
            provider_type=agent.provider_type,
            model_identifier=agent.model_identifier,
            prompt=prompt,
            history=history,
            resume=resume,
            run_as_unavailable=run_as.status
            in {AgentRunAsState.TRASHED, AgentRunAsState.MISSING},
            acting_subject=acting_subject,
            allowed_tool_names=tools["allowed_tools"],
            ask_first_tool_names=tools["ask_first_tools"],
            timezone=conversation.owner_user.profile.timezone,
            mcp_servers=mcp_servers,
            reasoning_effort=agent.reasoning_effort,
            web_search_tool=web_search_tool,
            web_search_enabled=agent.web_search_enabled,
        )

    def has_mcp_tools(self, agent: AgentApplication) -> bool:
        """
        Whether a reply may offer MCP tools: one of the Agent's servers has a
        tool turned on and, if it uses OAuth, an account connected. Unlike
        `get_mcp_servers` it doesn't refresh a token, so it suits reads.

        :param agent: The Agent.
        :return: True when a server offers a tool.
        """

        return (
            MCPServerTool.objects.filter(
                integration__application_id=agent.id,
                integration__trashed=False,
                enabled=True,
                removed=False,
            )
            .exclude(
                integration__auth_type=MCPAuthType.OAUTH,
                integration__oauth_connected_at__isnull=True,
            )
            .exists()
        )

    def get_mcp_servers(self, agent: AgentApplication) -> tuple[MCPServerSnapshot, ...]:
        """
        Read the Agent's MCP servers that have tools turned on. They don't depend
        on the Agent's workspace identity: their tools act with the server's own
        credential, not in the workspace.

        :param agent: The Agent.
        :return: One snapshot per server, in the integrations' order.
        """

        enabled_tools = Prefetch(
            "tools",
            queryset=MCPServerTool.objects.filter(enabled=True, removed=False),
            to_attr="enabled_tools",
        )
        servers = MCPServerIntegration.objects.filter(
            application_id=agent.id, trashed=False
        ).prefetch_related(enabled_tools)
        snapshots = []
        for server in servers:
            if not server.enabled_tools:
                continue
            try:
                # Refreshes an OAuth token that expires soon, before the reply
                # starts, so the reply itself never writes to the database.
                connection = MCPServerHandler().get_connection(server)
            except MCPServerNotConnected:
                # Its tools can't be called until an editor connects again.
                continue
            snapshots.append(
                MCPServerSnapshot.from_integration(
                    server, server.enabled_tools, connection
                )
            )
        return tuple(snapshots)

    def _get_paused_transcript(
        self, reply: AgentMessage
    ) -> AgentReplyTranscript | None:
        """
        :param reply: The reply.
        :return: Its transcript with the paused run, without the model messages, or
            None when the reply isn't paused.
        """

        return (
            AgentReplyTranscript.objects.filter(
                reply=reply, paused_conversation__isnull=False
            )
            .only(
                "paused_conversation",
                "paused_web_search",
                "paused_run_as_subject_type",
                "paused_run_as_subject_id",
            )
            .first()
        )

    def _get_reply_prompt(self, reply: AgentMessage) -> tuple[str, list[AgentMessage]]:
        """
        Find what a reply answers: the message right before it.

        :param reply: The reply.
        :return: The prompt, and the recent messages before it, oldest first.
        """

        prompt, *history = reply.conversation.messages.filter(id__lt=reply.id).order_by(
            "-id"
        )[: HISTORY_MESSAGE_LIMIT + 1]
        return prompt.content, history[::-1]

    def _get_reply_resume(
        self,
        reply: AgentMessage,
        paused_conversation: Conversation,
        callable_tools: dict[str, str],
        disallowed_note: str,
    ) -> AgentReplyResume:
        """
        Continue a paused reply with the owner's decision on each held call, showing
        its saved steps again and updating those of the held calls in place.

        :param reply: The paused reply.
        :param paused_conversation: Its paused run, holding the calls.
        :param callable_tools: The tools the reply may call now, with the
            approval key of the MCP ones.
        :param disallowed_note: Tells the model why an approved call can't run.
        :return: The paused run with the decisions and the saved steps.
        """

        held = paused_conversation.deferred_tool_requests
        held_ids = {call.tool_call_id for call in held.approvals}
        # Providers may reuse a call id in a later response, so the newest row holds it.
        approvals = {
            approval.tool_call_id: approval
            for approval in reply.approvals.all()
            if approval.tool_call_id in held_ids
        }
        # An undecided call gets no result, so the run fails instead of guessing.
        results = {
            tool_call_id: self._get_approval_result(
                approval, callable_tools, disallowed_note
            )
            for tool_call_id, approval in approvals.items()
            if approval.status != AgentToolApproval.Status.PENDING
        }
        return AgentReplyResume(
            paused_conversation=paused_conversation,
            deferred_tool_results=held.build_results(approvals=results),
            saved_steps=reply.steps or [],
            held_step_ids={
                tool_call_id: approval.step_id
                for tool_call_id, approval in approvals.items()
            },
            approved_ids=frozenset(
                tool_call_id
                for tool_call_id, approval in approvals.items()
                if approval.status == AgentToolApproval.Status.APPROVED
            ),
        )

    def _get_approval_result(
        self,
        approval: AgentToolApproval,
        callable_tools: dict[str, str],
        disallowed_note: str,
    ) -> ToolApproved | ToolDenied:
        """
        Tell the model what the owner decided about a held call. An approved call
        to a tool the reply may no longer call, or to an MCP tool whose server,
        account or definition changed since it was held, is denied instead, and
        its step then shows a permission failure rather than a rejection.

        :param approval: The decided approval of the call.
        :param callable_tools: The tools the reply may call now, with the
            approval key of the MCP ones.
        :param disallowed_note: Tells the model why an approved call can't run.
        :return: Whether the call runs, or why it doesn't.
        """

        if approval.status == AgentToolApproval.Status.REJECTED:
            return ToolDenied(
                f"{REJECTED_TOOL_CALL_NOTE} Their reason: {approval.reason}"
                if approval.reason
                else REJECTED_TOOL_CALL_NOTE
            )
        if approval.tool_name not in callable_tools:
            # An MCP tool doesn't act as the Agent's identity, so losing it isn't why.
            return ToolDenied(
                DISALLOWED_TOOL_CALL_NOTE if approval.tool_key else disallowed_note
            )
        if callable_tools[approval.tool_name] != approval.tool_key:
            return ToolDenied(MCP_TOOL_CHANGED_CALL_NOTE)
        return ToolApproved()

    def finish_reply(
        self,
        reply_id: int,
        status: str,
        error_code: str,
        result: AgentReplyResult | None,
    ) -> AgentMessage | None:
        """
        Save how a run of a reply ended, with its text, activity and, when the
        responder reports the model it used, its transcript, unless the reply no
        longer exists. A paused run leaves the reply waiting for the owner's approval
        of its held calls. Characters PostgreSQL can't store are dropped from the
        text; steps come clean from ``ChatRunSteps``. Blank text, no steps and a run
        that never started keep what an earlier run of the reply saved, so a failed
        resume still shows the paused reply.

        :param reply_id: The id of the reply.
        :param status: The final status of the run: completed, cancelled or failed.
        :param error_code: Why the reply failed, or an empty string.
        :param result: What the run produced, or None when it never started.
        :return: The saved reply with its conversation, or None when it no longer
            exists.
        """

        # The caller's lock on the run or the reply serializes everything ending it.
        reply = (
            AgentMessage.objects.select_related("conversation")
            .filter(id=reply_id)
            .first()
        )
        if reply is None:
            return None
        paused = result is not None and result.paused
        reply.status = AgentReplyStatus.WAITING if paused else status
        reply.error_code = error_code
        content = remove_unstorable_characters(result.text if result else "")
        if content.strip():
            reply.content = content
        steps = (
            result.steps
            if result and result.steps
            else stop_running_steps(reply.steps or [])
        )
        if not paused:
            steps = self._end_held_steps(reply, steps, resumed=result is not None)
        reply.steps = steps or None
        reply.save(
            update_fields=["status", "error_code", "content", "steps", "updated_on"]
        )
        self._save_transcript(reply, result)
        if paused:
            last_pause = reply.approvals.aggregate(last=Max("pause"))["last"] or 0
            AgentToolApproval.objects.bulk_create(
                AgentToolApproval(
                    reply=reply,
                    tool_call_id=call.tool_call_id,
                    step_id=call.step_id,
                    pause=last_pause + 1,
                    tool_name=call.tool_name,
                    tool_key=result.tool_keys.get(call.tool_name, ""),
                )
                for call in result.waiting_calls
            )
        reply.conversation.save(update_fields=["updated_on"])
        return reply

    def _end_held_steps(
        self, reply: AgentMessage, steps: list[ChatRunStep], resumed: bool
    ) -> list[ChatRunStep]:
        """
        End the held calls of a reply that ends without resuming them, by the
        owner's decision on each.

        :param reply: The reply.
        :param steps: Its steps.
        :param resumed: Whether the reply resumed, so its approved calls may have
            run.
        :return: The steps with none left waiting.
        """

        if not any(step["status"] == ChatRunStepStatus.WAITING for step in steps):
            return steps
        decisions = {
            approval.step_id: approval.status for approval in reply.approvals.all()
        }
        return end_waiting_steps(
            steps,
            rejected_step_ids={
                step_id
                for step_id, status in decisions.items()
                if status == AgentToolApproval.Status.REJECTED
            },
            approved_step_ids={
                step_id
                for step_id, status in decisions.items()
                if resumed and status == AgentToolApproval.Status.APPROVED
            },
        )

    def _save_transcript(
        self, reply: AgentMessage, result: AgentReplyResult | None
    ) -> None:
        """
        Add a run's model messages to the reply's transcript and keep the paused
        run only while the reply waits. A run without a model result keeps the
        transcript of earlier runs.

        :param reply: The reply the run wrote.
        :param result: What the run produced, or None when it never started.
        """

        if result is None or not result.provider_type:
            AgentReplyTranscript.objects.filter(reply=reply).update(
                **self._paused_fields(None)
            )
            return
        transcript = AgentReplyTranscript.objects.filter(reply=reply).first()
        if transcript is None:
            transcript = AgentReplyTranscript(
                reply=reply,
                provider_type=result.provider_type,
                model_identifier=result.model_identifier,
            )
        for name, value in self._paused_fields(result.paused_run).items():
            setattr(transcript, name, value)
        if result.model_messages is not None:
            transcript.provider_type = result.provider_type
            transcript.model_identifier = result.model_identifier
            # Each run of a paused reply adds only its new messages.
            transcript.model_messages = [
                *(transcript.model_messages or []),
                *remove_unstorable_characters(result.model_messages),
            ]
            transcript.usage = result.usage
        transcript.save()

    def _paused_fields(self, paused_run: AgentPausedRun | None) -> dict[str, Any]:
        """
        :param paused_run: The run that paused, or None when the reply isn't paused.
        :return: The transcript's paused run fields, cleared when there is none.
        """

        if paused_run is None:
            return {
                "paused_conversation": None,
                "paused_web_search": False,
                "paused_run_as_subject_type": None,
                "paused_run_as_subject_id": None,
            }
        run_as = paused_run.run_as
        return {
            "paused_conversation": remove_unstorable_characters(
                paused_run.conversation
            ),
            "paused_web_search": paused_run.web_search,
            "paused_run_as_subject_type": None
            if run_as is None
            else subject_type_registry.get_by_model(run_as).type,
            "paused_run_as_subject_id": None if run_as is None else run_as.pk,
        }

    def refresh_unfinished_replies(
        self, messages: list[AgentMessage], active_runs: dict[int, UUID]
    ) -> list[AgentMessage]:
        """
        Read again, from the primary database, the replies that still look
        unfinished although no run writes them any more: the messages were read
        before the runs, maybe from a lagging replica.

        :param messages: Messages, possibly read from a replica.
        :param active_runs: The active run by reply id, read after the messages.
        :return: The same messages, with the replies whose run ended read again.
        """

        ended = [
            message.id
            for message in messages
            if message.status in ACTIVE_CHAT_RUN_STATUSES
            and message.id not in active_runs
        ]
        if not ended:
            return messages
        fresh = (
            AgentMessage.objects.using(DEFAULT_DB_ALIAS)
            .prefetch_related(
                Prefetch(
                    "approvals",
                    queryset=AgentToolApproval.objects.using(DEFAULT_DB_ALIAS),
                )
            )
            .in_bulk(ended)
        )
        return [fresh.get(message.id, message) for message in messages]

    def mark_reply_interrupted(self, reply_id: int) -> AgentConversation | None:
        """
        Show that a started reply did not complete, unless it already ended, the
        way a run ending without a model result does.

        :param reply_id: The id of the reply.
        :return: The reply's conversation when this ended the reply, else None.
        """

        still_active = (
            AgentMessage.objects.select_for_update()
            .filter(id=reply_id, status__in=ACTIVE_CHAT_RUN_STATUSES)
            .exists()
        )
        if not still_active:
            return None
        reply = self.finish_reply(
            reply_id,
            ChatRunStatus.FAILED,
            ChatRunErrorCode.INTERRUPTED,
            AgentReplyResult(text=""),
        )
        return reply.conversation

    def export_conversations(self, agent: AgentApplication) -> list[dict]:
        """
        Serialize the agent's conversations and messages for an internal copy. Reply
        transcripts stay behind: they hold every tool result, and nothing reads them.

        :param agent: The agent whose conversations are exported.
        :return: The conversations, oldest first, each with its messages in the order
            they were sent.
        """

        conversations = (
            AgentConversation.objects.filter(agent=agent)
            .order_by("id")
            .prefetch_related(
                Prefetch(
                    "messages",
                    queryset=AgentMessage.objects.order_by("id").prefetch_related(
                        "approvals"
                    ),
                )
            )
        )
        return [
            {
                "title": conversation.title,
                "pinned": conversation.pinned,
                "owner_user_id": conversation.owner_user_id,
                "created_on": conversation.created_on.isoformat(),
                "updated_on": conversation.updated_on.isoformat(),
                "messages": [
                    {
                        "role": message.role,
                        "content": message.content,
                        "status": message.status,
                        "error_code": message.error_code,
                        # Approvals aren't copied, so the copy gets held calls ended.
                        "steps": self._end_held_steps(
                            message,
                            message.steps or [],
                            resumed=message.status != AgentReplyStatus.WAITING,
                        )
                        or None,
                        "created_on": message.created_on.isoformat(),
                        "updated_on": message.updated_on.isoformat(),
                    }
                    for message in conversation.messages.all()
                ],
            }
            for conversation in conversations
        ]

    def import_conversations(
        self, agent: AgentApplication, serialized_conversations: list[dict]
    ) -> None:
        """
        Copy conversations with their messages into the agent with new uuids.
        Conversations of deleted owners are skipped, and a reply still being
        written or waiting for approvals is ended as interrupted.

        :param agent: The agent to copy the conversations into.
        :param serialized_conversations: The conversations from export_conversations.
        """

        existing_owner_ids = set(
            get_user_model()
            .objects.filter(
                id__in=[data["owner_user_id"] for data in serialized_conversations]
            )
            .values_list("id", flat=True)
        )
        retained_data = [
            data
            for data in serialized_conversations
            if data["owner_user_id"] in existing_owner_ids
        ]
        conversations = [
            AgentConversation(
                agent=agent,
                uuid=uuid4(),
                title=data["title"],
                pinned=data.get("pinned", False),
                owner_user_id=data["owner_user_id"],
            )
            for data in retained_data
        ]

        AgentConversation.objects.bulk_create(conversations, batch_size=1000)
        messages = []
        message_data = []
        for conversation, data in zip(conversations, retained_data):
            conversation.created_on = parse_datetime(data["created_on"])
            conversation.updated_on = parse_datetime(data["updated_on"])
            for serialized_message in data["messages"]:
                status = serialized_message["status"]
                error_code = serialized_message["error_code"]
                # Approvals are not copied, so a waiting reply could never resume.
                if (
                    status in ACTIVE_CHAT_RUN_STATUSES
                    or status == AgentReplyStatus.WAITING
                ):
                    status = ChatRunStatus.FAILED
                    error_code = ChatRunErrorCode.INTERRUPTED
                messages.append(
                    AgentMessage(
                        conversation=conversation,
                        uuid=uuid4(),
                        role=serialized_message["role"],
                        content=serialized_message["content"],
                        status=status,
                        error_code=error_code,
                        steps=stop_running_steps(serialized_message.get("steps") or [])
                        or None,
                    )
                )
                message_data.append(serialized_message)

        # auto_now overrides timestamps in bulk_create, so restore the captured ones.
        AgentConversation.objects.bulk_update(
            conversations, ["created_on", "updated_on"], batch_size=1000
        )
        AgentMessage.objects.bulk_create(messages, batch_size=1000)
        for message, data in zip(messages, message_data):
            message.created_on = parse_datetime(data["created_on"])
            message.updated_on = parse_datetime(data["updated_on"])
        AgentMessage.objects.bulk_update(
            messages, ["created_on", "updated_on"], batch_size=1000
        )
