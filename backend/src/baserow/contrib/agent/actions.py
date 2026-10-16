from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType

from .models import AgentApplication
from .service import AgentService
from .types import AgentMessageCreated


class CreateAgentConversationActionType(ActionType):
    type = "create_agent_conversation"
    description = ActionTypeDescription(
        _("Create agent conversation"),
        _("Conversation (%(conversation_id)s) created in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "conversation_id"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        message_id: int

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        uuid: UUID,
        message_uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Record first acceptance with IDs only; retries have no audit side effects."""

        result = AgentService().create_conversation(
            user, agent_id, uuid, message_uuid, content
        )
        if result.created:
            cls.register_action(
                user,
                cls.Params(agent_id, result.conversation.id, result.message.id),
                cls.scope(agent_id),
                result.conversation.agent.workspace,
            )
        return result

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)


class CreateAgentMessageActionType(ActionType):
    type = "create_agent_message"
    description = ActionTypeDescription(
        _("Create agent message"),
        _("Message (%(message_id)s) created in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        message_id: int

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        uuid: UUID,
        content: str,
    ) -> AgentMessageCreated:
        """Audit a new append without putting private content in event parameters."""

        result = AgentService().create_message(
            user, agent_id, conversation_uuid, uuid, content
        )
        if result.created:
            cls.register_action(
                user,
                cls.Params(agent_id, result.conversation.id, result.message.id),
                cls.scope(agent_id),
                result.conversation.agent.workspace,
            )
        return result

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)


class UpdateAgentConfigurationActionType(ActionType):
    type = "update_agent_configuration"
    description = ActionTypeDescription(
        _("Update agent configuration"),
        _("Configuration updated for agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "changed_fields"]

    @dataclass
    class Params:
        agent_id: int
        changed_fields: list[str]

    @classmethod
    @transaction.atomic
    def do(cls, user: AbstractUser, agent_id: int, **values) -> AgentApplication:
        """Record changed field names while keeping their values out of audit logs."""

        updated = AgentService().update_configuration(user, agent_id, **values)
        if updated.changed_fields:
            cls.register_action(
                user,
                cls.Params(agent_id, updated.changed_fields),
                cls.scope(agent_id),
                updated.agent.workspace,
            )
        return updated.agent

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)
