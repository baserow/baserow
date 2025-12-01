from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.actions import AUTOMATION_ACTION_CONTEXT
from baserow.contrib.automation.handler import AutomationHandler
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.workflows.constants import ALLOW_TEST_RUN_MINUTES
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.automation.workflows.trash_types import (
    AutomationWorkflowTrashableItemType,
)
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder


class CreateAutomationWorkflowActionType(UndoableActionType):
    type = "create_automation_workflow"
    description = ActionTypeDescription(
        _("Create automation workflow"),
        _('Workflow "%(workflow_name)s" (%(workflow_id)s) created'),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        workflow_id: int
        workflow_name: str

    @classmethod
    def do(
        cls, user: AbstractUser, automation_id: int, data: dict
    ) -> AutomationWorkflow:
        workflow = AutomationWorkflowService().create_workflow(
            user, automation_id, **data
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workflow.automation.id,
                workflow.automation.name,
                workflow.id,
                workflow.name,
            ),
            scope=cls.scope(workflow.automation.id),
            workspace=workflow.automation.workspace,
        )
        return workflow

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
        AutomationWorkflowService().delete_workflow(user, params.workflow_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user,
            AutomationWorkflowTrashableItemType.type,
            params.workflow_id,
        )


class UpdateAutomationWorkflowActionType(UndoableActionType):
    type = "update_automation_workflow"
    description = ActionTypeDescription(
        _("Update automation workflow"),
        _('Workflow "%(workflow_name)s" (%(workflow_id)s) updated'),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        workflow_id: int
        workflow_name: str
        workflow_original_params: dict[str, any]
        workflow_new_params: dict[str, any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_id: int,
        new_data: dict,
    ) -> AutomationWorkflow:
        allow_test_run = new_data.pop("allow_test_run", None)
        if allow_test_run is not None:
            if allow_test_run:
                new_data["allow_test_run_until"] = timezone.now() + timedelta(
                    minutes=ALLOW_TEST_RUN_MINUTES
                )
            else:
                new_data["allow_test_run_until"] = None

        updated_workflow = AutomationWorkflowService().update_workflow(
            user, workflow_id, **new_data
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                updated_workflow.workflow.automation.id,
                updated_workflow.workflow.automation.name,
                updated_workflow.workflow.id,
                updated_workflow.workflow.name,
                updated_workflow.original_values,
                updated_workflow.new_values,
            ),
            scope=cls.scope(updated_workflow.workflow.automation.id),
            workspace=updated_workflow.workflow.automation.workspace,
        )

        return updated_workflow.workflow

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
        AutomationWorkflowService().update_workflow(
            user, params.workflow_id, **params.workflow_original_params
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationWorkflowService().update_workflow(
            user, params.workflow_id, **params.workflow_new_params
        )


class DeleteAutomationWorkflowActionType(UndoableActionType):
    type = "delete_automation_workflow"
    description = ActionTypeDescription(
        _("Delete workflow"),
        _('Workflow "%(workflow_name)s" (%(workflow_id)s) deleted'),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        workflow_id: int
        workflow_name: str

    @classmethod
    def do(cls, user: AbstractUser, workflow_id: int) -> None:
        workflow = AutomationWorkflowService().delete_workflow(user, workflow_id)
        cls.register_action(
            user=user,
            params=cls.Params(
                workflow.automation.id,
                workflow.automation.name,
                workflow.id,
                workflow.name,
            ),
            scope=cls.scope(workflow.automation.id),
            workspace=workflow.automation.workspace,
        )

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
        TrashHandler.restore_item(
            user,
            AutomationWorkflowTrashableItemType.type,
            params.workflow_id,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationWorkflowService().delete_workflow(user, params.workflow_id)


class DuplicateAutomationWorkflowActionType(UndoableActionType):
    type = "duplicate_automation_workflow"
    description = ActionTypeDescription(
        _("Duplicate automation workflow"),
        _(
            'Workflow "%(workflow_name)s" (%(workflow_id)s) duplicated from'
            '"%(original_workflow_name)s" (%(original_workflow_id)s) '
        ),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        workflow_id: int
        workflow_name: str
        original_workflow_id: int
        original_workflow_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow: AutomationWorkflow,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> AutomationWorkflow:
        workflow_clone = AutomationWorkflowService().duplicate_workflow(
            user, workflow, progress_builder=progress_builder
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workflow.automation.id,
                workflow.automation.name,
                workflow_clone.id,
                workflow_clone.name,
                workflow.id,
                workflow.name,
            ),
            scope=cls.scope(workflow.automation.id),
            workspace=workflow.automation.workspace,
        )
        return workflow_clone

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
        AutomationWorkflowService().delete_workflow(user, params.workflow_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user,
            AutomationWorkflowTrashableItemType.type,
            params.workflow_id,
        )


class OrderAutomationWorkflowActionType(UndoableActionType):
    type = "order_automation_workflows"
    description = ActionTypeDescription(
        _("Order workflows"),
        _("Workflow order changed"),
        AUTOMATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        automation_id: int
        automation_name: str
        workflows_order: List[int]
        original_workflows_order: List[int]

    @classmethod
    def do(cls, user: AbstractUser, automation_id: int, order: List[int]) -> None:
        automation = AutomationHandler().get_automation(automation_id)

        original_workflows_order = AutomationWorkflowHandler().get_workflows_order(
            automation
        )
        params = cls.Params(
            automation_id,
            automation.name,
            order,
            original_workflows_order,
        )

        AutomationWorkflowService().order_workflows(user, automation, order=order)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(automation_id),
            workspace=automation.workspace,
        )

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
        AutomationWorkflowService().order_workflows(
            user,
            AutomationHandler().get_automation(params.automation_id),
            order=params.original_workflows_order,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        AutomationWorkflowService().order_workflows(
            user,
            AutomationHandler().get_automation(params.automation_id),
            order=params.workflows_order,
        )
