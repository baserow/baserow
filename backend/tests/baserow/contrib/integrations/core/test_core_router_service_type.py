import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_create_core_router_service(data_fixture):
    user = data_fixture.create_user()
    service_type = service_type_registry.get("router")
    values = service_type.prepare_values(
        {"default_edge_label": "Fallback"},
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    assert service.default_edge_label == "Fallback"


@pytest.mark.django_db
def test_update_core_router_service(data_fixture):
    user = data_fixture.create_user()
    service = data_fixture.create_core_router_service(default_edge_label="Fallback")
    service_type = service_type_registry.get("router")
    values = service_type.prepare_values(
        {
            "default_edge_label": "Default",
            "edges": [
                {
                    "label": "Branch name",
                    "condition": "'true'",
                }
            ],
        },
        user,
    )

    result = ServiceHandler().update_service(service_type, service, **values)
    assert result.service.default_edge_label == "Default"
    assert result.service.edges.count() == 1
    edge = result.service.edges.first()
    assert edge.label == "Branch name"
    assert edge.condition == "'true'"


@pytest.mark.django_db
def test_core_router_service_type_dispatch_data_with_a_truthful_edge(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)

    service = data_fixture.create_core_router_service()
    data_fixture.create_core_router_action_node(workflow=workflow, service=service)
    data_fixture.create_core_router_service_edge(
        service=service, label="Edge 1", condition="'false'"
    )
    edge2 = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 2", condition="'true'"
    )

    service_type = service.get_type()
    dispatch_context = AutomationDispatchContext(workflow, None)
    result = service_type.dispatch_data(service, {}, dispatch_context)
    assert result == {
        "output_uid": str(edge2.uid),
        "data": {"label": edge2.label},
    }


@pytest.mark.django_db
def test_core_router_service_type_dispatch_data_using_default_edge(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)

    service = data_fixture.create_core_router_service(default_edge_label="Default")
    data_fixture.create_core_router_action_node(workflow=workflow, service=service)
    data_fixture.create_core_router_service_edge(
        service=service, label="Edge 1", condition="'false'"
    )

    service_type = service.get_type()
    dispatch_context = AutomationDispatchContext(workflow, None)
    result = service_type.dispatch_data(service, {}, dispatch_context)
    assert result == {
        "output_uid": "",
        "data": {"label": service.default_edge_label},
    }
