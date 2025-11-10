from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.test_utils.helpers import AnyDict, AnyInt, AnyStr
from tests.baserow.contrib.automation.api.utils import get_api_kwargs

API_URL_BASE = "api:automation:nodes"
API_URL_LIST = f"{API_URL_BASE}:list"
API_URL_ITEM = f"{API_URL_BASE}:item"
API_URL_MOVE = f"{API_URL_BASE}:move"
API_URL_ORDER = f"{API_URL_BASE}:order"
API_URL_DUPLICATE = f"{API_URL_BASE}:duplicate"
API_URL_REPLACE = f"{API_URL_BASE}:replace"
API_URL_SIMULATE_DISPATCH = f"{API_URL_BASE}:simulate_dispatch"
API_URL_UNDO = "api:user:undo"
API_URL_REDO = "api:user:redo"


@pytest.mark.django_db
def test_create_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node_before = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow_update_row",
            "reference_node_id": trigger.id,
            "position": "south",
            "output": "",
        },
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "label": "",
        "service": AnyDict(),
        "type": "local_baserow_update_row",
        "workflow": workflow.id,
    }

    AutomationNode.objects.get(id=response.json()["id"])

    workflow.refresh_from_db()
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_create_row": {},
            "local_baserow_rows_created": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {"next": {"": ["local_baserow_create_row"]}},
        }
    )


@pytest.mark.django_db
def test_create_node_reference_node_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow_a = data_fixture.create_automation_workflow(user)
    trigger_a = workflow_a.get_trigger()
    workflow_b = data_fixture.create_automation_workflow(user)
    node2_b = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow_b
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow_a.id})

    response = api_client.post(
        url,
        {
            "type": "local_baserow_create_row",
            "reference_node_id": 99999999999,
            "position": "south",
            "output": "",
        },
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_REFERENCE_NODE_INVALID",
        "detail": "The reference node 99999999999 doesn't exist",
    }

    response = api_client.post(
        url,
        {
            "type": "local_baserow_create_row",
            "reference_node_id": node2_b.id,
            "position": "south",
            "output": "",
        },
        **get_api_kwargs(token),
    )
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_REFERENCE_NODE_INVALID",
        "detail": f"The reference node {node2_b.id} doesn't exist",
    }


@pytest.mark.django_db
def test_create_node_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user, name="test")

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"foo": "bar"},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": {
            "type": [
                {
                    "code": "required",
                    "error": "This field is required.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }


@pytest.mark.django_db
def test_create_node_invalid_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 0})
    response = api_client.post(
        url,
        {
            "type": "local_baserow_create_row",
            "reference_node_id": 0,
            "position": "south",
            "output": "",
        },
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested workflow does not exist.",
        "error": "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_create_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user, name="test")
    assert workflow.automation_workflow_nodes.count() == 1

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    api_kwargs = get_api_kwargs(token)

    response = api_client.post(
        url,
        {
            "type": "local_baserow_create_row",
            "reference_node_id": workflow.get_trigger().id,
            "position": "south",
            "output": "",
        },
        **api_kwargs,
    )
    assert response.status_code == HTTP_200_OK

    assert workflow.automation_workflow_nodes.count() == 2

    payload = {
        "scopes": {
            "workspace": workflow.automation.workspace.id,
            "application": workflow.automation.id,
            "root": True,
            "workflow": workflow.id,
        },
    }

    response = api_client.patch(reverse(API_URL_UNDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert workflow.automation_workflow_nodes.count() == 1

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert workflow.automation_workflow_nodes.count() == 2


@pytest.mark.django_db
def test_get_nodes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(workflow=workflow)

    url = reverse(API_URL_LIST, kwargs={"workflow_id": node.workflow.id})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "id": trigger.id,
            "label": trigger.label,
            "service": AnyDict(),
            "type": "local_baserow_rows_created",
            "workflow": workflow.id,
        },
        {
            "id": node.id,
            "label": node.label,
            "service": AnyDict(),
            "type": "local_baserow_create_row",
            "workflow": node.workflow.id,
        },
    ]


@pytest.mark.django_db
def test_get_node_invalid_workflow(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 999})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    response = api_client.delete(delete_url, **get_api_kwargs(token))
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_trigger_node_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)

    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": trigger.id})
    response = api_client.delete(delete_url, **get_api_kwargs(token))
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_DELETABLE",
        "detail": "Trigger nodes cannot be deleted if they are followed nodes.",
    }


