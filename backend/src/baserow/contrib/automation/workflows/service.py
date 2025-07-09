from typing import Dict, List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.handler import AutomationHandler
from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.operations import OrderAutomationWorkflowsOperationType
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.operations import (
    CreateAutomationWorkflowOperationType,
    DeleteAutomationWorkflowOperationType,
    DuplicateAutomationWorkflowOperationType,
    PublishAutomationWorkflowOperationType,
    ReadAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.signals import (
    automation_workflow_created,
    automation_workflow_deleted,
    automation_workflow_published,
    automation_workflow_updated,
    automation_workflows_reordered,
)
from baserow.contrib.automation.workflows.types import UpdatedAutomationWorkflow
from baserow.core.handler import CoreHandler
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Job
from baserow.core.utils import ChildProgressBuilder, Progress


class AutomationWorkflowService:
    def __init__(self):
        self.handler = AutomationWorkflowHandler()

    def run_workflow(
        self,
        workflow_id: int,
        event_payload: Optional[List[Dict]] = None,
        user: Optional[AbstractUser] = None,
    ):
        """
        Runs the workflow with the given ID.

        :param workflow_id: The ID of the workflow to run.
        :param event_payload: The payload from the action.
        """

        self.handler.run_workflow(workflow_id, event_payload)

    def get_workflow(self, user: AbstractUser, workflow_id: int) -> AutomationWorkflow:
        """
        Returns an AutomationWorkflow instance by its ID.

        :param user: The user requesting the workflow.
        :param workflow_id: The ID of the workflow.
        :param published: Whether to return the published version of the workflow.
        :return: An instance of AutomationWorkflow.
        """

        workflow = self.handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            ReadAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        return workflow

    def create_workflow(
        self,
        user: AbstractUser,
        automation_id: int,
        name: str,
        auto_create_trigger: bool = True,
    ) -> AutomationWorkflow:
        """
        Returns a new instance of AutomationWorkflow.

        :param user: The user trying to create the workflow.
        :param automation_id: The automation workflow belongs to.
        :param name: The name of the workflow.
        :param auto_create_trigger: Whether to automatically create a
            trigger for the workflow.
        :return: The newly created AutomationWorkflow instance.
        """

        automation = AutomationHandler().get_automation(automation_id)

        CoreHandler().check_permissions(
            user,
            CreateAutomationWorkflowOperationType.type,
            workspace=automation.workspace,
            context=automation,
        )

        workflow = self.handler.create_workflow(automation, name)

        if auto_create_trigger:
            from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

            first_trigger_type = [
                t
                for t in automation_node_type_registry.get_all()
                if t.is_workflow_trigger
            ][0]
            prepared_values = first_trigger_type.prepare_values({}, user)
            AutomationNodeHandler().create_node(
                first_trigger_type, workflow, **prepared_values
            )

        automation_workflow_created.send(self, workflow=workflow, user=user)

        return workflow

    def delete_workflow(
        self, user: AbstractUser, workflow_id: int
    ) -> AutomationWorkflow:
        """
        Deletes the specified workflow.

        :param user: The user trying to delete the workflow.
        :param workflow_id: The AutomationWorkflow ID that must be deleted.
        """

        workflow = self.handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            DeleteAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        self.handler.delete_workflow(user, workflow)

        automation_workflow_deleted.send(
            self, automation=workflow.automation, workflow_id=workflow.id, user=user
        )

        return workflow

    def update_workflow(
        self, user: AbstractUser, workflow_id: int, **kwargs
    ) -> UpdatedAutomationWorkflow:
        """
        Updates fields of a workflow.

        :param user: The user trying to update the workflow.
        :param workflow_id: The workflow that should be updated.
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated workflow.
        """

        workflow = self.handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            UpdateAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        updated_workflow = self.handler.update_workflow(workflow, **kwargs)
        automation_workflow_updated.send(
            self, user=user, workflow=updated_workflow.workflow
        )

        return updated_workflow

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

        automation_workflows_reordered.send(
            self, automation=automation, order=full_order, user=user
        )

        return full_order

    def duplicate_workflow(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> AutomationWorkflow:
        """
        Duplicates an existing AutomationWorkflow instance.

        :param user: The user initiating the workflow duplication.
        :param workflow: The workflow that is being duplicated.
        :param progress_builder: A ChildProgressBuilder instance that can be
            used to report progress.
        :raises ValueError: When the provided workflow is not an instance of
            AutomationWorkflow.
        :return: The duplicated workflow.
        """

        CoreHandler().check_permissions(
            user,
            DuplicateAutomationWorkflowOperationType.type,
            workflow.automation.workspace,
            context=workflow,
        )

        workflow_clone = self.handler.duplicate_workflow(workflow, progress_builder)

        automation_workflow_created.send(self, workflow=workflow_clone, user=user)

        return workflow_clone

    def async_publish(self, user: AbstractUser, workflow_id: int) -> Job:
        """
        Starts an async job to publish the given automation workflow if the
        user has the right permission.

        :param user: The user publishing the workflow.
        :param workflow_id: The automation workflow the user wants to publish.
        """

        from baserow.contrib.automation.workflows.job_types import (
            PublishAutomationWorkflowJobType,
        )

        workflow = self.handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            PublishAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow.automation,
        )

        job = JobHandler().create_and_start_job(
            user,
            PublishAutomationWorkflowJobType.type,
            automation_workflow=workflow,
        )

        return job

    def publish(
        self, user: AbstractUser, workflow: AutomationWorkflow, progress: Progress
    ) -> None:
        """
        Publish the automation for the given automation workflow if the
        user has the right permission.

        :param user: The user publishing the workflow.
        :param workflow: The workflow the user wants to publish.
        """

        CoreHandler().check_permissions(
            user,
            PublishAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow.automation,
        )

        published_workflow = self.handler.publish(workflow, progress)

        automation_workflow_published.send(self, user=user, workflow=published_workflow)
