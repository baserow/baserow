from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet

from baserow.core.exceptions import PermissionDenied
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.signals import application_pending_count_updated, application_updated
from baserow.core.subject_options import SubjectOptionsHandler
from baserow.core.types import PermissionCheck

from .constants import RUN_AS_SUBJECT_TYPES, AgentReadinessState
from .exceptions import AgentConversationWaitingForApproval, AgentNotReady
from .handler import AgentHandler
from .models import AgentApplication, AgentConversation, AgentMessage, AgentToolApproval
from .operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    DeleteAgentConversationOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
    UpdateAgentConversationOperationType,
)
from .signals import (
    agent_conversation_activity,
    agent_conversation_deleted,
    agent_conversation_updated,
)
from .types import (
    AgentConfiguration,
    AgentConfigurationUpdated,
    AgentConversationCursor,
    AgentConversationUpdated,
    AgentMessageCreated,
    AgentReplyRequest,
    AgentToolDecision,
    AgentToolDecisionsResult,
)
from .validators import validate_message_content


class AgentService:
    def __init__(self):
        self.handler = AgentHandler()

    def _get_authorized_agent(
        self,
        user: AbstractUser,
        agent_id: int,
        *operations: str,
        for_update: bool = False,
    ) -> AgentApplication:
        """Fetch the Agent and check each operation on it."""

        agent = self.handler.get_agent(agent_id, for_update=for_update)
        CoreHandler().check_multiple_permissions(
            [PermissionCheck(user, operation, agent) for operation in operations],
            workspace=agent.workspace,
            raise_exception=True,
        )
        return agent

    def get_configuration(
        self, user: AbstractUser, agent_id: int
    ) -> AgentConfiguration:
        """
        Return the Agent configuration to a user allowed to read it.

        :param user: The user reading the configuration.
        :param agent_id: The id of the Agent.
        :raises PermissionException: When the user may not read the configuration.
        :return: The configuration values with their readiness.
        """

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.get_configuration(agent)

    def get_run_as_subject_options(
        self, user: AbstractUser, agent_id: int, search: str = ""
    ) -> QuerySet:
        """
        List identities selectable by a user who may change this Agent's configuration.

        :param user: The user choosing a workspace identity.
        :param agent_id: The Agent whose configuration is being edited.
        :param search: The optional identity-name search.
        :raises PermissionException: When the user may not read and update the Agent.
        :return: Active identity options from the Agent's authoritative workspace.
        """

        agent = self._get_authorized_agent(
            user,
            agent_id,
            UpdateApplicationOperationType.type,
            ReadAgentConfigurationOperationType.type,
        )
        return SubjectOptionsHandler.get_options(
            workspace=agent.workspace,
            search=search,
            subject_types=set(RUN_AS_SUBJECT_TYPES),
        )

    @transaction.atomic
    def update_configuration(
        self, user: AbstractUser, agent_id: int, **values: str | int | list[str] | None
    ) -> AgentConfigurationUpdated:
        """
        Save part of the configuration for a user who may update and read it.

        :param user: The user updating the configuration.
        :param agent_id: The id of the Agent.
        :param values: The configuration values to set, by field name.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :raises AgentRunAsSubjectDoesNotExist: When the Agent can't act as the
            given subject.
        :return: The Agent, its original and new configuration values, and the
            resolved resulting configuration.
        """

        agent = self._get_authorized_agent(
            user,
            agent_id,
            UpdateApplicationOperationType.type,
            ReadAgentConfigurationOperationType.type,
            for_update=True,
        )
        updated = self.handler.update_configuration(agent, **values)
        if updated.original_values != updated.new_values:
            # Open pages refresh readiness from this public application payload.
            application_updated.send(self, application=agent, user=user)
        return updated

    def list_conversations(
        self,
        user: AbstractUser,
        agent_id: int,
        cursor: AgentConversationCursor | None = None,
        pinned: bool | None = None,
        has_pending_approvals: bool | None = None,
    ) -> QuerySet[AgentConversation]:
        """
        Return only the user's own conversations, never another owner's.

        :param user: The user listing their conversations.
        :param agent_id: The id of the agent.
        :param cursor: The last conversation of the previous page, to continue after.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :param pinned: Only pinned or unpinned conversations, or both when omitted.
        :param has_pending_approvals: Only conversations with or without pending calls.
        :return: The user's conversations, pinned first, then most recently active.
        """

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.list_conversations(
            agent, user, cursor, pinned, has_pending_approvals
        )

    def list_messages(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> tuple[AgentConversation, QuerySet[AgentMessage]]:
        """
        Return one of the user's conversations with its messages.

        :param user: The user reading the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :return: The conversation, and its messages newest first.
        """

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(agent, user, conversation_uuid)
        return conversation, conversation.messages.prefetch_related("approvals")

    @transaction.atomic
    def update_conversation(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        **values: str | bool,
    ) -> AgentConversationUpdated:
        """
        Update one of the user's conversations and tell their other sessions what
        changed.

        :param user: The user updating the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param values: The values to set, by field name, such as the title.
        :raises PermissionException: When the user may not update conversations of
            the agent.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :return: The conversation with the original and new values that changed.
        """

        agent = self._get_authorized_agent(
            user, agent_id, UpdateAgentConversationOperationType.type
        )
        # Locked so a concurrent delete or rename can't interleave with this one.
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        updated = self.handler.update_conversation(conversation, **values)
        if updated.new_values:
            agent_conversation_updated.send(
                self, conversation=conversation, user=user, values=updated.new_values
            )
        return updated

    @transaction.atomic
    def delete_conversation(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> AgentConversation:
        """
        Move one of the user's conversations to the trash, where only they see it.

        :param user: The user deleting the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the user may not delete conversations of
            the agent.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :return: The trashed conversation.
        """

        agent = self._get_authorized_agent(
            user, agent_id, DeleteAgentConversationOperationType.type
        )
        # The lock waits for a message being sent, so its reply is stopped too.
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        had_pending_approvals = self.handler.conversation_has_pending_approvals(
            conversation.id
        )
        self.handler.delete_conversation(user, conversation)
        agent_conversation_deleted.send(self, conversation=conversation, user=user)
        if had_pending_approvals:
            application_pending_count_updated.send(
                self, application=agent, user_ids=[conversation.owner_user_id]
            )
        return conversation

    def _require_ready(self, agent: AgentApplication) -> None:
        """Reject new content without leaking privileged setting diagnostics."""

        readiness, _ = self.handler.get_configuration_readiness(agent)
        if readiness != AgentReadinessState.READY:
            raise AgentNotReady

    def can_read_conversation(self, user: AbstractUser, conversation_id: int) -> bool:
        """
        Check that the user owns the conversation in an untrashed Agent and may
        still read the agent's conversations.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :return: Whether the user may read the conversation.
        """

        conversation = (
            self.handler.get_accessible_conversations(user)
            .select_related("agent__workspace")
            .filter(id=conversation_id)
            .first()
        )
        if conversation is None:
            return False
        return CoreHandler().check_permissions(
            user,
            ReadAgentConversationsOperationType.type,
            workspace=conversation.agent.workspace,
            context=conversation.agent,
            raise_permission_exceptions=False,
        )

    def prepare_reply(self, reply_id: int) -> AgentReplyRequest:
        """
        Load what a reply answers, or the paused run it continues, checking again
        that the conversation's owner may still send it: access and configuration
        can change while the reply waits.

        :param reply_id: The id of the reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists or its
            conversation is in the trash.
        :raises PermissionException: When the agent or its workspace is trashed, or
            the owner left the workspace or may no longer send messages to the agent.
        :raises AgentNotReady: When the agent's configuration is no longer ready.
        :return: The instructions, the model and the tools, with the prompt and the
            earlier messages, or with the paused run and the owner's decisions.
        """

        reply = self.handler.get_reply(reply_id)
        agent = reply.conversation.agent
        # Workspace membership is part of the permission check below.
        if agent.trashed or agent.workspace is None or agent.workspace.trashed:
            raise PermissionDenied
        CoreHandler().check_permissions(
            reply.conversation.owner_user,
            CreateAgentMessageOperationType.type,
            workspace=agent.workspace,
            context=agent,
        )
        self._require_ready(agent)
        return self.handler.get_reply_request(reply)

    @transaction.atomic
    def create_conversation(
        self,
        user: AbstractUser,
        agent_id: int,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """
        Start a private conversation, or return its first message on a retry.

        :param user: The user starting the conversation.
        :param agent_id: The id of the agent.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :raises FeatureDisabledException: When Agents are disabled, so an imported
            Agent can't call its provider.
        :raises PermissionException: When the user may not start conversations with
            the agent.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentConversationDoesNotExist: When the uuid belongs to another
            owner's or agent's conversation, or to a deleted one.
        :raises AgentMessageConflict: When the uuid was accepted with another first
            message.
        :raises AgentNotReady: When the agent isn't ready for a new conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation, its first message and its reply, and whether they
            are new.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self._get_authorized_agent(
            user,
            agent_id,
            CreateAgentConversationOperationType.type,
            CreateAgentMessageOperationType.type,
        )
        validate_message_content(content)
        retry = self.handler.get_creation_retry(
            agent, user, uuid, message_uuid, content
        )
        if retry is not None:
            return retry
        self._require_ready(agent)
        result = self.handler.create_conversation(
            agent, user, uuid, message_uuid, content
        )
        if result.created:
            agent_conversation_activity.send(
                self, conversation=result.conversation, user=user, run_id=result.run_id
            )
        return result

    @transaction.atomic
    def create_message(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """
        Send a message to one of the user's conversations, or return it on a retry.

        :param user: The user sending the message.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :raises FeatureDisabledException: When Agents are disabled, so an imported
            Agent can't call its provider.
        :raises PermissionException: When the user may not send messages to the
            agent.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :raises AgentConversationWaitingForApproval: When the latest reply waits for
            the user to decide its held calls.
        :raises AgentNotReady: When the agent isn't ready for a new message.
        :raises ChatRunAlreadyActive: When the agent is still replying in this
            conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation, the message and its reply, and whether the message
            is new.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        agent = self._get_authorized_agent(
            user, agent_id, CreateAgentMessageOperationType.type
        )
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        validate_message_content(content)
        retry = self.handler.get_message_retry(conversation, uuid, content)
        if retry is not None:
            return retry
        if self.handler.get_waiting_reply(conversation) is not None:
            raise AgentConversationWaitingForApproval
        # Configuration may have changed while waiting for the conversation lock.
        agent = self.handler.get_agent(agent_id)
        self._require_ready(agent)
        result = self.handler.create_message(conversation, uuid, content)
        if result.created:
            agent_conversation_activity.send(
                self, conversation=result.conversation, user=user, run_id=result.run_id
            )
        return result

    @transaction.atomic
    def decide_approvals(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        decisions: list[AgentToolDecision],
        always_allow: bool = False,
    ) -> AgentToolDecisionsResult:
        """
        Approve or reject held calls of the reply waiting in one of the user's
        conversations, tell the owner's other sessions what is left to decide, and
        continue the reply once nothing is. Continuing costs model usage like a
        message, so it needs the same access.

        :param user: The user deciding.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param decisions: Whether each held call may run, by approval id, with the
            reason for a rejection.
        :param always_allow: Whether the tools of the approved calls stop asking
            first, which needs the access of a configuration update.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises PermissionException: When the user may not send messages to the
            agent, or may not update its configuration while always allowing.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :raises AgentToolApprovalNotPending: When an approval is decided already or
            isn't held by the reply waiting in the conversation.
        :raises AgentNotReady: When the agent isn't ready to continue the reply.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The reply with its approvals, the run continuing it or None while
            some held calls are still undecided, and the tools that stopped asking
            first.
        """

        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        operations = [CreateAgentMessageOperationType.type]
        if always_allow:
            operations += [
                UpdateApplicationOperationType.type,
                ReadAgentConfigurationOperationType.type,
            ]
        agent = self._get_authorized_agent(user, agent_id, *operations)
        # The lock serializes decisions with each other and with sends and trashing.
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        reply, decided, all_decided = self.handler.decide_approvals(
            conversation, user, decisions
        )
        approved_tools = [
            approval.tool_name
            for approval in decided
            if approval.status == AgentToolApproval.Status.APPROVED
        ]
        rejected_tools = [
            approval.tool_name
            for approval in decided
            if approval.status == AgentToolApproval.Status.REJECTED
        ]
        always_allowed_tools = (
            self._stop_asking_first(user, agent_id, approved_tools)
            if always_allow
            else []
        )
        application_pending_count_updated.send(
            self, application=agent, user_ids=[conversation.owner_user_id]
        )
        run_id = None
        if all_decided:
            self._require_ready(self.handler.get_agent(agent_id))
            run_id = self.handler.resume_reply(reply).id
        agent_conversation_activity.send(
            self, conversation=conversation, user=user, run_id=run_id
        )
        return AgentToolDecisionsResult(
            reply, approved_tools, rejected_tools, always_allowed_tools, run_id
        )

    def _stop_asking_first(
        self, user: AbstractUser, agent_id: int, tool_names: list[str]
    ) -> list[str]:
        """
        Stop asking first for the given tools, telling the Agent's open pages when
        its configuration changed.

        :param user: The user deciding, already allowed to update the configuration.
        :param agent_id: The id of the Agent.
        :param tool_names: The tools of the approved calls.
        :return: The tools that stopped asking first.
        """

        # Locked after the conversation, as trashing it needs the Agent row too.
        agent = self.handler.get_agent(agent_id, for_update=True)
        stopped = self.handler.stop_asking_first(agent, tool_names)
        if stopped:
            application_updated.send(self, application=agent, user=user)
        return stopped
