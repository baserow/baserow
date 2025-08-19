from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from dateutil.relativedelta import relativedelta
from loguru import logger

from baserow.contrib.automation.periodic_trigger.models import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
    PeriodicTriggerService,
)
from baserow.contrib.automation.periodic_trigger.utils import (
    get_periodic_trigger_payload,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


class PeriodicTriggerHandler:
    @classmethod
    def call_periodic_triggers_that_are_due(cls):
        """
        This method is typically called by an async task. It uses a single ORM query
        to find all periodic triggers that are due to be executed based on the
        `last_periodic_trigger`.
        """

        now = timezone.now()
        query_conditions = Q()
        is_null = Q(last_periodic_trigger__isnull=True)
        workflow_handler = AutomationWorkflowHandler()

        # MINUTE
        minute_ago = now - timedelta(minutes=1)
        minute_condition = Q(
            is_null | Q(last_periodic_trigger__lt=minute_ago),
            interval=PERIODIC_INTERVAL_MINUTE,
        )
        query_conditions |= minute_condition

        # HOUR
        hour_ago = now - timedelta(hours=1)
        hour_condition = Q(
            is_null | Q(last_periodic_trigger__lt=hour_ago),
            interval=PERIODIC_INTERVAL_HOUR,
            minute__lte=now.minute,
        )
        query_conditions |= hour_condition

        # DAY
        day_ago = now - timedelta(days=1)
        day_condition = Q(
            is_null | Q(last_periodic_trigger__lt=day_ago),
            interval=PERIODIC_INTERVAL_DAY,
            hour__lte=now.hour,
            minute__lte=now.minute,
        )
        query_conditions |= day_condition

        # WEEK
        week_ago = now - timedelta(weeks=1)
        week_condition = Q(
            is_null | Q(last_periodic_trigger__lt=week_ago),
            interval=PERIODIC_INTERVAL_WEEK,
            day_of_week=now.weekday(),
            hour__lte=now.hour,
            minute__lte=now.minute,
        )
        query_conditions |= week_condition

        # MONTH
        month_ago = now - relativedelta(months=1)
        month_condition = Q(
            is_null | Q(last_periodic_trigger__lt=month_ago),
            interval=PERIODIC_INTERVAL_MONTH,
            day_of_month=now.day,
            hour__lte=now.hour,
            minute__lte=now.minute,
        )
        query_conditions |= month_condition

        periodic_services = (
            PeriodicTriggerService.objects.filter(query_conditions)
            .filter(
                Q(
                    automation_workflow_node__workflow__published=True,
                    automation_workflow_node__workflow__paused=False,
                )
            )
            .select_related(
                "automation_workflow_node__workflow__automation__workspace",
                "automation_workflow_node__workflow",
            )
            .select_for_update(
                of=("self",),
                skip_locked=True,
            )
            .order_by("id")
        )

        for service in periodic_services:
            service.last_periodic_trigger = now
            workflow = service.automation_workflow_node.workflow
            # TODO add comment in MR stating that if no `event_payload` is provided,
            # the PreviousNodeProviderType fails with `The previous node id is not
            # present in the dispatch context results`
            workflow_handler.run_workflow(workflow, get_periodic_trigger_payload(now))

        if periodic_services:
            PeriodicTriggerService.objects.bulk_update(
                periodic_services, fields=["last_periodic_trigger"]
            )

        logger.info(f"Scheduled {len(periodic_services)} periodic triggers")
