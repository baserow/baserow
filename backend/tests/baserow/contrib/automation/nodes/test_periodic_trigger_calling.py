from datetime import datetime, timezone
from unittest.mock import call, patch

from django.db import transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
)
from baserow.contrib.integrations.core.models import CorePeriodicService


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.automation.workflows.handler.run_workflow")
def test_call_periodic_triggers_that_are_not_published(mock_run_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=False,
        paused=False,
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            AutomationNodeHandler().call_periodic_triggers_that_are_due()

    mock_run_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.automation.workflows.handler.run_workflow")
def test_call_periodic_triggers_that_are_paused(mock_run_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=True,
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            AutomationNodeHandler().call_periodic_triggers_that_are_due()

    mock_run_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@patch("baserow.contrib.automation.workflows.handler.run_workflow")
def test_call_periodic_triggers_that_are_locked(mock_run_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=False,
    )
    trigger_node = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )

    with transaction.atomic(using="default-copy"):
        CorePeriodicService.objects.using("default-copy").filter(
            id=trigger_node.service_id,
        ).select_for_update().get()

        with freeze_time("2025-02-15 10:30:45"):
            with transaction.atomic():
                AutomationNodeHandler().call_periodic_triggers_that_are_due()

        mock_run_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.automation.workflows.handler.run_workflow")
def test_call_multiple_periodic_triggers_that_are_due(mock_run_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=False,
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=False,
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow_2,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            AutomationNodeHandler().call_periodic_triggers_that_are_due()

    mock_run_workflow.delay.assert_has_calls(
        [
            call(workflow.id, False, {"triggered_at": "2025-02-15T10:30:45+00:00"}),
            call(workflow_2.id, False, {"triggered_at": "2025-02-15T10:30:45+00:00"}),
        ]
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.automation.workflows.handler.run_workflow")
@pytest.mark.parametrize(
    "service_kwargs,frozen_time,should_be_called",
    [
        # Minute
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": None,
            },
            "2025-02-15 10:30:45",
            # never triggered before, so it must always be triggered.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 2, 15, 10, 30, 30, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-2-15-10 30:30 = 15 seconds, so should not be
            # triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-2-15-10 30:00 = 45 seconds, so should not be
            # triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 2, 15, 10, 29, 59, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-2-15-10 29:59 = 46 seconds, so should not be
            # triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 2, 15, 10, 28, 59, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-2-15-10 28:59 = 1 minute 46 seconds, so should
            # be triggered.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 1, 16, 2, 59, 59, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # Almost a month ago, so it should be triggered.
            True,
        ),
        # Hour
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": None,
                "minute": 34,
            },
            "2025-02-15 10:30:45",
            # Never triggerd before, but it's not past the 34th minute,
            # so not triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": None,
                "minute": 34,
            },
            "2025-02-15 10:35:45",
            # Never triggerd before, but it's not past the 34th minute,
            # so not triggered.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 15, 10, 5, 45, tzinfo=timezone.utc
                ),
                "minute": 5,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-15 10:05:45 = 25 minutes ago,
            # so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 15, 9, 45, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-15 09:45:30 = 45 minutes ago,
            # so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 15, 9, 27, 45, tzinfo=timezone.utc
                ),
                "minute": 31,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-15 09:27:30 = 1 hour and 3 minutes ago,
            # but not yet past the desired minute, so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 15, 9, 27, 45, tzinfo=timezone.utc
                ),
                "minute": 29,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-15 09:27:30 = 1 hour and 3 minutes ago,
            # and past the desired minute, so it should be triggered.
            True,
        ),
        # Day
        (
            {
                "interval": PERIODIC_INTERVAL_DAY,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
            },
            "2025-02-15 10:30:45",
            # Never triggerd before, but it's not past 11:34,
            # so not triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_DAY,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
            },
            "2025-02-15 10:35:45",
            # Triggered because it was never triggered before, and it's past 11:34.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 14, 10, 40, 45, tzinfo=timezone.utc
                ),
                "minute": 34,
                "hour": 10,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-14 10:40:45 = 23 hours and 10 minutes ago,
            # so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 14, 9, 45, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
                "hour": 11,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-14 09:45:45 = 1 day and 1 hout ago,
            # but not yet at 11:45, so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 14, 9, 45, 45, tzinfo=timezone.utc
                ),
                "minute": 15,
                "hour": 10,
            },
            "2025-02-15 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-14 09:45:45 = 1 day and 1 hour ago,
            # and it's 10:15, so it should not be triggered.
            True,
        ),
        # Week
        (
            {
                "interval": PERIODIC_INTERVAL_WEEK,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
                "day_of_week": 1,  # Tuesday
            },
            "2025-02-10 10:30:45",
            # Never triggerd before, but it's not past Tuesday 11:34,
            # so not triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_WEEK,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
                "day_of_week": 1,  # Tuesday
            },
            "2025-02-11 10:35:45",
            # Triggered because it was never triggered before, and it's past
            # Tuesday 11:34.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 4, 10, 40, 45, tzinfo=timezone.utc
                ),
                "minute": 34,
                "hour": 10,
                "day_of_week": 1,  # Tuesday
            },
            "2025-02-11 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-04 10:40:45 = 1 week, 23 hours and 10
            # minutes ago, so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 4, 9, 45, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
                "hour": 11,
                "day_of_week": 1,  # Tuesday
            },
            "2025-02-11 10:30:45",
            # 2025-02-15 10:30:45 - 2025-02-04 09:45:45 = 1 week and 1 hour ago,
            # but not yet at 11:45, so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_HOUR,
                "last_periodic_run": datetime(
                    2025, 2, 4, 9, 45, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
                "hour": 11,
                "day_of_week": 1,  # Tuesday
            },
            "2025-02-11 11:46:45",
            # 2025-02-15 10:30:45 - 2025-02-04 09:45:45 = 1 week and 1 hour ago,
            # and past 11:46 on Tuesday, so should be triggered.
            True,
        ),
        # Month
        (
            {
                "interval": PERIODIC_INTERVAL_MONTH,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
                "day_of_month": 12,
            },
            "2025-02-10 10:30:45",
            # Never triggerd before, but it's not past 12th 11:34,
            # so not triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MONTH,
                "last_periodic_run": None,
                "minute": 34,
                "hour": 10,
                "day_of_month": 11,
            },
            "2025-02-11 10:35:45",
            # Triggered because it was never triggered before, and it's past 12th 11:34.
            True,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MONTH,
                "last_periodic_run": datetime(
                    2025, 1, 10, 10, 40, 45, tzinfo=timezone.utc
                ),
                "minute": 34,
                "hour": 10,
                "day_of_month": 11,
            },
            "2025-02-11 10:30:45",
            # 2025-02-15 10:30:45 - 2025-01-10 10:40:45 = 1 month, 23 hours and 10
            # minutes ago, so it should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MONTH,
                "last_periodic_run": datetime(
                    2025, 1, 11, 10, 20, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
                "hour": 11,
                "day_of_month": 11,
            },
            "2025-02-11 10:30:45",
            #  Should not be triggered.
            False,
        ),
        (
            {
                "interval": PERIODIC_INTERVAL_MONTH,
                "last_periodic_run": datetime(
                    2025, 1, 11, 11, 44, 45, tzinfo=timezone.utc
                ),
                "minute": 45,
                "hour": 11,
                "day_of_month": 11,
            },
            "2025-02-11 11:46:45",
            # 2025-02-15 10:30:45 - 2025-01-11 11:44:45 = 1 week and 1 hour ago,
            # and past 11:46 on Tuesday, so should be triggered.
            True,
        ),
    ],
)
def test_call_periodic_triggers_that_are_due(
    mock_run_workflow, data_fixture, service_kwargs, frozen_time, should_be_called
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=False,
    )
    trigger_node = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs=service_kwargs,
    )

    with freeze_time(frozen_time):
        with transaction.atomic():
            AutomationNodeHandler().call_periodic_triggers_that_are_due()

    trigger_node.refresh_from_db()
    service = trigger_node.service.specific
    service.refresh_from_db()

    if should_be_called:
        mock_run_workflow.delay.assert_called_once_with(
            workflow.id,
            False,
            {"triggered_at": service.last_periodic_run.isoformat()},
        )
    else:
        mock_run_workflow.delay.assert_not_called()

    if should_be_called:
        target_date = datetime.fromisoformat(frozen_time).replace(tzinfo=timezone.utc)
        assert service.last_periodic_run == target_date
