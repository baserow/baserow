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
from .types import (
    AgentConfiguration,
    AgentMessageCreated,
    AgentToolDecision,
    AgentToolDecisionsResult,
)


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


class DecideAgentToolApprovalsActionType(ActionType):
    type = "decide_agent_tool_approvals"
    description = ActionTypeDescription(
        _("Decide agent tool approvals"),
        _("Held steps of reply (%(reply_id)s) decided in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "approved", "rejected", "always_allowed_tools"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        reply_id: int
        approved: list[str]
        rejected: list[str]
        always_allowed_tools: list[str]

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        decisions: list[AgentToolDecision],
        always_allow: bool = False,
    ) -> AgentToolDecisionsResult:
        """
        Approve or reject held calls, auditing the tools decided and those that
        stopped asking first, but never the rejection reasons, which can quote the
        private conversation.

        :param user: The user deciding.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param decisions: Whether each held call may run, by approval id, with the
            reason for a rejection.
        :param always_allow: Whether the tools of the approved calls stop asking
            first.
        :return: The saved decisions, the tools that stopped asking first and the
            run continuing the reply.
        """

        result = AgentService().decide_approvals(
            user, agent_id, conversation_uuid, decisions, always_allow
        )
        reply = result.reply
        cls.register_action(
            user,
            cls.Params(
                agent_id,
                reply.conversation_id,
                reply.id,
                approved=result.approved_tools,
                rejected=result.rejected_tools,
                always_allowed_tools=result.always_allowed_tools,
            ),
            cls.scope(agent_id),
            reply.conversation.agent.workspace,
        )
        return result

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)


class UpdateAgentConversationActionType(UndoableActionType):
    type = "update_agent_conversation"
    description = ActionTypeDescription(
        _("Update agent conversation"),
        _("Conversation (%(conversation_id)s) updated in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "conversation_id"]

    @dataclass
    class Params:
        agent_id: int
        conversation_id: int
        conversation_uuid: str
        original_values: dict[str, str | bool]
        new_values: dict[str, str | bool]

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        conversation_uuid: UUID,
        **values: str | bool,
    ) -> AgentConversation:
        """
        Update a conversation, such as its title. The description names it by id
        because titles are private.

        :param user: The user updating the conversation.
        :param agent_id: The id of the agent.
        :param conversation_uuid: The uuid of the conversation.
        :param values: The values to set, by field name.
        :return: The updated conversation.
        """

        updated = AgentService().update_conversation(
            user, agent_id, conversation_uuid, **values
        )
        if updated.new_values:
            cls.register_action(
                user,
                cls.Params(
                    agent_id,
                    updated.conversation.id,
                    str(updated.conversation.uuid),
                    updated.original_values,
                    updated.new_values,
                ),
                cls.scope(agent_id),
                updated.conversation.agent.workspace,
            )
        return updated.conversation

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        AgentService().update_conversation(
            user,
            params.agent_id,
            UUID(params.conversation_uuid),
            **params.original_values,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        AgentService().update_conversation(
            user, params.agent_id, UUID(params.conversation_uuid), **params.new_values
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
