from django.conf import settings
from django.db import models
from django.db.models import Q

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.core.subjects import UserSubjectType


class AutomationHistory(models.Model):
    started_on = models.DateTimeField()
    completed_on = models.DateTimeField(null=True, blank=True)

    message = models.TextField()

    status = models.CharField(
        choices=HistoryStatusChoices.choices,
        max_length=16,
    )

    class Meta:
        abstract = True
        ordering = ("-started_on", "id")


class AutomationWorkflowHistory(AutomationHistory):
    original_workflow = models.ForeignKey(
        "automation.AutomationWorkflow",
        on_delete=models.CASCADE,
        related_name="workflow_histories",
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

    # IDs overlap across subject types; the name survives the subject's deletion.
    triggered_by_id = models.PositiveIntegerField(
        null=True,
        help_text="The id of the subject who started this run. Null when an "
        "event started it.",
    )
    triggered_by_type = models.CharField(
        max_length=255,
        db_default=UserSubjectType.type,
        help_text="The subject type of who started this run.",
    )
    triggered_by_name = models.CharField(
        max_length=160,
        blank=True,
        db_default="",
        help_text="The name of who started this run, when it started.",
    )
    cancellation_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_default=None,
        help_text="The user who requested the cancellation of this run.",
    )
    cancellation_requested_on = models.DateTimeField(
        null=True,
        blank=True,
        db_default=None,
        help_text="When the cancellation of this run was requested.",
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


class AutomationWorkflowHistoryResponse(models.Model):
    workflow_history = models.OneToOneField(
        "automation.AutomationWorkflowHistory",
        on_delete=models.CASCADE,
        related_name="response",
    )
    status_code = models.PositiveSmallIntegerField()
    headers = models.JSONField(db_default={}, default=dict)
    body = models.JSONField(db_default=None, default=None, null=True, blank=True)
    body_type = models.CharField(max_length=10)
    source_node = models.ForeignKey(
        "automation.AutomationNode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_history_responses",
    )
    is_default = models.BooleanField(
        db_default=False,
        default=False,
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
    attempt = models.PositiveSmallIntegerField(
        default=1,
        db_default=1,
        help_text="Which attempt of the node this entry records, starting at 1.",
    )
    iteration_path = models.CharField(
        default="",
        db_default="",
        blank=True,
        help_text="The iteration path the node was dispatched in, set when the entry "
        "is created so a node without a result yet (waiting, cancelled while "
        "waiting) can still be placed under its iteration.",
    )
    resume_at = models.DateTimeField(
        null=True,
        blank=True,
        db_default=None,
        help_text="When a waiting node is due to resume.",
    )
    resume_state = models.JSONField(
        null=True,
        blank=True,
        db_default=None,
        help_text="What the runner needs to resume a waiting node: the state its "
        "service stored and the iterator positions of the dispatch. Cleared once "
        "the node resumed.",
    )

    class Meta(AutomationHistory.Meta):
        indexes = [
            models.Index(fields=["workflow_history", "node"]),
            # The recovery sweep looks for waiting nodes whose resume is overdue.
            models.Index(
                fields=["resume_at"],
                condition=Q(status=HistoryStatusChoices.WAITING),
                name="wa_node_hist_waiting_idx",
            ),
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
