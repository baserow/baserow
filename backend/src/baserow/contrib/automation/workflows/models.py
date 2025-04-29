import typing

from django.db import models

from baserow.contrib.automation.constants import WORKFLOW_NAME_MAX_LEN
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

if typing.TYPE_CHECKING:
    from baserow.contrib.automation.models import Automation


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

    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)
        unique_together = [["automation", "name"]]

    def get_parent(self):
        return self.automation

    @classmethod
    def get_last_order(cls, automation: "Automation"):
        queryset = AutomationWorkflow.objects.filter(automation=automation)
        return cls.get_highest_order_of_queryset(queryset) + 1


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
