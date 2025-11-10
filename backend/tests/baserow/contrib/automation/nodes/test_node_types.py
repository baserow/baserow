import uuid
from unittest.mock import MagicMock, patch

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.handler import CoreHandler
from baserow.core.services.types import DispatchResult
from tests.baserow.contrib.automation.api.utils import get_api_kwargs

API_URL_BASE = "api:automation:nodes"
API_URL_MOVE = f"{API_URL_BASE}:move"


def test_automation_node_type_is_replaceable_with():
    trigger_node_type = automation_node_type_registry.get("local_baserow_rows_created")
    update_trigger_node_type = automation_node_type_registry.get(
        "local_baserow_rows_updated"
    )
    action_node_type = automation_node_type_registry.get("local_baserow_create_row")
    update_action_node_type = automation_node_type_registry.get(
        "local_baserow_update_row"
    )

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
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_create_row"
    )

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_create_row_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_create_row"
    )

    values = {"service": {}, "workflow": node.workflow}
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
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_create_row"
    )

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_local_baserow_rows_created_prepare_values_with_instance(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user, create_trigger=False)
    node = data_fixture.create_automation_node(
        workflow=workflow, type="local_baserow_rows_created"
    )

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_service_node_type_local_baserow_rows_created_prepare_values_without_instance(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user, create_trigger=False)
    node = data_fixture.create_automation_node(
        workflow=workflow, type="local_baserow_rows_created"
    )

    values = {"service": {}, "workflow": node.workflow}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@pytest.mark.django_db
def test_automation_node_type_update_row_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_update_row"
    )

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_update_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_update_row"
    )

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_with_instance(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        workflow=workflow, type="local_baserow_delete_row"
    )

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_without_instance(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    node = data_fixture.create_automation_node(
        workflow=workflow, type="local_baserow_delete_row"
    )
    another_node = data_fixture.create_automation_node(
        workflow=workflow, type="local_baserow_delete_row"
    )

    values = {
        "service": {},
        "workflow": node.workflow,
    }
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
    node = data_fixture.create_automation_node(
        user=user, type="local_baserow_delete_row"
    )

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


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

    # Create a Node + workflow that is disabled
    original_workflow = data_fixture.create_automation_workflow()
    workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.DISABLED, trigger_service_kwargs={"table": table}
    )
    workflow.automation.published_from = original_workflow
    workflow.automation.save()

    trigger = workflow.get_trigger()

    service_queryset = trigger.service.get_type().model_class.objects.filter(
        table=table
    )

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

    mock_async_start_workflow.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_type",
    [
        node_type.type
        for node_type in automation_node_type_registry.get_all()
        if node_type.is_workflow_trigger
    ],
)
def test_trigger_cant_be_moved(node_type, api_client, data_fixture):
    node_type = automation_node_type_registry.get(node_type)

    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user, trigger_type=node_type)
    trigger = workflow.get_trigger()
    node_after = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="before"
    )
    response = api_client.post(
        reverse(API_URL_MOVE, kwargs={"node_id": trigger.id}),
        {"reference_node_id": node_after.id, "position": "south", "output": ""},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_MOVABLE",
        "detail": "Trigger nodes cannot be moved.",
    }


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

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["fallback node"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )

    AutomationNodeService().duplicate_node(user, router.id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["router-"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "router-": {"next": {"Default": ["fallback node"]}},
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )


@pytest.mark.django_db
def test_moving_router_node_allowed_with_next_on_default_edge(api_client, data_fixture):
    node_type = automation_node_type_registry.get("router")

    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    before_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="before"
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=node_type.type,
    )
    after_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        label="after",
        reference_node=node,
    )
    response = api_client.post(
        reverse(API_URL_MOVE, kwargs={"node_id": node.id}),
        {"reference_node_id": trigger.id, "position": "south", "output": ""},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_202_ACCEPTED


@pytest.mark.django_db
def test_moving_router_node_not_allowed_with_next_on_edge(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    before_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="before"
    )
    router = data_fixture.create_core_router_action_node(
        workflow=workflow,
    )
    edge1 = data_fixture.create_core_router_service_edge(
        service=router.service,
        label="Do this",
        condition="'true'",
        output_label="output edge 1",
    )
    after_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="after", reference_node=router, output=edge1.uid
    )
    response = api_client.post(
        reverse(API_URL_MOVE, kwargs={"node_id": router.id}),
        {"reference_node_id": trigger.id, "position": "south", "output": ""},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_MOVABLE",
        "detail": "Router nodes cannot be moved if they "
        "have one or more output nodes associated with them.",
    }


@pytest.mark.django_db
def test_trigger_node_dispatch_returns_event_payload_if_not_simulated(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE, trigger_service_kwargs={"table": table}
    )

    trigger = workflow.get_trigger().specific

    dispatch_context = AutomationDispatchContext(workflow, "foo")

    result = trigger.get_type().dispatch(trigger, dispatch_context)

    assert result == DispatchResult(data="foo", status=200, output_uid="")


@pytest.mark.django_db
def test_trigger_node_dispatch_returns_sample_data_if_simulated(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE,
        trigger_service_kwargs={
            "table": table,
            "sample_data": {"data": {"foo": "bar"}},
        },
    )

    trigger = workflow.get_trigger()

    dispatch_context = AutomationDispatchContext(workflow, simulate_until_node=trigger)
    # If we don't reset this value, the trigger is considered as updatable and will
    # be dispatched.
    dispatch_context.update_sample_data_for = []

    result = trigger.get_type().dispatch(workflow.get_trigger(), dispatch_context)

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
