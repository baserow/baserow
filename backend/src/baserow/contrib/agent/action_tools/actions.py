from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import ApplicationActionScopeType

from .service import AgentActionService


class CreateAgentActionActionType(ActionType):
    """Audit action creation without retaining email content in the action log."""

    type = "create_agent_action"
    description = ActionTypeDescription(
        _("Create agent action"),
        _(
            "Action (%(action_id)s) of type %(action_type)s created in agent (%(agent_id)s)."
        ),
    )
    analytics_params = ["agent_id", "action_type"]

    @dataclass
    class Params:
        agent_id: int
        action_id: int
        action_type: str

    @classmethod
    def scope(cls, agent_id):
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(cls, user, agent_id, service_type_name, service=None, **values):
        action = AgentActionService().create_action(
            user, agent_id, service_type_name, service_values=service, **values
        )
        cls.register_action(
            user,
            cls.Params(agent_id, action.id, service_type_name),
            ApplicationActionScopeType.value(agent_id),
            action.agent.workspace,
        )
        return action


class UpdateAgentActionActionType(ActionType):
    """Audit changed configuration fields, matching the Agent's other settings."""

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
    def scope(cls, agent_id):
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(cls, user, agent_id, action_id, service=None, **values):
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
                ApplicationActionScopeType.value(agent_id),
                action.agent.workspace,
            )
        return action


class DeleteAgentActionActionType(ActionType):
    """Trash configuration only; already prepared proposals remain independent."""

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
    def scope(cls, agent_id):
        return ApplicationActionScopeType.value(agent_id)

    @classmethod
    @transaction.atomic
    def do(cls, user, agent_id, action_id):
        action = AgentActionService().delete_action(user, agent_id, action_id)
        cls.register_action(
            user,
            cls.Params(agent_id, action.id, action.service.get_type().type),
            ApplicationActionScopeType.value(agent_id),
            action.agent.workspace,
        )
