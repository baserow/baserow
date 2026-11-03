from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler

from .models import AgentConversation
from .service import AgentService
from .types import AgentConfiguration, AgentMessageCreated


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
        """
        Start a conversation, registering the action by ids and only once.

        :param user: The user starting the conversation.
        :param agent_id: The id of the agent.
        :param uuid: The uuid of the conversation.
        :param message_uuid: The uuid of the first message.
        :param content: The content of the first message.
        :return: The conversation and its first message, and whether they are new.
        """

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
        """
        Send a message, registering the action by ids and only once.

        :param user: The user sending the message.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param uuid: The uuid of the message.
        :param content: The content of the message.
        :return: The conversation and the message, and whether the message is new.
        """

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


class RenameAgentConversationActionType(UndoableActionType):
    type = "rename_agent_conversation"
    description = ActionTypeDescription(
        _("Rename agent conversation"),
        _("Conversation (%(conversation_id)s) renamed in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "conversation_id"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        conversation_uuid: str
        title: str
        original_title: str

    @classmethod
    @transaction.atomic
    def do(
        cls, user: AbstractUser, agent_id: int, conversation_uuid: UUID, title: str
    ) -> AgentConversation:
        """
        Rename a conversation. The description names it by id because titles are
        private.

        :param user: The user renaming the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param title: The new title.
        :return: The renamed conversation.
        """

        conversation, original_title = AgentService().rename_conversation(
            user, agent_id, conversation_uuid, title
        )
        cls.register_action(
            user,
            cls.Params(
                agent_id,
                conversation.id,
                str(conversation.uuid),
                conversation.title,
                original_title,
            ),
            cls.scope(agent_id),
            conversation.agent.workspace,
        )
        return conversation

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        AgentService().rename_conversation(
            user, params.agent_id, UUID(params.conversation_uuid), params.original_title
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        AgentService().rename_conversation(
            user, params.agent_id, UUID(params.conversation_uuid), params.title
        )


class DeleteAgentConversationActionType(UndoableActionType):
    type = "delete_agent_conversation"
    description = ActionTypeDescription(
        _("Delete agent conversation"),
        _("Conversation (%(conversation_id)s) deleted in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "conversation_id"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        conversation_uuid: str

    @classmethod
    @transaction.atomic
    def do(
        cls, user: AbstractUser, agent_id: int, conversation_uuid: UUID
    ) -> AgentConversation:
        """
        Move a conversation to the trash. Undoing restores it and redoing trashes
        it again.

        :param user: The user deleting the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :return: The trashed conversation.
        """

        conversation = AgentService().delete_conversation(
            user, agent_id, conversation_uuid
        )
        cls.register_action(
            user,
            cls.Params(agent_id, conversation.id, str(conversation.uuid)),
            cls.scope(agent_id),
            conversation.agent.workspace,
        )
        return conversation

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        TrashHandler.restore_item(user, "agent_conversation", params.conversation_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        AgentService().delete_conversation(
            user, params.agent_id, UUID(params.conversation_uuid)
        )


class UpdateAgentConfigurationActionType(ActionType):
    type = "update_agent_configuration"
    description = ActionTypeDescription(
        _("Update agent configuration"),
        _("Configuration updated for agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id"]

    @dataclass
    class Params:
        agent_id: int
        original_values: dict[str, str | int | list[str] | None]
        new_values: dict[str, str | int | list[str] | None]

    @classmethod
    def get_analytics_properties(cls, action_params: dict[str, Any]) -> dict[str, Any]:
        return {
            **super().get_analytics_properties(action_params),
            "changed_fields": [
                field
                for field, value in action_params["new_values"].items()
                if value != action_params["original_values"][field]
            ],
        }

    @classmethod
    def do(
        cls, user: AbstractUser, agent_id: int, **values: str | int | list[str] | None
    ) -> AgentConfiguration:
        """
        Update the configuration and audit its original and new values.

        :param user: The user updating the configuration.
        :param agent_id: The id of the Agent.
        :param values: The configuration values to set, by field name.
        :return: The resulting configuration.
        """

        updated = AgentService().update_configuration(user, agent_id, **values)
        if updated.original_values != updated.new_values:
            cls.register_action(
                user,
                cls.Params(agent_id, updated.original_values, updated.new_values),
                cls.scope(agent_id),
                updated.agent.workspace,
            )
        return updated.configuration

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)
