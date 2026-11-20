from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import F, Q, QuerySet

from rest_framework.exceptions import ValidationError

from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.signals import application_pending_count_updated, application_updated
from baserow.core.types import PermissionCheck

from .action_tools.handler import AgentActionHandler
from .action_tools.signals import agent_action_updated
from .constants import AgentReadinessState
from .exceptions import (
    AgentConversationWaitingForApproval,
    AgentNotReady,
    AgentToolApprovalNotPending,
    AgentTriggerOff,
)
from .handler import AgentHandler
from .models import AgentApplication, AgentConversation, AgentMessage, AgentToolApproval
from .operations import (
    ApproveAgentToolCallsOperationType,
    ContinueAgentTriggeredConversationOperationType,
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    DeleteAgentConversationOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
    UpdateAgentConversationOperationType,
)
from .registries import agent_tool_type_registry
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

    def get_authorized_agent(
        self,
        user: AbstractUser,
        agent_id: int,
        *operations: str,
        for_update: bool = False,
    ) -> AgentApplication:
        """
        Fetch the Agent and check each operation on it.

        :param user: The user asking.
        :param agent_id: The id of the Agent.
        :param operations: The operation type names the user needs on the Agent.
        :param for_update: Whether to lock the Agent.
        :raises ApplicationDoesNotExist: When the Agent doesn't exist or is trashed.
        :raises PermissionException: When the user lacks any of the operations.
        :return: The Agent.
        """

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

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.get_configuration(agent)

    def get_available_tools(self, user: AbstractUser, workspace_id: int) -> list[dict]:
        """
        List the tools an Agent created in the workspace can be allowed to call.

        :param user: The user about to create an Agent.
        :param workspace_id: The id of the workspace the Agent is created in.
        :raises WorkspaceDoesNotExist: When the workspace doesn't exist.
        :raises PermissionException: When the user may not create an application in
            the workspace.
        :return: Each tool an Agent can be given.
        """

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return self.handler.get_available_tools(
            self.handler.get_deactivated_tools(workspace)
        )

    def get_run_as_identities(
        self, user: AbstractUser, agent_id: int, search: str = ""
    ) -> QuerySet:
        """
        List identities selectable by a user who may change this Agent's configuration.

        :param user: The user choosing a workspace identity.
        :param agent_id: The Agent whose configuration is being edited.
        :param search: The optional identity-name search.
        :raises PermissionException: When the user may not read and update the Agent.
        :return: Active identity options from the Agent's authoritative workspace,
            none when the user may not bind identities.
        """

        agent = self.get_authorized_agent(
            user,
            agent_id,
            UpdateApplicationOperationType.type,
            ReadAgentConfigurationOperationType.type,
        )
        identities = IdentityHandler().get_queryset(agent.workspace, for_selection=True)
        if not IdentityService().check_can_bind(
            user, agent.workspace, raise_permission_exceptions=False
        ):
            identities = identities.none()
        if search := search.strip():
            identities = identities.filter(first_name__icontains=search)
        return identities.values("id", name=F("first_name"))

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
            its configuration, or may not bind it to a different identity.
        :raises AgentRunAsSubjectDoesNotExist: When the Agent can't act as the
            given subject.
        :raises rest_framework.exceptions.PermissionDenied: When an allowed tool is
            deactivated in the Agent's workspace, unless its type raises its own
            error.
        :return: The Agent, its original and new configuration values, and the
            resolved resulting configuration.
        """

        agent = self.get_authorized_agent(
            user,
            agent_id,
            UpdateApplicationOperationType.type,
            ReadAgentConfigurationOperationType.type,
            for_update=True,
        )
        run_as = [values.get(field) for field in self.handler.run_as_fields]
        current_run_as = [getattr(agent, field) for field in self.handler.run_as_fields]
        if any(run_as) and run_as != current_run_as:
            IdentityService().check_can_bind(user, agent.workspace)
        for name in values.get("allowed_tools") or []:
            agent_tool_type_registry.get(name).raise_if_deactivated(agent.workspace)
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
        Return shared conversations and private conversations this user participates in.

        :param user: The user listing conversations.
        :param agent_id: The id of the agent.
        :param cursor: The last conversation of the previous page, to continue after.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :param pinned: Only pinned or unpinned conversations, or both when omitted.
        :param has_pending_approvals: Only conversations with or without pending calls.
        :return: The conversations, pinned first, then most recently active.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.list_conversations(
            agent, user, cursor, pinned, has_pending_approvals
        )

    def list_pending_replies(
        self, user: AbstractUser, agent_id: int
    ) -> QuerySet[AgentMessage]:
        """Replies with undecided tool calls in conversations visible to this user."""

        return self.handler.list_pending_replies(
            self.list_conversations(user, agent_id)
        )

    def list_messages(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> tuple[AgentConversation, QuerySet[AgentMessage]]:
        """
        Return one of the user's own or shared conversations with its messages.

        :param user: The user reading the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The conversation, and its messages newest first.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(agent, user, conversation_uuid)
        return conversation, conversation.messages.select_related(
            "sender"
        ).prefetch_related("approvals")

    def _check_shared_change(
        self,
        user: AbstractUser,
        agent: AgentApplication,
        conversation: AgentConversation,
    ) -> None:
        """
        A shared conversation is the agent's own record, so changing it needs the
        access of a configuration update on top of the conversation operation.

        :param user: The user changing the conversation.
        :param agent: The agent, with its workspace.
        :param conversation: The conversation being changed.
        :raises PermissionException: When the conversation is shared and the user
            may not update the agent.
        """

        if not conversation.shared and conversation.owner_user_id != user.id:
            raise PermissionDenied()
        for operation in self.handler.get_shared_change_operations(conversation):
            CoreHandler().check_permissions(
                user, operation, workspace=agent.workspace, context=agent
            )

    @transaction.atomic
    def update_conversation(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        **values: str | bool,
    ) -> AgentConversationUpdated:
        """
        Update one of the user's own or shared conversations and tell its other
        readers' sessions what changed.

        :param user: The user updating the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param values: The values to set, by field name, such as the title.
        :raises PermissionException: When the user may not update conversations of
            the agent, or may not update the agent for a shared conversation.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The conversation with the original and new values that changed.
        """

        agent = self.get_authorized_agent(
            user, agent_id, UpdateAgentConversationOperationType.type
        )
        # Locked so a concurrent delete or rename can't interleave with this one.
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        self._check_shared_change(user, agent, conversation)
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
        Move one of the user's own or shared conversations to the trash.

        :param user: The user deleting the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the user may not delete conversations of
            the agent, or may not update the agent for a shared conversation.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The trashed conversation.
        """

        agent = self.get_authorized_agent(
            user, agent_id, DeleteAgentConversationOperationType.type
        )
        # The lock waits for a message being sent, so its reply is stopped too.
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        self._check_shared_change(user, agent, conversation)
        had_pending_approvals = self.handler.conversation_has_pending_approvals(
            conversation.id
        )
        self.handler.delete_conversation(user, conversation)
        agent_conversation_deleted.send(self, conversation=conversation, user=user)
        if had_pending_approvals:
            application_pending_count_updated.send(
                self, application=agent, user_ids=conversation.pending_count_user_ids
            )
        return conversation

    def _author_conversation(self, user, agent_id, uuid, *, lock=False):
        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(agent, user, uuid, for_update=lock)
        if conversation.owner_user_id != user.id:
            raise PermissionDenied()
        return conversation

    @transaction.atomic
    def share_conversation(self, user, agent_id, uuid):
        conversation = self._author_conversation(user, agent_id, uuid, lock=True)
        if not conversation.shared:
            conversation.shared = True
            conversation.save(update_fields=["shared"])
            self._notify_audience_change(user, conversation)
        return conversation

    def _notify_audience_change(self, user, conversation):
        agent_conversation_updated.send(
            self,
            conversation=conversation,
            user=user,
            values={
                "shared": conversation.shared,
                "participants": [
                    {"id": u.pk, "name": u.first_name or u.username}
                    for u in conversation.participants.all()
                ]
                if not conversation.shared
                else [],
            },
        )
        application_pending_count_updated.send(
            self,
            application=conversation.agent,
            user_ids=conversation.pending_count_user_ids,
        )

    def _approval_candidates(self, conversation, candidates):
        agent = conversation.agent
        checks_by_user = {
            candidate: (
                PermissionCheck(
                    candidate, ReadAgentConversationsOperationType.type, agent
                ),
                PermissionCheck(
                    candidate, ApproveAgentToolCallsOperationType.type, agent
                ),
            )
            for candidate in candidates
        }
        allowed = CoreHandler().check_multiple_permissions(
            [check for pair in checks_by_user.values() for check in pair],
            workspace=agent.workspace,
        )
        return [
            candidate
            for candidate, checks in checks_by_user.items()
            if all(allowed[c] for c in checks)
        ]

    def approval_candidates(self, user, agent_id, uuid, search=""):
        conversation = self._author_conversation(user, agent_id, uuid)
        if conversation.shared or not self.handler.get_waiting_reply(conversation):
            return []
        members = (
            get_user_model()
            .objects.filter(
                workspaceuser__workspace=conversation.agent.workspace, is_active=True
            )
            .exclude(pk=user.pk)
        )
        if search:
            members = members.filter(
                Q(first_name__icontains=search) | Q(email__icontains=search)
            )
        return self._approval_candidates(
            conversation, list(members.order_by("first_name", "pk"))
        )

    @transaction.atomic
    def request_approval(self, user, agent_id, uuid, reply_uuid, user_ids):
        conversation = self._author_conversation(user, agent_id, uuid, lock=True)
        reply = self.handler.get_waiting_reply(conversation)
        if conversation.shared or reply is None or reply.uuid != reply_uuid:
            raise AgentToolApprovalNotPending()
        candidates = list(
            get_user_model()
            .objects.filter(
                pk__in=user_ids,
                is_active=True,
                workspaceuser__workspace=conversation.agent.workspace,
            )
            .exclude(pk=user.pk)
        )
        if {
            person.pk for person in self._approval_candidates(conversation, candidates)
        } != set(user_ids):
            raise ValidationError({"user_ids": "Choose eligible workspace members."})
        conversation.participants.add(*candidates)
        self._notify_audience_change(user, conversation)
        return conversation

    @transaction.atomic
    def delete_for_me(self, user, agent_id, uuid):
        conversation = self._author_conversation(user, agent_id, uuid, lock=True)
        if conversation.shared:
            raise PermissionDenied()
        CoreHandler().check_permissions(
            user,
            DeleteAgentConversationOperationType.type,
            workspace=conversation.agent.workspace,
            context=conversation.agent,
        )
        if not conversation.participants.exclude(pk=user.pk).exists():
            return self.delete_conversation(user, agent_id, uuid)
        conversation.participants.remove(user)
        from baserow.ws.tasks import broadcast_to_users

        transaction.on_commit(
            lambda: broadcast_to_users.delay(
                [user.pk],
                {
                    "type": "agent_conversation_deleted",
                    "agent_id": agent_id,
                    "conversation_uuid": str(uuid),
                },
            )
        )
        self._notify_audience_change(user, conversation)
        application_pending_count_updated.send(
            self, application=conversation.agent, user_ids=[user.pk]
        )
        return conversation

    def _require_ready(self, agent: AgentApplication) -> None:
        """Reject new content without leaking privileged setting diagnostics."""

        readiness, _ = self.handler.get_configuration_readiness(agent)
        if readiness != AgentReadinessState.READY:
            raise AgentNotReady

    def _get_accessible_conversation(
        self, user: AbstractUser, conversation_id: int, using: str | None = None
    ) -> AgentConversation | None:
        """
        Fetch the conversation with its agent if the user sees it at all.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :param using: The database to read from, or None to let the router pick.
        :return: The conversation, or None when the user doesn't see it.
        """

        return (
            self.handler.get_accessible_conversations(user)
            .using(using)
            .select_related("agent__workspace")
            .filter(id=conversation_id)
            .first()
        )

    def _can_read_agent_conversations(
        self, user: AbstractUser, agent: AgentApplication
    ) -> bool:
        """
        :param user: The user asking.
        :param agent: The agent, with its workspace.
        :return: Whether the user may read the agent's conversations.
        """

        return CoreHandler().check_permissions(
            user,
            ReadAgentConversationsOperationType.type,
            workspace=agent.workspace,
            context=agent,
            raise_permission_exceptions=False,
        )

    def can_read_conversation(self, user: AbstractUser, conversation_id: int) -> bool:
        """
        Check that the user sees the conversation, their own or a shared one, in an
        untrashed Agent whose conversations they may still read.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :return: Whether the user may read the conversation.
        """

        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            return False
        return self._can_read_agent_conversations(user, conversation.agent)

    def can_follow_conversation(self, user: AbstractUser, conversation_id: int) -> bool:
        """
        Check participation or sharing and the current permission to read the agent.

        :param user: The user following the conversation.
        :param conversation_id: The id of the conversation.
        :return: Whether the user may follow the conversation's runs.
        """

        # A replica can lag behind the conversation that this tab's send just created.
        conversation = self._get_accessible_conversation(
            user, conversation_id, using=DEFAULT_DB_ALIAS
        )
        if conversation is None:
            return False
        return self._can_read_agent_conversations(user, conversation.agent)

    def can_cancel_conversation_run(
        self, user: AbstractUser, conversation_id: int
    ) -> bool:
        """
        Check that the user may stop the reply running in the conversation: reading
        is enough for their own, a shared one also needs the access of a
        configuration update.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :return: Whether the user may stop the run.
        """

        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            return False
        if not conversation.shared and conversation.owner_user_id != user.id:
            return False
        operations = [
            ReadAgentConversationsOperationType.type,
            *self.handler.get_shared_change_operations(conversation),
        ]
        agent = conversation.agent
        allowed = CoreHandler().check_multiple_permissions(
            [PermissionCheck(user, operation, agent) for operation in operations],
            workspace=agent.workspace,
        )
        return all(allowed.values())

    def _require_live_trigger(self, conversation: AgentConversation) -> None:
        """
        An unattended reply runs on its trigger's authority, so it stops once the
        trigger is gone, trashed or disabled.

        :param conversation: The shared conversation, with its trigger.
        :raises AgentTriggerOff: When the trigger is off, trashed or deleted.
        """

        trigger = conversation.trigger
        if trigger is None or trigger.trashed or not trigger.enabled:
            raise AgentTriggerOff

    def prepare_reply(
        self, reply_id: int, *, approval_actor_id: int | None = None
    ) -> AgentReplyRequest:
        """
        Load what a reply answers, or the paused run it continues, checking again
        that it may still be written: access and configuration can change while
        the reply waits. An approver needs to approve tool calls, a sender in a
        conversation a trigger started needs to continue it, and any other sender
        needs to send messages. An unattended reply needs its trigger alive and
        enabled.

        :param reply_id: The id of the reply.
        :param approval_actor_id: The actor whose decision resumed the reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists or its
            conversation is in the trash.
        :raises PermissionException: When the agent or its workspace is trashed, or
            the actor no longer has permission to continue the reply.
        :raises AgentTriggerOff: When the trigger of a shared conversation is off,
            trashed or deleted.
        :raises AgentNotReady: When the agent's configuration is no longer ready.
        :return: The instructions, the model and the tools, with the prompt and the
            earlier messages, or with the paused run and the approval decisions.
        """

        reply = self.handler.get_reply(reply_id)
        conversation = reply.conversation
        agent = conversation.agent
        # Workspace membership is part of the permission check below.
        if agent.trashed or agent.workspace is None or agent.workspace.trashed:
            raise PermissionDenied
        if reply.unattended:
            self._require_live_trigger(conversation)
        if approval_actor_id is not None or not reply.unattended:
            actor = (
                get_user_model().objects.filter(pk=approval_actor_id).first()
                if approval_actor_id is not None
                else reply.sender
            )
            if actor is None or not self.can_read_conversation(actor, conversation.id):
                raise PermissionDenied()
            if approval_actor_id is not None:
                operation = ApproveAgentToolCallsOperationType
            elif conversation.started_by_trigger:
                operation = ContinueAgentTriggeredConversationOperationType
            else:
                operation = CreateAgentMessageOperationType
            CoreHandler().check_permissions(
                actor, operation.type, workspace=agent.workspace, context=agent
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
        :raises ChatRunLimitReached: When a reply limit is reached.
        :return: The conversation, its first message and its reply, and whether they
            are new.
        """

        agent = self.get_authorized_agent(
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
            agent, or may not continue conversations a trigger started.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :raises AgentConversationWaitingForApproval: When the latest reply waits for
            the user to decide its held calls.
        :raises AgentNotReady: When the agent isn't ready for a new message.
        :raises ChatRunAlreadyActive: When the agent is still replying in this
            conversation.
        :raises ChatRunLimitReached: When a reply limit is reached.
        :return: The conversation, the message and its reply, and whether the message
            is new.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        operation = (
            ContinueAgentTriggeredConversationOperationType
            if conversation.started_by_trigger
            else CreateAgentMessageOperationType
        )
        CoreHandler().check_permissions(
            user, operation.type, workspace=agent.workspace, context=agent
        )
        validate_message_content(content)
        retry = self.handler.get_message_retry(conversation, uuid, content, user)
        if retry is not None:
            return retry
        if self.handler.get_waiting_reply(conversation) is not None:
            raise AgentConversationWaitingForApproval
        # Configuration may have changed while waiting for the conversation lock.
        agent = self.handler.get_agent(agent_id)
        self._require_ready(agent)
        result = self.handler.create_message(conversation, uuid, content, sender=user)
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
        Record decisions in a visible conversation, notify its readers, and
        continue the reply once all pending calls have a decision.

        :param user: The user deciding.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param decisions: Whether each held call may run, by approval id, with the
            reason for a rejection or the answer to a question.
        :param always_allow: Whether the tools of the approved calls stop asking
            first, which needs the access of a configuration update.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises PermissionException: When the user may not approve tool calls or
            may not update the configuration while always allowing.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :raises AgentToolApprovalNotPending: When an approval is decided already or
            isn't held by the reply waiting in the conversation.
        :raises AgentToolDecisionInvalid: When a question is answered without an
            answer or dismissed with a reason, or another call is decided with an
            answer.
        :raises AgentNotReady: When the agent isn't ready to continue the reply.
        :raises ChatRunLimitReached: When a reply limit is reached.
        :return: The reply with its approvals, the run continuing it or None while
            some held calls are still undecided, and the tools that stopped asking
            first.
        """

        operations = [
            ReadAgentConversationsOperationType.type,
            ApproveAgentToolCallsOperationType.type,
        ]
        if always_allow:
            operations += [
                UpdateApplicationOperationType.type,
                ReadAgentConfigurationOperationType.type,
            ]
        agent = self.get_authorized_agent(user, agent_id, *operations)
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
            self._stop_asking_first(user, agent_id, decided) if always_allow else []
        )
        application_pending_count_updated.send(
            self, application=agent, user_ids=conversation.pending_count_user_ids
        )
        run_id = None
        if all_decided:
            self._require_ready(self.handler.get_agent(agent_id))
            run_id = self.handler.resume_reply(reply, user).id
        agent_conversation_activity.send(
            self, conversation=conversation, user=user, run_id=run_id
        )
        return AgentToolDecisionsResult(
            reply, approved_tools, rejected_tools, always_allowed_tools, run_id
        )

    def _stop_asking_first(
        self,
        user: AbstractUser,
        agent_id: int,
        approvals: list[AgentToolApproval],
    ) -> list[str]:
        """
        Stop asking first for the tools of the approved calls, telling the Agent's
        open pages when its configuration changed. An action only stops asking
        while it's still the one whose call was approved.

        :param user: The user deciding, already allowed to update the configuration.
        :param agent_id: The id of the Agent.
        :param approvals: The decisions saved in this request.
        :return: The tools that stopped asking first.
        """

        approved = {
            approval.tool_name: approval.tool_key
            for approval in approvals
            if approval.status == AgentToolApproval.Status.APPROVED
        }
        # Locked after the conversation, as trashing it needs the Agent row too.
        agent = self.handler.get_agent(agent_id, for_update=True)
        stopped = self.handler.stop_asking_first(agent, list(approved))
        if stopped:
            application_updated.send(self, application=agent, user=user)
        for tool in self.handler.get_action_tools(agent):
            if tool.ask_first and approved.get(tool.type) == tool.approval_key:
                updated = AgentActionHandler().update_action(
                    tool.action, ask_first=False
                )
                # No session edited the action, so the approver's own is told too.
                agent_action_updated.send(self, action=updated.action, user=None)
                stopped.append(tool.type)
        return stopped
