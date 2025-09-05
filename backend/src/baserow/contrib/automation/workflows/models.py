from typing import TYPE_CHECKING, Optional

from django.db import models

from baserow.contrib.automation.constants import WORKFLOW_NAME_MAX_LEN
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
    WithRegistry,
)

if TYPE_CHECKING:
    from baserow.contrib.automation.models import Automation
    from baserow.contrib.automation.nodes.models import AutomationTriggerNode


class AutomationWorkflowTrashManager(models.Manager):
    """
    Manager for the AutomationWorkflow model.

    Ensure all trashed relations are excluded from the default queryset.
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(
                models.Q(trashed=True)
                | models.Q(automation__trashed=True)
                | models.Q(automation__workspace__trashed=True)
            )
        )


class AutomationWorkflow(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    WithRegistry,
):
    automation = models.ForeignKey(
        "automation.Automation", on_delete=models.CASCADE, related_name="workflows"
    )

    name = models.CharField(max_length=WORKFLOW_NAME_MAX_LEN)
    state = models.CharField(
        choices=WorkflowState.choices,
        default=WorkflowState.DRAFT,
        db_default=WorkflowState.DRAFT,
        max_length=20,
    )

    order = models.PositiveIntegerField()

    allow_test_run_until = models.DateTimeField(null=True, blank=True)

    objects = AutomationWorkflowTrashManager()
    objects_and_trash = models.Manager()

    class Meta:
        ordering = ("order",)
        unique_together = [["automation", "name"]]

    def get_parent(self):
        return self.automation

    @classmethod
    def get_last_order(cls, automation: "Automation"):
        queryset = AutomationWorkflow.objects.filter(automation=automation)
        return cls.get_highest_order_of_queryset(queryset) + 1

    @classmethod
    def get_last_node_id(
        cls, workflow: "AutomationWorkflow", parent_node_id: Optional[int] = None
    ) -> Optional[int]:
        from baserow.contrib.automation.nodes.models import AutomationNode

        last_node = (
            AutomationNode.objects.filter(
                workflow=workflow, parent_node_id=parent_node_id
            )
            .order_by("order")
            .only("id")
            .last()
        )
        return last_node.id if last_node else None

    def get_trigger(self, specific: bool = True) -> "AutomationTriggerNode":
        node = self.automation_workflow_nodes.get(previous_node_id=None)
        return node.specific if specific else node

    @property
    def is_published(self) -> bool:
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )

        workflow = self
        if published_workflow := AutomationWorkflowHandler().get_published_workflow(
            self
        ):
            workflow = published_workflow

        return workflow.state == WorkflowState.LIVE


class DuplicateAutomationWorkflowJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_automation_workflow = models.ForeignKey(
        AutomationWorkflow,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The automation workflow to duplicate.",
    )

    duplicated_automation_workflow = models.OneToOneField(
        AutomationWorkflow,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated automation workflow.",
    )


class PublishAutomationWorkflowJob(JobWithUserIpAddress, Job):
    automation_workflow = models.ForeignKey(
        AutomationWorkflow,
        null=True,
        on_delete=models.SET_NULL,
    )
