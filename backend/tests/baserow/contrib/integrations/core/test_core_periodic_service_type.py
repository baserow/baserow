import json
from datetime import datetime, timezone
from unittest.mock import call, patch
from zoneinfo import ZoneInfo

from django.db import transaction

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
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_WEEK,
)
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType
from baserow.contrib.integrations.core.utils import calculate_next_periodic_run
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry

from .cases.core_periodic_service_type import (
    CALL_PERIODIC_SERVICES_THAT_ARE_DUE_CASES,
)


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
        "properties": {
            "triggered_at": {"type": "string", "title": "Previous scheduled run"},
            "next_run_at": {"type": "string", "title": "Next scheduled run"},
        },
    }


@pytest.mark.django_db
def test_periodic_trigger_node_creation_and_property_updates(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )

    service_type = CorePeriodicServiceType()
    node_type = automation_node_type_registry.get(CorePeriodicTriggerNodeType.type)

    with freeze_time("2025-02-15 10:30:45"):
        service = ServiceHandler().create_service(
            service_type,
            interval=PERIODIC_INTERVAL_MINUTE,
            minute=15,
            hour=10,
        )
        service_type.prepare_values({}, user, service)
        trigger_node = AutomationNodeHandler().create_node(
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
    # Creating the service schedules it, 15 minutes on from 10:30.
    assert service_specific.next_run_at == datetime(
        2025, 2, 15, 10, 45, 0, tzinfo=timezone.utc
    )

    with freeze_time("2025-02-15 11:00:00"):
        updated_service = (
            ServiceHandler()
            .update_service(
                service_type=service_type,
                service=service,
                interval=PERIODIC_INTERVAL_HOUR,
                minute=30,
                hour=14,
                day_of_week=2,  # Wednesday
            )
            .service
        )
        service_type.prepare_values({}, user, updated_service)

    updated_service_specific = updated_service.specific
    assert updated_service_specific.interval == PERIODIC_INTERVAL_HOUR
    assert updated_service_specific.minute == 30
    assert updated_service_specific.hour == 14
    assert updated_service_specific.day_of_week == 2
    # Changing the schedule reschedules it onto the next matching hour, rather
    # than leaving the `next_run_at` the previous schedule calculated.
    assert updated_service_specific.next_run_at == datetime(
        2025, 2, 15, 11, 30, 0, tzinfo=timezone.utc
    )


@pytest.mark.django_db
def test_periodic_service_export_serializes_next_run_at_as_iso(data_fixture):
    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_MINUTE,
        minute=15,
        next_run_at=datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
    )

    serialized = json.loads(
        json.dumps(CorePeriodicServiceType().export_serialized(service))
    )

    assert serialized["next_run_at"] == "2025-02-15T10:30:00+00:00"


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
def test_call_periodic_services_in_draft_workflow(mock_start_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.DRAFT, create_trigger=False
    )
    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_MINUTE,
        last_periodic_run=None,
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service=service,
    )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due()

    mock_start_workflow.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.start_workflow"
)
def test_call_periodic_services_in_paused_workflow(mock_start_workflow, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.PAUSED, create_trigger=False
    )
    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_MINUTE,
        last_periodic_run=None,
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service=service,
    )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due()

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
    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_MINUTE,
        last_periodic_run=None,
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service=service,
    )

    with transaction.atomic(using="default-copy"):
        CorePeriodicService.objects.using("default-copy").filter(
            id=trigger.service_id,
        ).select_for_update().get()

        with freeze_time("2025-02-15 10:30:45"):
            with transaction.atomic():
                service_type_registry.get(
                    CorePeriodicServiceType.type
                ).call_periodic_services_that_are_due()

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
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )

    # Create services with next_run_at set to now so they trigger immediately
    with freeze_time("2025-02-15 10:30:45"):
        service_1 = data_fixture.create_core_periodic_service(
            interval=PERIODIC_INTERVAL_MINUTE,
            last_periodic_run=None,
            next_run_at=datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        )
        data_fixture.create_periodic_trigger_node(
            workflow=workflow_1,
            service=service_1,
        )
        service_2 = data_fixture.create_core_periodic_service(
            interval=PERIODIC_INTERVAL_MINUTE,
            last_periodic_run=None,
            next_run_at=datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        )
        data_fixture.create_periodic_trigger_node(
            workflow=workflow_2,
            service=service_2,
        )

    with freeze_time("2025-02-15 10:30:45"):
        with transaction.atomic():
            service_type_registry.get(
                CorePeriodicServiceType.type
            ).call_periodic_services_that_are_due()

    assert list(mock_async_start_workflow.call_args_list) == unordered(
        [
            call(
                workflow_1,
                {
                    "triggered_at": "2025-02-15T10:30:00+00:00",
                    "next_run_at": "2025-02-15T10:31:00+00:00",
                },
            ),
            call(
                workflow_2,
                {
                    "triggered_at": "2025-02-15T10:30:00+00:00",
                    "next_run_at": "2025-02-15T10:31:00+00:00",
                },
            ),
        ]
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "service_kwargs,frozen_time,should_be_called",
    CALL_PERIODIC_SERVICES_THAT_ARE_DUE_CASES,
)
def test_call_periodic_services_that_are_due(
    data_fixture, service_kwargs, frozen_time, should_be_called
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    # Create the service at the frozen time so next_run_at is calculated correctly
    with freeze_time(frozen_time):
        service = data_fixture.create_core_periodic_service(**service_kwargs)
        trigger = data_fixture.create_periodic_trigger_node(
            workflow=workflow,
            service=service,
        )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    target_date = datetime.fromisoformat(frozen_time).replace(
        tzinfo=timezone.utc, second=0, microsecond=0
    )

    def check_service_count(services, event_payload):
        if should_be_called:
            assert len(services) == 1
            next_run_at = calculate_next_periodic_run(
                services[0].interval,
                services[0].minute,
                services[0].hour,
                services[0].day_of_week,
                services[0].day_of_month,
            )
            service_payload = event_payload(services[0])
            assert service_payload == {
                "triggered_at": target_date.isoformat(),
                "next_run_at": next_run_at.isoformat(),
            }
        else:
            assert len(services) == 0

    # The service type is a registry singleton, so `on_event` is patched rather
    # than assigned, otherwise the mock leaks into every subsequent test.
    with patch.object(service_type, "on_event", side_effect=check_service_count):
        with freeze_time(frozen_time):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()

    trigger.refresh_from_db()
    service = trigger.service.specific
    service.refresh_from_db()

    if should_be_called:
        assert service.last_periodic_run == target_date
        # Verify next_run_at was updated to the next scheduled time
        assert service.next_run_at is not None
        assert service.next_run_at > target_date


@pytest.mark.django_db(transaction=True)
def test_publishing_a_workflow_does_not_trigger_an_unscheduled_run(data_fixture):
    """
    Publishing imports a fresh copy of the service. The copy must be scheduled from
    the schedule itself, otherwise it inherits the draft's `next_run_at` (always
    null, as drafts are never dispatched), is immediately considered due, and runs
    once at publish time regardless of the configured schedule.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.DRAFT, create_trigger=False
    )
    data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_WEEK,
            "day_of_week": 0,  # Monday
            "hour": 5,
            "minute": 0,
        },
    )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    # Publish on a Wednesday, nowhere near the Monday 05:00 schedule.
    with freeze_time("2025-02-12 14:23:00"):
        with transaction.atomic():
            published_workflow = AutomationWorkflowHandler().publish(workflow)

    published_service = published_workflow.get_trigger().service.specific
    assert published_service.next_run_at == datetime(
        2025, 2, 17, 5, 0, 0, tzinfo=timezone.utc
    )

    # The tick straight after publishing must not dispatch it.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2025-02-12 14:24:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 0

    # It fires on the Monday it was configured for.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2025-02-17 05:00:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_unconfigured_periodic_service_is_never_due(data_fixture):
    """
    A periodic trigger which hasn't been given an interval yet has no schedule, so
    it must not be dispatched. Previously it was considered due via its null
    `next_run_at`, and `calculate_next_periodic_run` fell through to its unknown
    interval branch, causing it to run every hour.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow, service_kwargs={"interval": None}
    )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2025-02-12 14:24:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 0

    trigger.service.specific.refresh_from_db()
    assert trigger.service.specific.next_run_at is None


