from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.services.models import Service

User = get_user_model()

PERIODIC_INTERVAL_MINUTE = "MINUTE"
PERIODIC_INTERVAL_HOUR = "HOUR"
PERIODIC_INTERVAL_DAY = "DAY"
PERIODIC_INTERVAL_WEEK = "WEEK"
PERIODIC_INTERVAL_MONTH = "MONTH"

PERIODIC_INTERVAL_CHOICES = [
    (PERIODIC_INTERVAL_MINUTE, PERIODIC_INTERVAL_MINUTE),
    (PERIODIC_INTERVAL_HOUR, PERIODIC_INTERVAL_HOUR),
    (PERIODIC_INTERVAL_DAY, PERIODIC_INTERVAL_DAY),
    (PERIODIC_INTERVAL_WEEK, PERIODIC_INTERVAL_WEEK),
    (PERIODIC_INTERVAL_MONTH, PERIODIC_INTERVAL_MONTH),
]


class PeriodicTriggerService(Service):
    last_periodic_trigger = models.DateTimeField(
        null=True,
        help_text="Timestamp when the trigger was last executed periodically. This "
        "value is used to calculate when it should be triggered.",
    )
    interval = models.CharField(
        max_length=10,
        choices=PERIODIC_INTERVAL_CHOICES,
        null=True,
        default=None,
        help_text="The interval frequency for triggering the workflow.",
    )
    minute = models.PositiveSmallIntegerField(
        default=0,
        help_text="The minute of the hour when to trigger (0-59). Required for hourly,"
        "daily, weekly, monthly intervals.",
    )
    hour = models.PositiveSmallIntegerField(
        default=0,
        help_text="The hour of the day when to trigger (0-23). Required for daily,"
        "weekly, monthly intervals.",
    )
    day_of_week = models.PositiveSmallIntegerField(
        default=0,
        help_text="The day of the week when to trigger (0=Monday, 6=Sunday). Required "
        "for weekly intervals.",
    )
    day_of_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="The day of the month when to trigger (1-31). Required for monthly "
        "intervals.",
    )