@pytest.mark.django_db
def test_delete_node_invalid_node(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": 100})
    response = api_client.delete(delete_url, **api_kwargs)
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    api_client.delete(delete_url, **api_kwargs)
    assert workflow.automation_workflow_nodes.count() == 1

    payload = {
        "scopes": {
            "workspace": workflow.automation.workspace.id,
            "application": workflow.automation.id,
            "root": True,
            "workflow": workflow.id,
        },
    }
    response = api_client.patch(reverse(API_URL_UNDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert workflow.automation_workflow_nodes.count() == 2

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert workflow.automation_workflow_nodes.count() == 1


@pytest.mark.django_db
def test_duplicate_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="To duplicate"
    )

    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": action.id})

    response = api_client.post(duplicate_url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] != action.id

    workflow.refresh_from_db()

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["To duplicate"]}},
            "To duplicate": {"next": {"": ["To duplicate-"]}},
            "To duplicate-": {},
        }
    )


@pytest.mark.django_db
def test_duplicate_trigger_node_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()

    api_kwargs = get_api_kwargs(token)
    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": trigger.id})
    response = api_client.post(duplicate_url, **api_kwargs)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_TRIGGER_ALREADY_EXISTS",
        "detail": "This workflow already has a trigger",
    }


@pytest.mark.django_db
def test_duplicate_node_invalid_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    api_kwargs = get_api_kwargs(token)
    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": 100})
    response = api_client.post(duplicate_url, **api_kwargs)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested node does not exist.",
        "error": "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_update_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert node.label == ""

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    payload = {"label": "foo"}
    response = api_client.patch(update_url, payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": node.id,
        "label": "foo",
        "service": AnyDict(),
        "type": node.get_type().type,
        "workflow": workflow.id,
    }


@pytest.mark.django_db
def test_update_node_invalid_node(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": 100})
    payload = {"type": "local_baserow_update_row"}
    response = api_client.patch(update_url, payload, **api_kwargs)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested node does not exist.",
        "error": "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_update_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    payload = {"label": "foo"}

    response = api_client.patch(update_url, payload, **api_kwargs)

    assert response.status_code == HTTP_200_OK
    assert response.json()["label"] == "foo"

    payload = {
        "scopes": {
            "workspace": workflow.automation.workspace.id,
            "application": workflow.automation.id,
            "root": True,
            "workflow": workflow.id,
        },
    }
    response = api_client.patch(reverse(API_URL_UNDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert node.label == ""

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    node.refresh_from_db()
    assert node.label == "foo"


@pytest.mark.django_db
def test_replace_node_type_with_irreplaceable_type(
    api_client,
    data_fixture,
):
    original_type, irreplaceable_type = [
        "local_baserow_create_row",
        "local_baserow_rows_created",
    ]
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(
        user=user, type=original_type, workflow=workflow
    )
    response = api_client.post(
        reverse(API_URL_REPLACE, kwargs={"node_id": node.id}),
        {"new_type": irreplaceable_type},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_REPLACEABLE",
        "detail": "Automation nodes can only be updated with a type of the same "
        "category. Triggers cannot be updated with actions, and vice-versa.",
    }


@pytest.mark.django_db
def test_replace_node_type_with_replaceable_type_trigger(
    api_client,
    data_fixture,
):
    original_type, replaceable_type = [
        "local_baserow_rows_created",
        "local_baserow_rows_updated",
    ]
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user, trigger_type=original_type)
    trigger = workflow.get_trigger()

    response = api_client.post(
        reverse(API_URL_REPLACE, kwargs={"node_id": trigger.id}),
        {"new_type": replaceable_type},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "label": "",
        "type": replaceable_type,
        "workflow": workflow.id,
        "service": AnyDict(),
    }


@pytest.mark.django_db
def test_replace_node_type_with_replaceable_type(
    api_client,
    data_fixture,
):
    original_type, replaceable_type = [
        "local_baserow_update_row",
        "local_baserow_delete_row",
    ]
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(
        user=user, type=original_type, workflow=workflow
    )

    response = api_client.post(
        reverse(API_URL_REPLACE, kwargs={"node_id": node.id}),
        {"new_type": replaceable_type},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "label": "",
        "type": replaceable_type,
        "workflow": workflow.id,
        "service": AnyDict(),
    }


@pytest.mark.django_db
def test_create_router_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})

    response = api_client.post(
        url,
        {
            "type": "router",
            "reference_node_id": trigger.id,
            "position": "south",
            "output": "",
        },
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "label": "",
        "service": {
            "sample_data": None,
            "context_data": None,
            "context_data_schema": None,
            "default_edge_label": "",
            "edges": [
                {
                    "condition": {"formula": "", "mode": "simple", "version": "0.1"},
                    "label": "Branch",
                    "order": AnyStr(),
                    "uid": AnyStr(),
                },
            ],
            "id": AnyInt(),
            "integration_id": None,
            "schema": {
                "properties": {
                    "edge": {
                        "properties": {
                            "label": {
                                "description": "The label of the branch that matched the condition.",
                                "title": "Label",
                                "type": "string",
                            },
                        },
                        "title": "Branch taken",
                        "type": "object",
                    },
                },
                "title": AnyStr(),
                "type": "object",
            },
            "type": "router",
        },
        "type": "router",
        "workflow": workflow.id,
    }


