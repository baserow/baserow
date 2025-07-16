from django.db import models

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.core.mixins import CreatedAndUpdatedOnMixin


class AutomationHistory(CreatedAndUpdatedOnMixin):
    completed_on = models.DateTimeField(null=True, blank=True)

    message = models.TextField()

    is_test_run = models.BooleanField()

    status = models.CharField(
        choices=HistoryStatusChoices.choices,
        max_length=8,
    )

    class Meta:
        abstract = True


class AutomationWorkflowHistory(AutomationHistory):
    workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        on_delete=models.CASCADE,
        related_name="workflow_history",
    )


class AutomationNodeHistory(AutomationHistory):
    node = models.ForeignKey(
        "automation.AutomationNode",
        on_delete=models.CASCADE,
        related_name="node_history",
    )
