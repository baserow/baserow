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
        ordering = ("-started_on", "id")


class AutomationWorkflowHistory(AutomationHistory):
    original_workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        on_delete=models.CASCADE,
        related_name="workflow_histories",
        # TODO ZDM: Make non-nullable after next release and add backfill
        # migration. See: https://github.com/baserow/baserow/issues/5236
        null=True,
    )
    workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        on_delete=models.CASCADE,
        related_name="cloned_workflow_histories",
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

    class Meta(AutomationHistory.Meta):
        indexes = [
            models.Index(
                fields=["workflow", "-started_on"],
                name="wa_hist_started_idx",
            ),
            models.Index(
                fields=["workflow", "status", "-started_on"],
                name="wa_hist_status_started_idx",
            ),
        ]


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

    class Meta(AutomationHistory.Meta):
        indexes = [
            models.Index(fields=["workflow_history", "node"]),
        ]


class AutomationNodeResult(models.Model):
    node_history = models.ForeignKey(
        "automation.AutomationNodeHistory",
        on_delete=models.CASCADE,
        related_name="node_results",
    )

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
        unique_together = [["node_history", "iteration_path"]]
