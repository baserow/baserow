import json

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
    dispatch_result = service_type.dispatch(service, dispatch_context)
    assert dispatch_result.output_uid == str(edge2.uid)
    assert dispatch_result.data == {"edge": {"label": edge2.label}}


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
    dispatch_result = service_type.dispatch(service, dispatch_context)
    assert dispatch_result.output_uid == ""
    assert dispatch_result.data == {"edge": {"label": service.default_edge_label}}


@pytest.mark.django_db
def test_core_router_service_type_generate_schema(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    data_fixture.create_core_router_action_node(workflow=workflow, service=service)
    assert service.get_type().generate_schema(service) == {
        "title": f"CoreRouter{service.id}Schema",
        "type": "object",
        "properties": {
            "edge": {
                "title": "Branch taken",
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "title": "Label",
                        "description": "The label of the "
                        "branch that matched the condition.",
                    }
                },
            }
        },
    }


@pytest.mark.django_db
def test_core_router_service_type_import_export(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    data_fixture.create_core_router_action_node(workflow=workflow, service=service)
    edge1 = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 1", condition="'false'"
    )
    edge2 = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 2", condition="'true'"
    )

    service_type = service.get_type()
    serialized = json.loads(json.dumps(service_type.export_serialized(service)))

    assert serialized == {
        "id": service.id,
        "integration_id": None,
        "type": "router",
        "sample_data": None,
        "edges": [
            {
                "label": edge1.label,
                "uid": str(edge1.uid),
                "condition": edge1.condition,
            },
            {
                "label": edge2.label,
                "uid": str(edge2.uid),
                "condition": edge2.condition,
            },
        ],
        "default_edge_label": service.default_edge_label,
    }

    new_service = service_type.import_serialized(
        None, serialized, {"automation_edge_outputs": {}}, import_formula=lambda x, d: x
    )

    assert new_service.edges.count() == 2
    new_edge1, new_edge2 = new_service.edges.all()
    assert new_edge1.uid and new_edge1.uid != edge1.uid
    assert new_edge1.uid and new_edge2.uid != edge2.uid
