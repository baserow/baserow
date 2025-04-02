from typing import List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.operations import OrderAutomationWorkflowsOperationType
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.operations import (
    CreateWorkflowOperationType,
    DeleteWorkflowOperationType,
    DuplicateWorkflowOperationType,
    ReadWorkflowOperationType,
    UpdateWorkflowOperationType,
)
from baserow.contrib.automation.workflows.signals import (
    workflow_created,
    workflow_deleted,
    workflow_updated,
    workflows_reordered,
)
from baserow.core.handler import CoreHandler
from baserow.core.utils import ChildProgressBuilder, extract_allowed


class AutomationWorkflowService:
    def __init__(self):
        self.handler = AutomationWorkflowHandler()

    def get_workflow(self, user: AbstractUser, workflow_id: int) -> AutomationWorkflow:
        """
        Returns a AutomationWorkflow instance by its ID.

        :param user: The user requesting the workflow.
        :param workflow_id: The ID of the workflow.
        :return: An instance of AutomationWorkflow.
        """

        workflow = self.handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            ReadWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        return workflow

    def create_workflow(
        self,
        user: AbstractUser,
        automation: Automation,
        name: str,
    ) -> AutomationWorkflow:
        """
        Returns a new instance of AutomationWorkflow.

        :param user: The user trying to create the workflow.
        :param automation: The automation the workflow belongs to.
        :param name: The name of the workflow.
        :return: The newly created AutomationWorkflow instance.
        """

        CoreHandler().check_permissions(
            user,
            CreateWorkflowOperationType.type,
            workspace=automation.workspace,
            context=automation,
        )

        workflow = self.handler.create_workflow(automation, name)

        workflow_created.send(self, workflow=workflow, user=user)

        return workflow

    def delete_workflow(self, user: AbstractUser, workflow: AutomationWorkflow) -> None:
        """
        Deletes the specified workflow.

        :param user: The user trying to delete the workflow.
        :param workflow: The AutomationWorkflow instance that must be deleted.
        """

        CoreHandler().check_permissions(
            user,
            DeleteWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        workflow_id = workflow.id

        self.handler.delete_workflow(workflow)

        workflow_deleted.send(
            self, automation=workflow.automation, workflow_id=workflow_id, user=user
        )

    def update_workflow(
        self, user: AbstractUser, workflow: AutomationWorkflow, **kwargs
    ) -> AutomationWorkflow:
        """
        Updates fields of a workflow.

        :param user: The user trying to update the workflow.
        :param workflow: The workflow that should be updated.
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated workflow.
        """

        CoreHandler().check_permissions(
            user,
            UpdateWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        allowed_updates = extract_allowed(
            kwargs,
            ["name"],
        )

        self.handler.update_workflow(workflow, **allowed_updates)

        workflow_updated.send(self, workflow=workflow, user=user)

        return workflow

    def order_workflows(
        self, user: AbstractUser, automation: Automation, order: List[int]
    ) -> List[int]:
        """
        Assigns a new order to the workflows in an Automation application.

        :param user: The user trying to order the workflows.
        :param automation: The automation that the workflows belong to.
        :param order: The new order of the workflows.
        :return: The new order of the workflows.
        """

        CoreHandler().check_permissions(
            user,
            OrderAutomationWorkflowsOperationType.type,
            workspace=automation.workspace,
            context=automation,
        )

        all_workflows = self.handler.get_workflows(
            automation, base_queryset=AutomationWorkflow.objects
        )

        user_workflows = CoreHandler().filter_queryset(
            user,
            OrderAutomationWorkflowsOperationType.type,
            all_workflows,
            workspace=automation.workspace,
        )

        full_order = self.handler.order_workflows(automation, order, user_workflows)

        workflows_reordered.send(
            self, automation=automation, order=full_order, user=user
        )

        return full_order

    def duplicate_workflow(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
        progress: Optional[ChildProgressBuilder] = None,
    ) -> AutomationWorkflow:
        """
        Duplicates an existing AutomationWorkflow instance.

        :param user: The user initiating the workflow duplication.
        :param workflow: The workflow that is being duplicated.
        :param progress: A ChildProgressBuilder instance that can be used to
            report progress.
        :raises ValueError: When the provided workflow is not an instance of
            AutomationWorkflow.
        :return: The duplicated workflow.
        """

        CoreHandler().check_permissions(
            user,
            DuplicateWorkflowOperationType.type,
            workflow.automation.workspace,
            context=workflow,
        )

        workflow_clone = self.handler.duplicate_workflow(workflow, progress)

        workflow_created.send(self, workflow=workflow_clone, user=user)

        return workflow_clone
