from dataclasses import dataclass
from typing import List

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.action.scopes import (
    NodeActionScopeType,
    WorkflowActionScopeType,
)
from baserow.contrib.automation.actions import AUTOMATION_ACTION_CONTEXT
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.trash.handler import TrashHandler


class CreateAutomationNodeActionType(UndoableActionType):
    type = "create_automation_node"
    description = ActionTypeDescription(
        _("Create automation node"),
        _('Node "%(node_id)s" created'),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        node_id: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        data: dict,
    ) -> AutomationNode:
        node = AutomationNodeService().create_node(user, node_type, workflow, **data)

        cls.register_action(
            user=user,
            params=cls.Params(
                node.workflow.automation.id,
                node.workflow.automation.name,
                node.id,
            ),
            scope=cls.scope(node.id),
            workspace=node.workflow.automation.workspace,
        )
        return node

    @classmethod
    def scope(cls, node_id):
        return NodeActionScopeType.value(node_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        AutomationNodeService().delete_node(user, params.node_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user,
            AutomationNodeTrashableItemType.type,
            params.node_id,
        )


class UpdateAutomationNodeActionType(UndoableActionType):
    type = "update_automation_node"
    description = ActionTypeDescription(
        _("Update automation node"),
        _('Node "%(node_id)s" updated'),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        node_id: int
        node_original_params: dict[str, any]
        node_new_params: dict[str, any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        node_id: int,
        new_data: dict,
    ) -> AutomationNode:
        updated_node = AutomationNodeService().update_node(user, node_id, **new_data)

        cls.register_action(
            user=user,
            params=cls.Params(
                updated_node.node.workflow.automation.id,
                updated_node.node.workflow.automation.name,
                updated_node.node.id,
                updated_node.original_values,
                updated_node.new_values,
            ),
            scope=cls.scope(node_id),
            workspace=updated_node.node.workflow.automation.workspace,
        )
        return updated_node.node

    @classmethod
    def scope(cls, node_id):
        return NodeActionScopeType.value(node_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        AutomationNodeService().update_node(
            user, params.node_id, **params.node_original_params
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationNodeService().update_node(
            user, params.node_id, **params.node_new_params
        )


class DeleteAutomationNodeActionType(UndoableActionType):
    type = "delete_automation_node"
    description = ActionTypeDescription(
        _("Delete automation node"),
        _("Node (%(node_id)s) deleted"),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        node_id: int

    @classmethod
    def do(cls, user: AbstractUser, node_id: int) -> None:
        node = AutomationNodeService().delete_node(user, node_id)
        automation = node.workflow.automation
        cls.register_action(
            user=user,
            params=cls.Params(
                automation.id,
                automation.name,
                node_id,
            ),
            scope=cls.scope(node_id),
            workspace=automation.workspace,
        )

    @classmethod
    def scope(cls, node_id):
        return NodeActionScopeType.value(node_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        TrashHandler.restore_item(
            user,
            AutomationNodeTrashableItemType.type,
            params.node_id,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationNodeService().delete_node(user, params.node_id)


class OrderAutomationNodesActionType(UndoableActionType):
    type = "order_automation_nodes"
    description = ActionTypeDescription(
        _("Order nodes"),
        _("Node order changed"),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        workflow_id: int
        nodes_order: List[int]
        original_nodes_order: List[int]

    @classmethod
    def do(cls, user: AbstractUser, workflow_id: int, order: List[int]) -> None:
        workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

        original_nodes_order = AutomationNodeHandler().get_nodes_order(workflow)
        params = cls.Params(
            workflow_id,
            order,
            original_nodes_order,
        )

        AutomationNodeService().order_nodes(user, workflow, order=order)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(workflow_id),
            workspace=workflow.automation.workspace,
        )

    @classmethod
    def scope(cls, workflow_id):
        return WorkflowActionScopeType.value(workflow_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        AutomationNodeService().order_nodes(
            user,
            AutomationWorkflowHandler().get_workflow(params.workflow_id),
            order=params.original_nodes_order,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationNodeService().order_nodes(
            user,
            AutomationWorkflowHandler().get_workflow(params.workflow_id),
            order=params.nodes_order,
        )


class DuplicateAutomationNodeActionType(UndoableActionType):
    type = "duplicate_automation_node"
    description = ActionTypeDescription(
        _("Duplicate automation node"),
        _("Node duplicated"),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        workflow_id: int
        node_id: int
        original_node_id: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        node_id: int,
    ) -> AutomationNode:
        node = AutomationNodeService().get_node(user, node_id)

        node_clone = AutomationNodeService().duplicate_node(user, node)
        cls.register_action(
            user=user,
            params=cls.Params(
                node_clone.workflow.id,
                node_clone.id,
                node_id,
            ),
            scope=cls.scope(node_clone.id),
            workspace=node.workflow.automation.workspace,
        )
        return node_clone

    @classmethod
    def scope(cls, node_id):
        return NodeActionScopeType.value(node_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        AutomationNodeService().delete_node(user, params.node_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user,
            AutomationNodeTrashableItemType.type,
            params.node_id,
        )
