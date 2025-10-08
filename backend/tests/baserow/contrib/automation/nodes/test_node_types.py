import json
import uuid
from unittest.mock import MagicMock, patch

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_204_NO_CONTENT

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.handler import CoreHandler
from baserow.core.services.types import DispatchResult
from baserow.core.utils import MirrorDict


def test_automation_node_type_is_replaceable_with():
    trigger_node_type = automation_node_type_registry.get("rows_created")
    update_trigger_node_type = automation_node_type_registry.get("rows_updated")
    action_node_type = automation_node_type_registry.get("create_row")
    update_action_node_type = automation_node_type_registry.get("update_row")

    assert trigger_node_type.is_replaceable_with(update_trigger_node_type)
    assert not trigger_node_type.is_replaceable_with(update_action_node_type)
    assert action_node_type.is_replaceable_with(update_action_node_type)
    assert not action_node_type.is_replaceable_with(update_trigger_node_type)


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_automation_service_node_trigger_type_on_event(
    mock_async_start_workflow, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    original_workflow = data_fixture.create_automation_workflow(
        user, trigger_service_kwargs={"table": table}
    )
    workflow = data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE, trigger_service_kwargs={"table": table}
    )
    workflow.automation.published_from = original_workflow
    workflow.automation.save()
    trigger = workflow.get_trigger()

    service = trigger.service.specific
    service_queryset = service.get_type().model_class.objects.filter(table=table)
    event_payload = [
        {
            "id": 1,
            "order": "1.00000000000000000000",
            f"field_1": "Community Engagement",
        },
        {
            "id": 2,
            "order": "2.00000000000000000000",
            f"field_1": "Construction",
        },
    ]

    trigger.get_type().on_event(service_queryset, event_payload, user=user)
    mock_async_start_workflow.assert_called_once()