@pytest.mark.django_db
def test_periodic_service_schedules_in_its_own_timezone(data_fixture):
    """
    The schedule fields are a wall clock time in the service's timezone. The same
    "Monday at 09:00 in Amsterdam" is a different instant either side of a DST
    transition, so the `next_run_at` it resolves to has to differ with it.
    """

    service_type = CorePeriodicServiceType()
    schedule = {
        "interval": PERIODIC_INTERVAL_WEEK,
        "timezone": "Europe/Amsterdam",
        "day_of_week": 0,  # Monday
        "hour": 9,
        "minute": 0,
    }

    # Saved in December, when Amsterdam is on CET (UTC+1).
    with freeze_time("2025-12-15 11:00:00"):
        winter = ServiceHandler().create_service(service_type, **schedule)
    assert winter.specific.next_run_at == datetime(
        2025, 12, 22, 8, 0, tzinfo=timezone.utc
    )

    # Saved in July, when Amsterdam is on CEST (UTC+2).
    with freeze_time("2026-07-01 11:00:00"):
        summer = ServiceHandler().create_service(service_type, **schedule)
    assert summer.specific.next_run_at == datetime(
        2026, 7, 6, 7, 0, tzinfo=timezone.utc
    )

    # Both are 09:00 in Amsterdam, which is the point.
    for service in [winter, summer]:
        local = service.specific.next_run_at.astimezone(ZoneInfo("Europe/Amsterdam"))
        assert (local.weekday(), local.hour, local.minute) == (0, 9, 0)