@pytest.mark.django_db
def test_updating_router_node_removing_edge_without_output_allowed(
    api_client,
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    first_edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'", skip_output_node=True
    )

    second_edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do that", condition="'true'"
    )

    response = api_client.patch(
        reverse(API_URL_ITEM, kwargs={"node_id": router.id}),
        {
            "service": {
                "type": "router",
                "edges": [
                    {
                        "uid": second_edge.uid,
                        "label": second_edge.label,
                        "condition": second_edge.condition,
                    }
                ],
            },
            "type": "router",
        },
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["service"]["edges"] == [
        {
            "uid": str(second_edge.uid),
            "label": second_edge.label,
            "order": "0.00000000000000000000",
            "condition": second_edge.condition,
        }
    ]


@pytest.mark.django_db
def test_updating_router_node_with_edge_removals_when_they_have_output_nodes_disallowed(
    api_client,
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )

    assert (
        workflow.get_graph().get_node_at_position(router, "south", str(edge.uid))
        is not None
    )

    response = api_client.patch(
        reverse(API_URL_ITEM, kwargs={"node_id": router.id}),
        {"service": {"edges": [], "type": "router"}, "type": "router"},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_MISCONFIGURED_SERVICE",
        "detail": "One or more branches have been removed from the router node, "
        "but they still point to output nodes. These nodes must be trashed before "
        "the router can be updated.",
    }


@pytest.mark.django_db
def test_deleting_router_node_with_output_nodes_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )

    assert (
        workflow.get_graph().get_node_at_position(router, "south", str(edge.uid))
        is not None
    )

    response = api_client.delete(
        reverse(API_URL_ITEM, kwargs={"node_id": router.id}),
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_DELETABLE",
        "detail": "Router nodes cannot be deleted if they "
        "have one or more output nodes associated with them.",
    }


@pytest.mark.django_db
def test_replacing_router_node_with_output_nodes_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )

    assert (
        workflow.get_graph().get_node_at_position(router, "south", str(edge.uid))
        is not None
    )

    response = api_client.post(
        reverse(API_URL_REPLACE, kwargs={"node_id": router.id}),
        {"new_type": "local_baserow_create_row"},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_REPLACEABLE",
        "detail": "Router nodes cannot be replaced if they "
        "have one or more output nodes associated with them.",
    }


@pytest.mark.django_db
def test_simulate_dispatch_invalid_node(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": 100})
    payload = {"update_sample_data": False}
    response = api_client.post(url, payload, **api_kwargs)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested node does not exist.",
        "error": "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
    }


@pytest.mark.django_db()
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_simulate_dispatch_trigger_node(
    mock_async_start_workflow, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    # Create a trigger node with service
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )

    trigger_node = workflow.get_trigger()

    assert trigger_node.workflow.simulate_until_node is None

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": trigger_node.id})
    response = api_client.post(url, **api_kwargs)

    assert response.status_code == HTTP_202_ACCEPTED

    workflow = trigger_node.workflow
    workflow.refresh_from_db()

    assert workflow.simulate_until_node_id == trigger_node.id
    mock_async_start_workflow.assert_not_called()


