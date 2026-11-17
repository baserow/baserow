from django.db import models
from django.db.models import Q

from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_CHOICES,
    PERIODIC_TIMEZONE_DEFAULT,
)
from baserow.core.models import Application, Workspace

AUTOMATIC_SNAPSHOT_PAUSED_LICENSE = "license"
AUTOMATIC_SNAPSHOT_PAUSED_REASONS = [
    (AUTOMATIC_SNAPSHOT_PAUSED_LICENSE, AUTOMATIC_SNAPSHOT_PAUSED_LICENSE),
]


class AutomaticSnapshotSchedule(models.Model):
    """
    A schedule that creates snapshots of applications automatically. A schedule
    without an application is the workspace default: it covers every application in
    the workspace that doesn't have a schedule of its own, including applications
    created later. A schedule of an application that is disabled opts that
    application out of the workspace default.
    """

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="automatic_snapshot_schedules",
        help_text="The workspace the schedule belongs to.",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="automatic_snapshot_schedules",
        help_text="The application the schedule creates snapshots of. Empty for the "
        "workspace default.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether the schedule creates snapshots. A disabled schedule of an "
        "application opts it out of the workspace default.",
    )
    interval = models.CharField(
        max_length=10,
        choices=PERIODIC_INTERVAL_CHOICES,
        help_text="The interval frequency for creating snapshots.",
    )
    timezone = models.CharField(
        max_length=255,
        default=PERIODIC_TIMEZONE_DEFAULT,
        help_text="The IANA timezone that the hour, minute, day of week and day of "
        "month are expressed in.",
    )
    minute = models.PositiveSmallIntegerField(
        default=0,
        help_text="The minute of the hour when to run (0-59), or the number of "
        "minutes between runs for the minute interval.",
    )
    hour = models.PositiveSmallIntegerField(
        default=0,
        help_text="The hour of the day when to run (0-23).",
    )
    day_of_week = models.PositiveSmallIntegerField(
        default=0,
        help_text="The day of the week when to run (0=Monday, 6=Sunday).",
    )
    day_of_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="The day of the month when to run (1-31).",
    )
    next_run_at = models.DateTimeField(
        null=True,
        db_index=True,
        help_text="The next time the schedule runs.",
    )
    last_run_at = models.DateTimeField(
        null=True,
        help_text="The last time the schedule ran.",
    )
    last_error = models.TextField(
        blank=True,
        default="",
        help_text="The error of the last run, if it failed.",
    )
    paused_reason = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        choices=AUTOMATIC_SNAPSHOT_PAUSED_REASONS,
        help_text="Why the last run was skipped, when it wasn't a failure.",
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["application"],
                condition=Q(application__isnull=False),
                name="unique_automatic_snapshot_schedule_per_application",
            ),
            models.UniqueConstraint(
                fields=["workspace"],
                condition=Q(application__isnull=True),
                name="unique_automatic_snapshot_workspace_default",
            ),
        ]

    @property
    def is_workspace_default(self) -> bool:
        return self.application_id is None
