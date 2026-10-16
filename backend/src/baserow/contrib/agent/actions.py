from dataclasses import dataclass

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