@pytest.mark.django_db(transaction=True)
def test_periodic_service_keeps_local_time_when_advancing_across_dst(data_fixture):
    """
    A live schedule crosses a DST transition by being advanced in the dispatch
    loop, not by being re-saved. Advancing has to re-resolve the offset each time,
    otherwise the run drifts by an hour once the clocks change.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_WEEK,
            "timezone": "Europe/Amsterdam",
            "day_of_week": 0,  # Monday
            "hour": 9,
            "minute": 0,
            # 09:00 in Amsterdam while the clocks are on CET.
            "next_run_at": datetime(2025, 12, 22, 8, 0, tzinfo=timezone.utc),
        },
    )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    # Dispatch at the July occurrence, which is 09:00 in Amsterdam on CEST.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2026-07-06 07:00:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 1

    service = trigger.service.specific
    service.refresh_from_db()

    # The next run is the following Monday, still 09:00 in Amsterdam. It's 07:00
    # UTC rather than the 08:00 it was scheduled at in December.
    assert service.next_run_at == datetime(2026, 7, 13, 7, 0, tzinfo=timezone.utc)
    local = service.next_run_at.astimezone(ZoneInfo("Europe/Amsterdam"))
    assert (local.weekday(), local.hour, local.minute) == (0, 9, 0)


@pytest.mark.django_db
def test_periodic_service_defaults_to_utc(data_fixture):
    """
    A service which doesn't choose a timezone is scheduled in UTC, which is what
    services created before the schedule became timezone aware relied on.
    """

    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_WEEK, day_of_week=0, hour=9, minute=0
    )
    assert service.timezone == "UTC"


@pytest.mark.django_db
def test_periodic_service_prepare_values_validates_timezone(data_fixture):
    user = data_fixture.create_user()
    service_type = CorePeriodicServiceType()

    prepared = service_type.prepare_values(
        {"interval": PERIODIC_INTERVAL_WEEK, "timezone": "Europe/Amsterdam"}, user
    )
    assert prepared["timezone"] == "Europe/Amsterdam"

    with pytest.raises(AutomationNodeMisconfiguredService) as e:
        service_type.prepare_values(
            {"interval": PERIODIC_INTERVAL_WEEK, "timezone": "Middle/Earth"}, user
        )
    assert str(e.value) == "The timezone `Middle/Earth` is not a valid timezone."


@pytest.mark.django_db(transaction=True)
def test_late_periodic_service_catches_up_once_and_resumes(data_fixture):
    """
    If the workers are down over one or more scheduled runs, the service is late
    rather than skipped. When they come back it runs once to catch up, and is then
    put back onto its normal schedule instead of firing once per missed run.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_WEEK,
            "day_of_week": 0,  # Monday
            "hour": 5,
            "minute": 0,
            # Due three Mondays ago: the workers never picked it up.
            "next_run_at": datetime(2025, 1, 27, 5, 0, tzinfo=timezone.utc),
        },
    )

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    # The workers come back on a Wednesday, long after three runs were missed.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2025-02-19 09:13:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        # It catches up once, not once per missed run.
        assert mock_start.call_count == 1

    service = trigger.service.specific
    service.refresh_from_db()

    # It's back on schedule: the next run is the coming Monday, not another
    # missed one in the past.
    assert service.last_periodic_run == datetime(
        2025, 2, 19, 9, 13, tzinfo=timezone.utc
    )
    assert service.next_run_at == datetime(2025, 2, 24, 5, 0, tzinfo=timezone.utc)

    # The next tick must not fire it again now that it's caught up.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2025-02-19 09:14:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 0


