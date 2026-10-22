from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.signals import application_updated
from baserow.core.types import PermissionCheck

from .exceptions import AgentNotReady
from .handler import AgentHandler
from .models import AgentApplication, AgentConversation, AgentMessage
from .operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
)
from .signals import agent_conversation_updated
from .types import AgentConfiguration, AgentConfigurationUpdated, AgentMessageCreated
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

    @transaction.atomic
    def update_configuration(
        self, user: AbstractUser, agent_id: int, **values: str | None
    ) -> AgentConfigurationUpdated:
        """
        Save part of the configuration for a user who may update and read it.

        :param user: The user updating the configuration.
        :param agent_id: The id of the Agent.
        :param values: The configuration values to set, by field name.
        :raises PermissionException: When the user may not update the Agent or read
            its configuration.
        :return: The Agent, the names of the fields that changed and the resulting
            configuration.
        """

        agent = self._get_authorized_agent(
            user,
            agent_id,
            UpdateApplicationOperationType.type,
            ReadAgentConfigurationOperationType.type,
            for_update=True,
        )
        updated = self.handler.update_configuration(agent, **values)
        if updated.changed_fields:
            # Open pages refresh readiness from this public application payload.
            application_updated.send(self, application=agent, user=user)
        return updated

    def list_conversations(
        self, user: AbstractUser, agent_id: int
    ) -> QuerySet[AgentConversation]:
        """
        Return only the user's own conversations, never another owner's.

        :param user: The user listing their conversations.
        :param agent_id: The id of the agent.
        :raises PermissionException: When the user may not read conversations of the
            agent.
        :return: The user's conversations, most recently updated first.
        """

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.list_conversations(agent, user)

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
        :return: The conversation, and its messages newest first with their turns
            and authors.
        """

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        conversation = self.handler.get_conversation(agent, user, conversation_uuid)
        return conversation, conversation.messages.select_related("turn", "author_user")

    def _require_ready(self, agent: AgentApplication) -> None:
        """Reject new content without leaking privileged setting diagnostics."""

        if self.handler.get_configuration(agent)["readiness"] != "ready":
            raise AgentNotReady

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
        :raises PermissionException: When the user may not start conversations with
            the agent.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentConversationDoesNotExist: When the uuid belongs to another
            owner's or agent's conversation.
        :raises AgentMessageConflict: When the uuid was accepted with another first
            message.
        :raises AgentNotReady: When the agent isn't ready for a new conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation and its first message, and whether they are new.
        """

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
            agent_conversation_updated.send(
                self, conversation=result.conversation, user=user
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
        :raises PermissionException: When the user may not send messages to the
            agent.
        :raises AgentConversationDoesNotExist: When the user has no conversation with
            this uuid in the agent.
        :raises ValidationError: When the content is blank or too long.
        :raises AgentMessageConflict: When the uuid was accepted with other content.
        :raises AgentNotReady: When the agent isn't ready for a new message.
        :raises ChatRunAlreadyActive: When the agent is still replying in this
            conversation.
        :raises ChatRunLimitReached: When the workspace has its maximum of replies
            running.
        :return: The conversation and the message, and whether the message is new.
        """

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
        # Configuration may have changed while waiting for the conversation lock.
        agent = self.handler.get_agent(agent_id)
        self._require_ready(agent)
        result = self.handler.create_message(conversation, uuid, content, user)
        if result.created:
            agent_conversation_updated.send(
                self, conversation=result.conversation, user=user
            )
        return result

