from django.db import models

from baserow.contrib.automation.history.constants import HistoryStatusChoices


class AutomationHistory(models.Model):
    started_on = models.DateTimeField()
    completed_on = models.DateTimeField(null=True, blank=True)

    message = models.TextField()

    is_test_run = models.BooleanField()

    status = models.CharField(
        choices=HistoryStatusChoices.choices,
        max_length=8,
    )

    class Meta:
        abstract = True
        ordering = ("-started_on",)


class AutomationWorkflowHistory(AutomationHistory):
    workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        on_delete=models.CASCADE,
        related_name="workflow_history",
    )
