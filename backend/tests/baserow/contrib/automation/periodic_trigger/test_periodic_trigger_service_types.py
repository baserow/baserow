import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.node_types import PeriodicTriggerNodeType
from baserow.contrib.automation.nodes.periodic_trigger.models import (
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PeriodicTriggerService,
)
from baserow.contrib.automation.nodes.periodic_trigger.service_types import (
    PeriodicTriggerServiceType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.services.handler import ServiceHandler


@pytest.mark.django_db
def test_periodic_trigger_service_type_generate_schema(data_fixture):
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
            "minute": 30,
        },
    )

    service_type = PeriodicTriggerServiceType()
    service = trigger_node.service.specific

    assert service_type.type == "periodic"
    assert service_type.model_class == PeriodicTriggerService

    schema = service_type.generate_schema(service)
    assert schema is not None
    assert schema["title"] == "PeriodicTriggerSchema"
    assert schema["type"] == "object"
    assert "triggered_at" in schema["properties"]

    schema_name = service_type.get_schema_name(service)
    assert schema_name == "PeriodicTriggerSchema"


@pytest.mark.django_db
def test_periodic_trigger_node_creation_and_property_updates(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=True,
        paused=False,
    )

    node_handler = AutomationNodeHandler()
    service_handler = ServiceHandler()
    node_type = automation_node_type_registry.get(PeriodicTriggerNodeType.type)
    service_type = PeriodicTriggerServiceType()

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
    assert isinstance(service_specific, PeriodicTriggerService)
    assert service_specific.interval == PERIODIC_INTERVAL_MINUTE
    assert service_specific.minute == 15
    assert service_specific.hour == 10
    assert service_specific.last_periodic_trigger is None

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