@pytest.mark.django_db(transaction=True)
def test_existing_utc_periodic_service_is_unaffected_across_dst(data_fixture):
    """
    Schedules which predate the timezone field default to UTC, and must keep firing
    at exactly the instants they did before. That means they still drift against a
    local clock across a DST transition, which is the pre-existing behaviour: this
    change mustn't silently move a live schedule, only let it be corrected.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_WEEK,
            "day_of_week": 0,  # Monday
            "hour": 5,
            "minute": 0,
            # Set while the clocks were on CET, as an existing service would be.
            "next_run_at": datetime(2026, 3, 23, 5, 0, tzinfo=timezone.utc),
        },
    )
    service = trigger.service.specific
    assert service.timezone == "UTC"

    service_type = service_type_registry.get(CorePeriodicServiceType.type)

    # Advance it over the 29 March transition, when Amsterdam goes CET -> CEST.
    with patch.object(AutomationWorkflowHandler, "async_start_workflow") as mock_start:
        with freeze_time("2026-03-30 05:00:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()
        assert mock_start.call_count == 1

    service.refresh_from_db()

    # Still 05:00 UTC on the Monday, exactly as before this change.
    assert service.next_run_at == datetime(2026, 4, 6, 5, 0, tzinfo=timezone.utc)
    # And still drifting against a local clock, which is the point: UTC schedules
    # are left alone rather than quietly reinterpreted as somebody's local time.
    local = service.next_run_at.astimezone(ZoneInfo("Europe/Amsterdam"))
    assert (local.weekday(), local.hour) == (0, 7)


@pytest.mark.django_db
def test_periodic_payload_timestamps_are_in_the_service_timezone(data_fixture):
    """
    The payload timestamps describe the same instants either way, but they're
    formatted in the service's timezone so that a user who scheduled "23:30
    Europe/London" sees 23:30 rather than the UTC equivalent.
    """

    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_DAY,
        timezone="Europe/London",
        hour=23,
        minute=30,
    )
    service_type = CorePeriodicServiceType()

    # 29 July is BST (UTC+1): 23:30 London is 22:30 UTC.
    with freeze_time("2026-07-29 15:44:00"):
        payload = service_type._get_simulation_payload(service)

    assert payload["next_run_at"] == "2026-07-29T23:30:00+01:00"
    assert payload["triggered_at"] == "2026-07-29T16:44:00+01:00"

    # The dispatch payload is formatted the same way.
    service.last_periodic_run = datetime(2026, 7, 28, 22, 30, tzinfo=timezone.utc)
    service.next_run_at = datetime(2026, 7, 29, 22, 30, tzinfo=timezone.utc)
    dispatch_payload = service_type._get_dispatch_payload(service)
    assert dispatch_payload["triggered_at"] == "2026-07-28T23:30:00+01:00"
    assert dispatch_payload["next_run_at"] == "2026-07-29T23:30:00+01:00"
