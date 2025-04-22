from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.actions import AUTOMATION_ACTION_CONTEXT
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType


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
        updated_node = AutomationNodeService().update_node(
            user, node_id, **new_data
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                updated_node.node.workflow.automation.id,
                updated_node.node.workflow.automation.name,
                updated_node.node.id,
                updated_node.original_values,
                updated_node.new_values,
            ),
            scope=cls.scope(updated_node.node.workflow.automation.id),
            workspace=updated_node.node.workflow.automation.workspace,
        )
        return updated_node.node

    @classmethod
    def scope(cls, automation_id):
        return ApplicationActionScopeType.value(automation_id)

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
