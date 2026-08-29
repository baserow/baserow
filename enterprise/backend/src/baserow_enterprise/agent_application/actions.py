from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType

from .models import AgentDefinition
from .service import AgentApplicationService

AGENT_ACTION_CONTEXT = _('in application "%(application_name)s" (%(application_id)s).')


class UpdateAgentDefinitionActionType(UndoableActionType):
    type = "update_agent_definition"
    description = ActionTypeDescription(
        _("Update agent"),
        _('Agent "%(agent_name)s" (%(agent_id)s) updated'),
        AGENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        agent_id: int
        agent_name: str
        original_values: dict
        new_values: dict

    @classmethod
    def do(cls, user: AbstractUser, agent_id: int, new_values: dict) -> AgentDefinition:
        service = AgentApplicationService()
        agent = service.get_agent(user, agent_id)
        original_values = {
            key: getattr(agent, key)
            for key in new_values
            if key in service.handler.allowed_agent_fields
        }

        agent = service.update_agent(user, agent_id, **new_values)

        cls.register_action(
            user=user,
            params=cls.Params(
                agent.application_id,
                agent.application.name,
                agent.id,
                agent.name,
                original_values,
                {key: getattr(agent, key) for key in original_values},
            ),
            scope=cls.scope(agent.application_id),
            workspace=agent.application.workspace,
        )
        return agent

    @classmethod
    def scope(cls, application_id):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        AgentApplicationService().update_agent(
            user, params.agent_id, **params.original_values
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        AgentApplicationService().update_agent(
            user, params.agent_id, **params.new_values
        )