@pytest.mark.django_db
def test_automation_node_type_create_row_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_create_row_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_create_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_rows_created_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="rows_created")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_service_node_type_rows_created_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="rows_created")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@pytest.mark.django_db
def test_automation_node_type_update_row_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_update_row_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_update_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]

    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_delete_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_migrates_its_previous_node_output_on_import(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    data_fixture.create_core_router_action_node(workflow=workflow, service=service)
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )
    output_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, previous_node_output=str(edge.uid)
    )
    output_node_type = output_node.get_type()

    serialized = json.loads(json.dumps(output_node_type.export_serialized(output_node)))
    assert serialized["previous_node_output"] == str(edge.uid)

    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
        "automation_edge_outputs": {str(edge.uid): str(uuid.uuid4())},
    }
    new_output_node = output_node_type.import_serialized(
        workflow, serialized, id_mapping, import_formula=lambda x, d: x
    )
    assert (
        new_output_node.previous_node_output
        == id_mapping["automation_edge_outputs"][str(edge.uid)]
    )


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_on_event_excludes_disabled_workflows(mock_async_start_workflow, data_fixture):
    """
    Ensure that the AutomationNodeTriggerType::on_event() excludes any disabled
    workflows.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_rows_created_service(
        table=table,
    )

    # Create a Node + workflow that is disabled
    original_workflow = data_fixture.create_automation_workflow()
    workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.DISABLED,
    )
    workflow.automation.published_from = original_workflow
    workflow.automation.save()

    node = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, service=service
    )

    service_queryset = service.get_type().model_class.objects.filter(table=table)
    event_payload = [
        {
            "id": 1,
            "order": "1.00000000000000000000",
            f"field_1": "Community Engagement",
        },
        {
            "id": 2,
            "order": "2.00000000000000000000",
            f"field_1": "Construction",
        },
    ]

    node.get_type().on_event(service_queryset, event_payload, user=user)
    mock_async_start_workflow.assert_not_called()


@pytest.mark.django_db
def test_duplicating_router_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    core_router_with_edges = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    router = core_router_with_edges.router
    edge1_output = core_router_with_edges.edge1_output
    edge2_output = core_router_with_edges.edge2_output
    fallback_output_node = core_router_with_edges.fallback_output_node

    router_type = router.get_type()
    source_router_outputs = router_type.get_output_nodes(router, specific=True)
    assert len(source_router_outputs) == 3
    assert edge1_output in source_router_outputs
    assert edge2_output in source_router_outputs
    assert fallback_output_node in source_router_outputs

    duplication = AutomationNodeHandler().duplicate_node(router)
    duplicated_router = duplication.duplicated_node

    assert duplicated_router.previous_node_id == router.id
    assert duplicated_router.previous_node_output == ""

    source_router_outputs = router_type.get_output_nodes(router, specific=True)
    assert len(source_router_outputs) == 3
    assert edge1_output in source_router_outputs
    assert edge2_output in source_router_outputs
    assert duplicated_router in source_router_outputs

    fallback_output_node.refresh_from_db()
    assert fallback_output_node not in source_router_outputs
    assert fallback_output_node.previous_node_id == duplicated_router.id


@pytest.mark.django_db
def test_trigger_node_dispatch_returns_event_payload_if_not_simulated(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_rows_created_service(
        table=table,
    )
    workflow = data_fixture.create_automation_workflow(state=WorkflowState.LIVE)
    node = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, service=service
    )
    dispatch_context = AutomationDispatchContext(workflow, "foo")

    result = node.get_type().dispatch(node, dispatch_context)

    assert result == DispatchResult(data="foo", status=200, output_uid="")


@pytest.mark.django_db
def test_trigger_node_dispatch_returns_sample_data_if_simulated(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workflow = data_fixture.create_automation_workflow(state=WorkflowState.LIVE)
    node = workflow.get_trigger().specific
    service = node.service.specific
    service.table = table
    service.sample_data = {"data": {"foo": "bar"}}
    service.save()

    dispatch_context = AutomationDispatchContext(workflow, simulate_until_node=node)
    # If we don't reset this value, the trigger is considered as updatable and will
    # be dispatched.
    dispatch_context.update_sample_data_for = []

    result = node.get_type().dispatch(node, dispatch_context)

    assert result == DispatchResult(data={"foo": "bar"}, status=200, output_uid="")


@pytest.mark.django_db(transaction=True)
def test_core_http_trigger_node(api_client, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=user, automation=automation, state=WorkflowState.LIVE, create_trigger=False
    )
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=automation
    )

    trigger_node = data_fixture.create_http_trigger_node(
        workflow=workflow,
        service_kwargs={"is_public": True},
    )

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", "text")],
        rows=[],
    )
    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    action_service.field_mappings.create(
        field=fields[0],
        value=f"concat('foo: ', get('previous_node.{trigger_node.id}.body.foo'))",
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=action_service,
    )

    url = reverse("api:http_trigger", kwargs={"webhook_uid": trigger_node.service.uid})

    resp = api_client.post(url, {"foo": "bar sky"}, format="json")

    assert resp.status_code == HTTP_204_NO_CONTENT

    model = table.get_model()
    rows = model.objects.all()
    assert len(rows) == 1
    assert getattr(rows[0], f"field_{fields[0].id}") == "foo: bar sky"


@pytest.mark.django_db(transaction=True)
def test_core_http_trigger_node_duplicating_application_sets_unique_uid(data_fixture):
    user = data_fixture.create_user()

    workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger_node = data_fixture.create_http_trigger_node(user=user, workflow=workflow)
    assert isinstance(trigger_node.service.uid, uuid.UUID)

    duplicated_automation = CoreHandler().duplicate_application(
        user, workflow.automation
    )
    duplicated_service = (
        duplicated_automation.workflows.get()
        .automation_workflow_nodes.get()
        .specific.service.specific
    )

    assert isinstance(duplicated_service.uid, uuid.UUID)
    assert str(duplicated_service.uid) != str(trigger_node.service.uid)


@pytest.mark.django_db(transaction=True)
def test_core_http_trigger_node_duplicating_workflow_sets_unique_uid(data_fixture):
    user = data_fixture.create_user()

    workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.LIVE, create_trigger=False
    )
    trigger_node = data_fixture.create_http_trigger_node(user=user, workflow=workflow)
    assert isinstance(trigger_node.service.uid, uuid.UUID)

    duplicated_workflow = AutomationWorkflowService().duplicate_workflow(user, workflow)
    duplicated_service = (
        duplicated_workflow.automation_workflow_nodes.get().specific.service.specific
    )

    assert isinstance(duplicated_service.uid, uuid.UUID)
    assert str(duplicated_service.uid) != str(trigger_node.service.uid)
