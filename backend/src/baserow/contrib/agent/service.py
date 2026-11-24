from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import F, QuerySet

from rest_framework.exceptions import ValidationError

from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.models import UserProfile
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.signals import application_pending_count_updated, application_updated
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck

from .action_tools.handler import AgentActionHandler
from .action_tools.signals import agent_action_updated
from .api.serializers import AgentConversationUserSerializer
from .constants import AgentReadinessState
from .exceptions import (
    AgentConversationDoesNotExist,
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
    agent_conversation_left,
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

# Members checked per query while listing approvers, so few approvers stay cheap.
APPROVER_CHECK_BATCH_SIZE = 100


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
        shared: bool | None = None,
        started_by_trigger: bool | None = None,
        last_reply_failed: bool | None = None,
    ) -> QuerySet[AgentConversation]:
        """
        Return the user's own private conversations and the shared ones, never
        another owner's private ones.

        :param user: The user listing conversations.
        :param agent_id: The id of the agent.
        :param cursor: The last conversation of the previous page, to continue after.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :param pinned: Only pinned or unpinned conversations, or both when omitted.
        :param has_pending_approvals: Only conversations with or without pending calls.
        :param shared: Only shared or private conversations, or both when omitted.
        :param started_by_trigger: Only conversations a trigger started or not, or
            both when omitted.
        :param last_reply_failed: Only conversations whose latest reply failed or
            not, or both when omitted.
        :return: The conversations, pinned first, then most recently active.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.list_conversations(
            agent,
            user,
            cursor,
            pinned,
            has_pending_approvals,
            shared,
            started_by_trigger,
            last_reply_failed,
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
        :return: The conversation, and its messages newest first with their senders.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(agent, user, conversation_uuid)
        return conversation, conversation.messages.select_related(
            "sender", "stopped_by"
        ).prefetch_related("approvals")

    @staticmethod
    def _may_change(user: AbstractUser, conversation: AgentConversation) -> bool:
        """
        :param user: The user changing the conversation.
        :param conversation: The conversation being changed.
        :return: False for a private conversation the user only takes part in, as
            only its owner changes it, not those asked to approve in it.
        """

        return conversation.shared or conversation.owner_user_id == user.id

    def _check_shared_change(
        self,
        user: AbstractUser,
        agent: AgentApplication,
        conversation: AgentConversation,
    ) -> None:
        """
        Only its owner changes a private conversation. A shared conversation is
        the agent's own record, so changing it needs the access of a
        configuration update on top of the conversation operation.

        :param user: The user changing the conversation.
        :param agent: The agent, with its workspace.
        :param conversation: The conversation being changed.
        :raises PermissionException: When the user doesn't own the private
            conversation, or may not update the agent for a shared one.
        """

        if not self._may_change(user, conversation):
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
    def share_conversation(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> AgentConversationUpdated:
        """
        Share one of the user's private conversations with everyone who may read
        the agent's conversations, and add it to their lists.

        :param user: The user sharing the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the user may not update conversations of
            the agent.
        :raises AgentConversationDoesNotExist: When the user owns no conversation
            with this uuid in the agent.
        :return: The conversation, with no new values when it was shared already.
        """

        agent = self.get_authorized_agent(
            user, agent_id, UpdateAgentConversationOperationType.type
        )
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        if conversation.owner_user_id != user.id:
            raise AgentConversationDoesNotExist
        updated = self.handler.share_conversation(conversation)
        if updated.new_values:
            agent_conversation_updated.send(
                self, conversation=conversation, user=user, values=updated.new_values
            )
            if self.handler.conversation_has_pending_approvals(conversation.id):
                application_pending_count_updated.send(
                    self,
                    application=agent,
                    user_ids=conversation.pending_count_user_ids,
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

    def _get_own_private_conversation(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        for_update: bool = False,
    ) -> AgentConversation:
        """
        :param user: The user asking.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param for_update: Whether to lock the conversation until the transaction
            ends.
        :raises PermissionException: When the user may not read the agent's
            conversations, or doesn't own the private conversation.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The conversation.
        """

        agent = self.get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=for_update
        )
        if conversation.shared or conversation.owner_user_id != user.id:
            raise PermissionDenied()
        return conversation

    def _filter_approvers(
        self, agent: AgentApplication, users: list[AbstractUser]
    ) -> list[AbstractUser]:
        """
        :param agent: The agent, with its workspace.
        :param users: The workspace members to check.
        :return: Those who may read the agent's conversations and approve its
            tool calls, in the given order.
        """

        checks = {
            user: [
                PermissionCheck(user, operation, agent)
                for operation in (
                    ReadAgentConversationsOperationType.type,
                    ApproveAgentToolCallsOperationType.type,
                )
            ]
            for user in users
        }
        allowed = CoreHandler().check_multiple_permissions(
            [check for user_checks in checks.values() for check in user_checks],
            workspace=agent.workspace,
        )
        return [
            user
            for user, user_checks in checks.items()
            if all(allowed[check] for check in user_checks)
        ]

    def _get_member_ids(
        self, agent: AgentApplication, exclude_ids: list[int], search: str = ""
    ) -> QuerySet:
        """
        :param agent: The agent, with its workspace.
        :param exclude_ids: The ids of the people to leave out.
        :param search: Only people whose name or email contains it.
        :return: The ids of the active people in the agent's workspace, by name.
        """

        return (
            UserSubjectType()
            .get_options_queryset(agent.workspace, search, exclude_ids)
            .filter(subject_user_type=UserProfile.UserType.HUMAN)
            .order_by("subject_name", "subject_id")
            .values_list("subject_id", flat=True)
        )

    def list_approver_candidates(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        search: str,
        limit: int,
    ) -> list[AbstractUser]:
        """
        List the members the owner of a private conversation may ask to decide
        the held calls of its waiting reply. Members are checked a batch at a
        time until the limit is reached, so a page doesn't check everyone.

        :param user: The owner asking.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param search: Only members whose name or email contains it.
        :param limit: The most members to return.
        :raises PermissionException: When the user doesn't own the private
            conversation.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The first members by name who may approve tool calls and don't
            take part yet, or none when no reply waits.
        """

        conversation = self._get_own_private_conversation(
            user, agent_id, conversation_uuid
        )
        if self.handler.get_waiting_reply(conversation) is None:
            return []
        agent = conversation.agent
        member_ids = self._get_member_ids(
            agent, list(conversation.participants.values_list("id", flat=True)), search
        )
        approvers = []
        offset = 0
        while len(approvers) < limit:
            batch_ids = list(member_ids[offset : offset + APPROVER_CHECK_BATCH_SIZE])
            members = get_user_model().objects.in_bulk(batch_ids)
            approvers += self._filter_approvers(
                agent, [members[pk] for pk in batch_ids if pk in members]
            )
            if len(batch_ids) < APPROVER_CHECK_BATCH_SIZE:
                break
            offset += APPROVER_CHECK_BATCH_SIZE
        return approvers[:limit]

    @transaction.atomic
    def request_approval(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        user_ids: list[int],
    ) -> AgentConversation:
        """
        Add members to a private conversation so they can decide the held calls
        of its waiting reply. They keep seeing it afterwards.

        :param user: The owner asking.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param user_ids: The ids of the members to add.
        :raises PermissionException: When the user doesn't own the private
            conversation.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :raises AgentToolApprovalNotPending: When no reply waits.
        :raises ValidationError: When a member may not approve tool calls.
        :return: The conversation.
        """

        conversation = self._get_own_private_conversation(
            user, agent_id, conversation_uuid, for_update=True
        )
        if self.handler.get_waiting_reply(conversation) is None:
            raise AgentToolApprovalNotPending()
        agent = conversation.agent
        member_ids = self._get_member_ids(agent, [user.id]).filter(
            subject_id__in=user_ids
        )
        approvers = self._filter_approvers(
            agent, list(get_user_model().objects.filter(id__in=member_ids))
        )
        if len(approvers) != len(set(user_ids)):
            raise ValidationError({"user_ids": "Choose members who may approve."})
        conversation.participants.add(*approvers)
        self._send_participants_updated(user, conversation)
        application_pending_count_updated.send(
            self,
            application=agent,
            user_ids=[approver.id for approver in approvers],
        )
        return conversation

    @transaction.atomic
    def leave_conversation(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> AgentConversation:
        """
        Remove the user from a private conversation they take part in, which the
        others keep. Its owner left alone trashes it, as deleting does. Once the
        owner has left, the last one to leave deletes it for good: only an owner's
        trash may list a private conversation.

        :param user: The participant leaving.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :raises PermissionException: When the conversation is shared, or the user
            may not delete conversations of the agent.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :return: The conversation, trashed when its owner was alone in it.
        """

        agent = self.get_authorized_agent(
            user, agent_id, DeleteAgentConversationOperationType.type
        )
        conversation = self.handler.get_conversation(
            agent, user, conversation_uuid, for_update=True
        )
        if conversation.shared:
            raise PermissionDenied()
        if not conversation.participants.exclude(id=user.id).exists():
            if conversation.owner_user_id == user.id:
                return self.delete_conversation(user, agent_id, conversation_uuid)
            self.handler.delete_conversation_forever(conversation)
        else:
            conversation.participants.remove(user)
            self._send_participants_updated(user, conversation)
        agent_conversation_left.send(self, conversation=conversation, user=user)
        application_pending_count_updated.send(
            self, application=conversation.agent, user_ids=[user.id]
        )
        return conversation

    def _send_participants_updated(
        self, user: AbstractUser, conversation: AgentConversation
    ) -> None:
        """
        Tell the participants' sessions who takes part in the conversation now.

        :param user: The acting user.
        :param conversation: The private conversation.
        """

        participants = AgentConversationUserSerializer(
            conversation.participants.all(), many=True
        ).data
        agent_conversation_updated.send(
            self,
            conversation=conversation,
            user=user,
            values={"participants": participants},
        )

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
        Check that the user may follow the conversation's runs: their own with one
        query, as it runs on the websocket's shared thread, a shared one also with
        the permission to read the agent's conversations.

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
        return not conversation.shared or self._can_read_agent_conversations(
            user, conversation.agent
        )

    def can_cancel_conversation_run(
        self, user: AbstractUser, conversation_id: int, reply_id: int
    ) -> bool:
        """
        Check that the user may stop a reply running in the conversation: reading
        is enough for one that answers them, even when someone else's decision
        resumed it. Otherwise only those who change the conversation may, and a
        shared one also needs a configuration update.

        :param user: The user asking.
        :param conversation_id: The id of the conversation.
        :param reply_id: The id of the reply the run writes.
        :return: Whether the user may stop the run.
        """

        conversation = self._get_accessible_conversation(user, conversation_id)
        if conversation is None:
            return False
        operations = [ReadAgentConversationsOperationType.type]
        answers_user = AgentMessage.objects.filter(
            id=reply_id, conversation_id=conversation_id, sender_id=user.id
        ).exists()
        if not answers_user:
            if not self._may_change(user, conversation):
                return False
            operations += self.handler.get_shared_change_operations(conversation)
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

        :param conversation: The conversation the trigger started, with its trigger.
        :raises AgentTriggerOff: When the trigger is off, trashed or deleted.
        """

        trigger = conversation.trigger
        if trigger is None or trigger.trashed or not trigger.enabled:
            raise AgentTriggerOff

    def _get_reply_actor(
        self, reply: AgentMessage, approver_id: int | None
    ) -> tuple[AbstractUser | None, str] | None:
        """
        :param reply: The reply, with its conversation and sender.
        :param approver_id: The id of the person whose decision resumes the reply.
        :return: The person who must still be allowed to write the reply, None
            when deleted, with the operation they need, or None for an unattended
            reply nobody resumed.
        """

        if approver_id is not None:
            approver = get_user_model().objects.filter(id=approver_id).first()
            return approver, ApproveAgentToolCallsOperationType.type
        if reply.unattended:
            return None
        if reply.conversation.started_by_trigger:
            return reply.sender, ContinueAgentTriggeredConversationOperationType.type
        return reply.sender, CreateAgentMessageOperationType.type

    def prepare_reply(
        self, reply_id: int, approver_id: int | None = None
    ) -> AgentReplyRequest:
        """
        Load what a reply answers, or the paused run it continues, checking again
        that it may still be written: access and configuration can change while
        the reply waits. An unattended reply needs its trigger alive and enabled.
        The person whose decision resumes the reply must still see the
        conversation and approve tool calls; otherwise the person it answers must
        still see it and send messages, or continue it when a trigger started it.

        :param reply_id: The id of the reply.
        :param approver_id: The id of the person whose decision resumes the reply.
        :raises AgentConversationDoesNotExist: When the reply no longer exists or its
            conversation is in the trash.
        :raises PermissionException: When the agent or its workspace is trashed, or
            the person checked was deleted, no longer sees the conversation or
            lost the permission.
        :raises AgentTriggerOff: When the trigger that started the conversation is
            off, trashed or deleted.
        :raises AgentNotReady: When the agent's configuration is no longer ready.
        :return: The instructions, the model and the tools, with the prompt and the
            earlier messages, or with the paused run and the decisions.
        """

        reply = self.handler.get_reply(reply_id)
        conversation = reply.conversation
        agent = conversation.agent
        # Workspace membership is part of the permission check below.
        if agent.trashed or agent.workspace is None or agent.workspace.trashed:
            raise PermissionDenied
        if reply.unattended:
            self._require_live_trigger(conversation)
        checked = self._get_reply_actor(reply, approver_id)
        if checked is not None:
            actor, operation = checked
            if actor is None or not self.can_read_conversation(actor, conversation.id):
                raise PermissionDenied
            CoreHandler().check_permissions(
                actor, operation, workspace=agent.workspace, context=agent
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
        is_test: bool = False,
        title: str | None = None,
    ) -> AgentMessageCreated:
        """
        Start a private conversation, or return its first message on a retry.

        :param user: The user starting the conversation.
        :param agent_id: The id of the agent.
        :param is_test: Whether Kuma starts it to test the Agent, so every tool
            that changes data asks first.
        :param title: The title, instead of one taken from the first message.
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
            agent, user, uuid, message_uuid, content, is_test=is_test, title=title
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
        Send a message to a conversation the user sees, or return it on a retry.

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
        result = self.handler.create_message(conversation, uuid, content, user)
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
        Approve or reject held calls of the reply waiting in a conversation the
        user sees, tell the other sessions of those who may decide what is left,
        and continue the reply once nothing is.

        :param user: The user deciding.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param decisions: Whether each held call may run, by approval id, with the
            reason for a rejection.
        :param always_allow: Whether the tools of the approved calls stop asking
            first, which needs the access of a configuration update.
        :raises FeatureDisabledException: When Agents are disabled.
        :raises PermissionException: When the user may not approve tool calls of
            the agent, or may not update its configuration while always allowing.
        :raises AgentConversationDoesNotExist: When the user sees no conversation
            with this uuid in the agent.
        :raises AgentToolApprovalNotPending: When an approval is decided already or
            isn't held by the reply waiting in the conversation.
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
