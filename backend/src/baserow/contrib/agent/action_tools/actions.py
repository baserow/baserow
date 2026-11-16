from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.contrib.agent.models import AgentAction
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType

from .service import AgentActionService


class CreateAgentActionActionType(ActionType):
    """Adds an action to an Agent; not undoable, like the rest of its configuration."""

    type = "create_agent_action"
    description = ActionTypeDescription(
        _("Create agent action"),
        _(
            "Action (%(action_id)s) of type %(action_type)s created in agent "
            "(%(agent_id)s)."
        ),
    )
    analytics_params = ["agent_id", "action_type"]

    @dataclass
    class Params:
        agent_id: int
        action_id: int
        action_type: str

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        service_type_name: str,
        service: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentAction:
        """
        Add an action to an Agent and audit its type, never its content.

        :param user: The user adding the action.
        :param agent_id: The id of the Agent.
        :param service_type_name: The service type of the action.
        :param service: Service values replacing the type's defaults, or None.
        :param values: Editable fields replacing the type's defaults.
        :return: The created action.
        """

        action = AgentActionService().create_action(
            user, agent_id, service_type_name, service_values=service, **values
        )
        cls.register_action(
            user,
            cls.Params(agent_id, action.id, service_type_name),
            cls.scope(agent_id),
            action.agent.workspace,
        )
        return action


class UpdateAgentActionActionType(ActionType):
    """Changes an action's fields or service; audits which, never their content."""

    type = "update_agent_action"
    description = ActionTypeDescription(
        _("Update agent action"),
        _("Action (%(action_id)s) updated in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "action_type", "changed_fields"]

    @dataclass
    class Params:
        agent_id: int
        action_id: int
        action_type: str
        changed_fields: list[str]

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        action_id: int,
        service: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentAction:
        """
        Change an action and audit the changed fields. Nothing is audited when
        nothing changed.

        :param user: The user changing the action.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        :param service: The service values to change, or None.
        :param values: The editable fields to change.
        :return: The action.
        """

        updated = AgentActionService().update_action(
            user, agent_id, action_id, service_values=service, **values
        )
        action = updated.action
        if updated.changed_fields:
            cls.register_action(
                user,
                cls.Params(
                    agent_id,
                    action.id,
                    action.service.get_type().type,
                    updated.changed_fields,
                ),
                cls.scope(agent_id),
                action.agent.workspace,
            )
        return action


class DeleteAgentActionActionType(ActionType):
    """Trashes an action with its service; calls held for approval are then denied."""

    type = "delete_agent_action"
    description = ActionTypeDescription(
        _("Delete agent action"),
        _("Action (%(action_id)s) deleted in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "action_type"]

    @dataclass
    class Params:
        agent_id: int
        action_id: int
        action_type: str

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        :param agent_id: The id of the Agent.
        :return: The application scope of the Agent.
        """

        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(cls, user: AbstractUser, agent_id: int, action_id: int) -> None:
        """
        :param user: The user deleting the action.
        :param agent_id: The id of the Agent.
        :param action_id: The id of one of its actions.
        """

        action = AgentActionService().delete_action(user, agent_id, action_id)
        cls.register_action(
            user,
            cls.Params(agent_id, action.id, action.service.get_type().type),
            cls.scope(agent_id),
            action.agent.workspace,
        )
