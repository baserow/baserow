import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)


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
        "output_uid": edge2.uid,
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