@pytest.mark.django_db()
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_simulate_dispatch_trigger_node_immediate_dispatch(
    mock_async_start_workflow, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CorePeriodicTriggerNodeType.type
    )

    trigger_node = workflow.get_trigger()

    assert trigger_node.workflow.simulate_until_node is None

    old_imm = trigger_node.service.get_type().can_immediately_be_tested
    trigger_node.service.get_type().can_immediately_be_tested = lambda s: True

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": trigger_node.id})
    response = api_client.post(url, **api_kwargs)

    assert response.status_code == HTTP_202_ACCEPTED

    workflow = trigger_node.workflow
    workflow.refresh_from_db()

    assert workflow.simulate_until_node_id == trigger_node.id
    # In case of an immediate dispatch we want to trigger immediately the workflow
    mock_async_start_workflow.assert_called_with(workflow)

    trigger_node.service.get_type().can_immediately_be_tested = old_imm


@pytest.mark.django_db()
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_simulate_dispatch_trigger_node_with_sample_data(
    mock_async_start_workflow, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    # Create a trigger node with service
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )

    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={
            "table": table,
            "integration": data_fixture.create_local_baserow_integration(user=user),
        },
    )
    trigger_node = workflow.get_trigger()

    # Initially, the sample_data should be empty
    assert trigger_node.workflow.simulate_until_node is None

    trigger_node.service.sample_data = {"data": {"test": "data"}}
    trigger_node.service.save()

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": trigger_node.id})
    response = api_client.post(url, **api_kwargs)

    assert response.status_code == HTTP_202_ACCEPTED

    workflow = trigger_node.workflow
    workflow.refresh_from_db()

    assert workflow.simulate_until_node_id == trigger_node.id
    # Should be not called as even if the sample data are set, we are simulating the
    # trigger itself so we need to wait for a new event
    mock_async_start_workflow.assert_not_called()


@pytest.mark.django_db()
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_simulate_dispatch_action_node(
    mock_async_start_workflow, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    # Create a trigger node with service
    table_1, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Pumpkin pie"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_service_kwargs={"table": table_1},
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
    )

    # Create an action node with service
    table_2, fields_2, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )

    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table_2,
        integration=data_fixture.create_local_baserow_integration(user=user),
    )
    action_service.field_mappings.create(
        field=fields_2[0],
        value="'A new row'",
    )
    action_node = data_fixture.create_automation_node(
        user=user,
        workflow=workflow,
        type="local_baserow_create_row",
        service=action_service,
    )

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": action_node.id})
    response = api_client.post(url, **api_kwargs)

    assert response.status_code == HTTP_202_ACCEPTED

    # Not called as the trigger is not an immediate trigger
    mock_async_start_workflow.assert_not_called()

    workflow.refresh_from_db()

    assert workflow.simulate_until_node_id == action_node.id


@pytest.mark.django_db()
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowHandler.async_start_workflow"
)
def test_simulate_dispatch_action_node_with_sample_data(
    mock_async_start_workflow, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    # Create a trigger node with service
    table_1, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Pumpkin pie"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_service_kwargs={"table": table_1},
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
    )

    # Create an action node with service
    table_2, fields_2, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )

    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table_2,
        integration=data_fixture.create_local_baserow_integration(user=user),
    )
    action_service.field_mappings.create(
        field=fields_2[0],
        value="'A new row'",
    )
    action_node = data_fixture.create_automation_node(
        user=user,
        workflow=workflow,
        type="local_baserow_create_row",
        service=action_service,
    )

    trigger_node = workflow.get_trigger()
    trigger_node.service.sample_data = {"data": {"test": "data"}}
    trigger_node.service.save()

    api_kwargs = get_api_kwargs(token)
    url = reverse(API_URL_SIMULATE_DISPATCH, kwargs={"node_id": action_node.id})
    response = api_client.post(url, **api_kwargs)

    assert response.status_code == HTTP_202_ACCEPTED

    # As the trigger node has sample data we can immediately trigger the workflow
    mock_async_start_workflow.assert_called_with(workflow)

    workflow.refresh_from_db()
    assert workflow.simulate_until_node_id == action_node.id
