from django.db import models

from baserow.contrib.automation.history.constants import HistoryStatusChoices


class AutomationHistory(models.Model):
    started_on = models.DateTimeField()
    completed_on = models.DateTimeField(null=True, blank=True)

    message = models.TextField()

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
        related_name="workflow_histories",
    )
    simulate_until_node = models.ForeignKey(
        "automation.AutomationNode",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="simulation_histories",
    )

    is_test_run = models.BooleanField(
        db_default=False,
        help_text="True when the workflow is being simulated.",
    )

    event_payload = models.JSONField(
        db_default=None,
        null=True,
        blank=True,
        help_text="Event payload received by the workflow.",
    )


class AutomationNodeHistory(AutomationHistory):
    workflow_history = models.ForeignKey(
        "automation.AutomationWorkflowHistory",
        on_delete=models.CASCADE,
        related_name="node_histories",
    )
    node = models.ForeignKey(
        "automation.AutomationNode",
        on_delete=models.CASCADE,
        related_name="node_histories",
    )

    class Meta:
        indexes = [
            models.Index(fields=["workflow_history", "node"]),
        ]


class AutomationNodeResult(models.Model):
    node_history = models.ForeignKey(
        "automation.AutomationNodeHistory",
        on_delete=models.CASCADE,
        related_name="node_results",
    )

    iteration = models.PositiveIntegerField(
        db_default=0,
        help_text="Keeps track of the current iteration of the Iterator node.",
    )  # TODO ZDM: Remove after next release

    iteration_path = models.CharField(
        db_default="",
        default="",
        help_text="Keeps track of the iteration path that generated the result.",
    )

    result = models.JSONField(
        db_default={},
        help_text="Contains node results.",
    )

    class Meta:
        unique_together = [["node_history", "iteration"]]
