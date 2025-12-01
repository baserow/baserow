from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

from django.db import transaction
from django.utils.timezone import now

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.node_types import CorePeriodicTriggerNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
)
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_periodic_trigger_service_type_generate_schema(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger_node = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "minute": 30,
        },
    )
    service = trigger_node.service
    assert CorePeriodicServiceType().generate_schema(service) == {
        "title": f"Periodic{service.id}Schema",
        "type": "object",
        "properties": {"triggered_at": {"type": "string", "title": "Triggered at"}},
    }


@pytest.mark.django_db
def test_periodic_trigger_node_creation_and_property_updates(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )

    node_handler = AutomationNodeHandler()
    service_handler = ServiceHandler()
    node_type = automation_node_type_registry.get(CorePeriodicTriggerNodeType.type)
    service_type = CorePeriodicServiceType()

    service = service_handler.create_service(
        service_type,
        interval=PERIODIC_INTERVAL_MINUTE,
        minute=15,
        hour=10,
    )
    trigger_node = node_handler.create_node(
        node_type=node_type,
        workflow=workflow,
        service=service,
    )

    assert trigger_node.workflow == workflow
    assert trigger_node.service == service
    service_specific = service.specific
    assert isinstance(service_specific, CorePeriodicService)
    assert service_specific.interval == PERIODIC_INTERVAL_MINUTE
    assert service_specific.minute == 15
    assert service_specific.hour == 10
    assert service_specific.last_periodic_run is None

    updated_service = service_handler.update_service(
        service_type=service_type,
        service=service,
        interval=PERIODIC_INTERVAL_HOUR,
        minute=30,
        hour=14,
        day_of_week=2,  # Wednesday
    ).service

    updated_service_specific = updated_service.specific
    assert updated_service_specific.interval == PERIODIC_INTERVAL_HOUR
    assert updated_service_specific.minute == 30
    assert updated_service_specific.hour == 14
    assert updated_service_specific.day_of_week == 2


@pytest.mark.django_db
@patch(
    "baserow.contrib.integrations.core.service_types.settings.INTEGRATIONS_PERIODIC_MINUTE_MIN",
    5,
)
def test_periodic_service_prepare_values_validates_minute_minimum(data_fixture):
    user = data_fixture.create_user()
    values = {
        "interval": PERIODIC_INTERVAL_MINUTE,
        "minute": 5,
    }
    prepared = CorePeriodicServiceType().prepare_values(values, user)
    assert prepared["interval"] == PERIODIC_INTERVAL_MINUTE
    assert prepared["minute"] == 5

    values = {
        "interval": PERIODIC_INTERVAL_MINUTE,
        "minute": 10,
    }
    prepared = CorePeriodicServiceType().prepare_values(values, user)
    assert prepared["interval"] == PERIODIC_INTERVAL_MINUTE
    assert prepared["minute"] == 10

    values = {
        "interval": PERIODIC_INTERVAL_MINUTE,
        "minute": 3,
    }
    with pytest.raises(AutomationNodeMisconfiguredService) as e:
        CorePeriodicServiceType().prepare_values(values, user)
    assert str(e.value) == "The `minute` value must be greater or equal to 5."


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.start_workflow"
)
def test_call_periodic_services_that_are_not_published(
    mock_start_workflow, data_fixture
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.DRAFT, create_trigger=False
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
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due(now())

    mock_start_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.start_workflow"
)
def test_call_periodic_services_that_are_paused(mock_start_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.PAUSED, create_trigger=False
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
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due(now())

    mock_start_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.start_workflow"
)
def test_call_periodic_services_that_are_locked(mock_start_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )

    with transaction.atomic(using="default-copy"):
        CorePeriodicService.objects.using("default-copy").filter(
            id=trigger.service_id,
        ).select_for_update().get()

        with freeze_time("2025-02-15 10:30:45"):
            with transaction.atomic():
                service_type_registry.get(
                    CorePeriodicServiceType.type
                ).call_periodic_services_that_are_due(now())

        mock_start_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.async_start_workflow"
)
def test_call_multiple_periodic_services_that_are_due(
    mock_async_start_workflow, data_fixture
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow_1,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
        },
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
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
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due(now())

    assert list(mock_async_start_workflow.call_args_list) == unordered(
        [
            call(
                workflow_1,
                {"triggered_at": "2025-02-15T10:30:00+00:00"},
            ),
            call(
                workflow_2,
                {"triggered_at": "2025-02-15T10:30:00+00:00"},
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
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
                # Compat: no `minute` is provided, so it defaults to "1" (every minute).
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
                # Compat: no `minute` is provided, so it defaults to "1" (every minute).
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
                # Compat: no `minute` is provided, so it defaults to "1" (every minute).
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
                # Compat: no `minute` is provided, so it defaults to "1" (every minute).
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 1, 16, 2, 59, 59, tzinfo=timezone.utc
                ),
            },
            "2025-02-15 10:30:45",
            # Almost a month ago, so it should be triggered.
            True,
        ),
        (
            {
                "minute": 5,
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 11, 6, 12, 0, 0, tzinfo=timezone.utc
                ),
            },
            "2025-11-06 12:03:00",
            # It's been 3 minutes, so it should not be triggered.
            False,
        ),
        (
            {
                "minute": 5,
                "interval": PERIODIC_INTERVAL_MINUTE,
                "last_periodic_run": datetime(
                    2025, 11, 6, 12, 0, 0, tzinfo=timezone.utc
                ),
            },
            "2025-11-06 12:05:00",
            # It's been 5 minutes, so it should be triggered.
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
def test_call_periodic_services_that_are_due(
    data_fixture, service_kwargs, frozen_time, should_be_called
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs=service_kwargs,
    )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)
    service_type.on_event = MagicMock()

    target_date = datetime.fromisoformat(frozen_time).replace(
        tzinfo=timezone.utc, second=0, microsecond=0
    )

    def check_service_count(services, event_payload):
        if should_be_called:
            assert services.count() == 1
            assert event_payload == {"triggered_at": target_date.isoformat()}
        else:
            assert services.count() == 0

    service_type.on_event.side_effect = check_service_count

    with freeze_time(frozen_time):
        with transaction.atomic():
            service_type.call_periodic_services_that_are_due(now())

    trigger.refresh_from_db()
    service = trigger.service.specific
    service.refresh_from_db()

    if should_be_called:
        assert service.last_periodic_run == target_date
