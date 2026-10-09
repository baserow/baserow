from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.agent_builder.handler import AgentHandler
from baserow_enterprise.agent_builder.service import AgentService
from baserow_enterprise.agent_builder.trash_types import AgentTrashableItemType

AGENT_BUILDER_ACTION_CONTEXT = _(
    'in agent builder "%(agent_builder_name)s" (%(agent_builder_id)s).'
)


class CreateAgentActionType(UndoableActionType):
    type = "create_agent"
    description = ActionTypeDescription(
        _("Create agent"),
        _('Agent "%(agent_name)s" (%(agent_id)s) created'),
        AGENT_BUILDER_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        agent_builder_id: int
        agent_builder_name: str
        agent_id: int
        agent_name: str

    @classmethod
    def do(cls, user, agent_builder_id: int, data: dict):
        agent = AgentService().create_agent(user, agent_builder_id, **data)
        cls.register_action(
            user,
            cls.Params(
                agent.agent_builder_id, agent.agent_builder.name, agent.id, agent.name
            ),
            cls.scope(agent.agent_builder_id),
            agent.agent_builder.workspace,
        )
        return agent

    @classmethod
    def scope(cls, agent_builder_id):
        return ApplicationActionScopeType.value(agent_builder_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        AgentService().delete_agent(user, params.agent_id)

    @classmethod
    def redo(cls, user, params, action_to_redo):
        TrashHandler.restore_item(user, AgentTrashableItemType.type, params.agent_id)


class UpdateAgentActionType(UndoableActionType):
    type = "update_agent"
    description = ActionTypeDescription(
        _("Update agent"),
        _('Agent "%(agent_name)s" (%(agent_id)s) updated'),
        AGENT_BUILDER_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        agent_builder_id: int
        agent_builder_name: str
        agent_id: int
        agent_name: str
        original_values: dict
        new_values: dict

    @classmethod
    def do(cls, user, agent_id: int, new_data: dict):
        updated = AgentService().update_agent(user, agent_id, **new_data)
        agent = updated.agent
        cls.register_action(
            user,
            cls.Params(
                agent.agent_builder_id,
                agent.agent_builder.name,
                agent.id,
                agent.name,
                updated.original_values,
                updated.new_values,
            ),
            cls.scope(agent.agent_builder_id),
            agent.agent_builder.workspace,
        )
        return agent

    @classmethod
    def scope(cls, agent_builder_id):
        return ApplicationActionScopeType.value(agent_builder_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        AgentService().update_agent(user, params.agent_id, **params.original_values)

    @classmethod
    def redo(cls, user, params, action_to_redo):
        AgentService().update_agent(user, params.agent_id, **params.new_values)


class DeleteAgentActionType(UndoableActionType):
    type = "delete_agent"
    description = ActionTypeDescription(
        _("Delete agent"),
        _('Agent "%(agent_name)s" (%(agent_id)s) deleted'),
        AGENT_BUILDER_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        agent_builder_id: int
        agent_builder_name: str
        agent_id: int
        agent_name: str

    @classmethod
    def do(cls, user, agent_id: int):
        agent = AgentService().delete_agent(user, agent_id)
        cls.register_action(
            user,
            cls.Params(
                agent.agent_builder_id, agent.agent_builder.name, agent.id, agent.name
            ),
            cls.scope(agent.agent_builder_id),
            agent.agent_builder.workspace,
        )

    @classmethod
    def scope(cls, agent_builder_id):
        return ApplicationActionScopeType.value(agent_builder_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        TrashHandler.restore_item(user, AgentTrashableItemType.type, params.agent_id)

    @classmethod
    def redo(cls, user, params, action_to_redo):
        AgentService().delete_agent(user, params.agent_id)


class OrderAgentsActionType(UndoableActionType):
    type = "order_agents"
    description = ActionTypeDescription(
        _("Order agents"),
        _("Agent order changed"),
        AGENT_BUILDER_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        agent_builder_id: int
        agent_builder_name: str
        original_order: list[int]
        new_order: list[int]

    @classmethod
    def do(cls, user, agent_builder_id: int, order: list[int]):
        service = AgentService()
        original_order = list(
            service.list_agents(user, agent_builder_id).values_list("id", flat=True)
        )
        agent_builder = AgentHandler().get_agent_builder(agent_builder_id)
        new_order = service.order_agents(user, agent_builder_id, order)
        cls.register_action(
            user,
            cls.Params(agent_builder_id, agent_builder.name, original_order, new_order),
            cls.scope(agent_builder_id),
            agent_builder.workspace,
        )

    @classmethod
    def scope(cls, agent_builder_id):
        return ApplicationActionScopeType.value(agent_builder_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        AgentService().order_agents(
            user, params.agent_builder_id, params.original_order
        )

    @classmethod
    def redo(cls, user, params, action_to_redo):
        AgentService().order_agents(user, params.agent_builder_id, params.new_order)
