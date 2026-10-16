from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler
from baserow.core.operations import (
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.signals import application_updated

from .exceptions import AgentConfigurationInvalid
from .handler import AgentHandler
from .models import AgentApplication, AgentConversation, AgentMessage
from .operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    ReadAgentConversationsOperationType,
    ReadAgentSettingsOperationType,
)
from .types import (
    AgentConfiguration,
    AgentConfigurationUpdated,
    AgentMessageCreated,
    AgentReadiness,
)
from .validators import validate_message_content


class AgentService:
    def __init__(self):
        self.handler = AgentHandler()

    def _get_authorized_agent(
        self,
        user: AbstractUser,
        agent_id: int,
        operation: str,
        for_update: bool = False,
    ) -> AgentApplication:
        """Authorize at the owning application's scope, never a thread scope."""

        agent = self.handler.get_agent(agent_id, for_update=for_update)
        CoreHandler().check_permissions(
            user, operation, workspace=agent.workspace, context=agent
        )
        return agent

    def get_readiness(self, user: AbstractUser, agent_id: int) -> AgentReadiness:
        """Expose only coarse readiness to ordinary application readers."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadApplicationOperationType.type
        )
        return {"state": self.handler.get_configuration(agent)["state"]}

    def get_configuration(
        self, user: AbstractUser, agent_id: int
    ) -> AgentConfiguration:
        """Return actual setting values only with the privileged settings operation."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentSettingsOperationType.type
        )
        return self.handler.get_configuration(agent)

    @transaction.atomic
    def update_configuration(
        self, user: AbstractUser, agent_id: int, **values
    ) -> AgentConfigurationUpdated:
        """Save an authorized partial draft and emit a name-only application update."""

        agent = self._get_authorized_agent(
            user, agent_id, UpdateApplicationOperationType.type, for_update=True
        )
        updated = self.handler.update_configuration(agent, **values)
        if updated.changed_fields:
            # The existing serializer deliberately carries only public name metadata.
            application_updated.send(self, application=agent, user=user)
        return updated

    def list_conversations(
        self, user: AbstractUser, agent_id: int
    ) -> QuerySet[AgentConversation]:
        """Application access never grants access to another owner's transcripts."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.list_conversations(agent, user)

    def list_messages(
        self, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> QuerySet[AgentMessage]:
        """Return this owner's messages after checking current application access."""

        agent = self._get_authorized_agent(
            user, agent_id, ReadAgentConversationsOperationType.type
        )
        return self.handler.get_conversation(
            agent, user, conversation_uuid
        ).messages.all()

    def _require_ready(self, agent: AgentApplication) -> None:
        """Reject new content without leaking privileged setting diagnostics."""

        if self.handler.get_configuration(agent)["state"] != "ready":
            raise AgentConfigurationInvalid

    @transaction.atomic
    def create_conversation(
        self,
        user: AbstractUser,
        agent_id: int,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Accept the first message, or return it for an authorized retry."""

        agent = self._get_authorized_agent(
            user, agent_id, CreateAgentConversationOperationType.type, for_update=True
        )
        CoreHandler().check_permissions(
            user,
            CreateAgentMessageOperationType.type,
            workspace=agent.workspace,
            context=agent,
        )
        validate_message_content(content)
        retry = self.handler.get_creation_retry(
            agent, user, uuid, message_uuid, content
        )
        if retry is not None:
            return retry
        self._require_ready(agent)
        return self.handler.create_conversation(
            agent, user, uuid, message_uuid, content
        )

    @transaction.atomic
    def create_message(
        self,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Recheck ownership, access and saved readiness before accepting content."""

        agent = self._get_authorized_agent(
            user, agent_id, CreateAgentMessageOperationType.type, for_update=True
        )
        conversation = self.handler.get_conversation(agent, user, conversation_uuid)
        validate_message_content(content)
        retry = self.handler.get_message_retry(conversation, uuid, content)
        if retry is not None:
            return retry
        self._require_ready(agent)
        return self.handler.create_message(conversation, user, uuid, content)
