from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

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
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
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
    assert service_specific.next_run_at is None

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
    assert updated_service_specific.next_run_at is None


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
    service_type.on_event = MagicMock()

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

    service_type.on_event.side_effect = check_service_count

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
