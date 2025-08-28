from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.test_utils.helpers import AnyDict, AnyInt, AnyStr
from tests.baserow.contrib.automation.api.utils import get_api_kwargs

API_URL_BASE = "api:automation:nodes"
API_URL_LIST = f"{API_URL_BASE}:list"
API_URL_ITEM = f"{API_URL_BASE}:item"
API_URL_ORDER = f"{API_URL_BASE}:order"
API_URL_DUPLICATE = f"{API_URL_BASE}:duplicate"
API_URL_REPLACE = f"{API_URL_BASE}:replace"
API_URL_UNDO = "api:user:undo"
API_URL_REDO = "api:user:redo"


@pytest.mark.django_db
def test_create_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "create_row"},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": 1,
        "label": "",
        "order": AnyStr(),
        "previous_node_id": None,
        "previous_node_output": "",
        "service": AnyDict(),
        "type": "create_row",
        "workflow": AnyInt(),
    }
    assert workflow.automation_workflow_nodes.count() == 1


@pytest.mark.django_db
def test_create_node_before(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node1 = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, order="1.0000"
    )
    node3 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, order="2.0000"
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "create_row", "before_id": node3.id},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "label": "",
        "order": "1.50000000000000000000",
        "previous_node_id": node1.id,
        "previous_node_output": "",
        "service": AnyDict(),
        "type": "create_row",
        "workflow": workflow.id,
    }

    node2 = AutomationNode.objects.get(id=response.json()["id"])
    nodes = AutomationNode.objects.all()

    assert nodes[0].id == node1.id
    assert nodes[1].id == node2.id
    assert nodes[2].id == node3.id


@pytest.mark.django_db
def test_create_node_before_router_edge_output(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service()
    router = data_fixture.create_core_router_action_node(
        service=service, workflow=workflow
    )
    edge1 = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 1", condition="'true'"
    )
    edge1_output = AutomationNode.objects.get(
        previous_node_id=router.id, previous_node_output=edge1.uid
    )
    edge2 = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 2", condition="'true'"
    )
    edge2_output = AutomationNode.objects.get(
        previous_node_id=router.id, previous_node_output=edge2.uid
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "router", "before_id": edge2_output.id},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["previous_node_id"] == router.id
    assert response_json["previous_node_output"] == str(edge2.uid)

    # edge1's output should be *unaffected*.
    edge1_output.refresh_from_db()
    assert edge1_output.previous_node_id == router.id
    assert edge1_output.previous_node_output == str(edge1.uid)

    # edge2's output is now after the node we just created.
    edge2_output.refresh_from_db()
    assert edge2_output.previous_node_id == response_json["id"]
    assert edge2_output.previous_node_output == ""


@pytest.mark.django_db
def test_create_node_before_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node1_a = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, order="1.0000"
    )
    workflow_b = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow_b, order="1.0000"
    )
    node2_b = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow_b, order="2.0000"
    )

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})

    response = api_client.post(
        url,
        {"type": "create_row", "before_id": node1_a.id},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_BEFORE_INVALID",
        "detail": "You cannot create an automation node before a trigger.",
    }

    response = api_client.post(
        url,
        {"type": "create_row", "before_id": node2_b.id},
        **get_api_kwargs(token),
    )
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_BEFORE_INVALID",
        "detail": "The `before` node must belong to the same workflow "
        "as the one supplied.",
    }


@pytest.mark.django_db
def test_create_node_before_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    response = api_client.post(
        reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id}),
        {"type": "create_row", "before_id": 9999999999},
        **get_api_kwargs(token),
    )
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
        "detail": "The requested node does not exist.",
    }


@pytest.mark.django_db
def test_create_node_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    assert workflow.automation_workflow_nodes.count() == 0

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
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 999})
    response = api_client.post(
        url,
        {"type": "create_row"},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested workflow does not exist.",
        "error": "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_create_trigger_node_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "rows_created"},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED",
        "detail": "Triggers can not be created, deleted or duplicated, "
        "they can only be replaced with a different type.",
    }


@pytest.mark.django_db
def test_create_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.count() == 1

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    api_kwargs = get_api_kwargs(token)
    response = api_client.post(url, {"type": "create_row"}, **api_kwargs)
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
def test_get_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    url = reverse(API_URL_LIST, kwargs={"workflow_id": node.workflow.id})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "id": node.id,
            "label": "",
            "order": AnyStr(),
            "previous_node_id": None,
            "previous_node_output": "",
            "service": AnyDict(),
            "type": "create_row",
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
def test_order_nodes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    list_url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    api_kwargs = get_api_kwargs(token)
    response = api_client.get(list_url, **api_kwargs)
    assert [n["id"] for n in response.json()] == [node_1.id, node_2.id]

    order_url = reverse(API_URL_ORDER, kwargs={"workflow_id": workflow.id})
    payload = {"node_ids": [node_2.id, node_1.id]}
    response = api_client.post(order_url, payload, **api_kwargs)
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(list_url, **api_kwargs)
    assert [n["id"] for n in response.json()] == [node_2.id, node_1.id]


@pytest.mark.django_db
def test_order_nodes_invalid_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow_1 = data_fixture.create_automation_workflow(user=user)

    # Create a node that belongs to another workflow
    workflow_2 = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow_2)

    order_url = reverse(API_URL_ORDER, kwargs={"workflow_id": workflow_1.id})
    payload = {"node_ids": [node.id]}
    response = api_client.post(
        order_url,
        payload,
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": f"The node id {node.id} does not belong to the workflow.",
        "error": "ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW",
    }


@pytest.mark.django_db
def test_order_nodes_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)

    order_url = reverse(API_URL_ORDER, kwargs={"workflow_id": workflow.id})
    payload = {"node_ids": [node_2.id, node_1.id]}
    response = api_client.post(order_url, payload, **api_kwargs)
    assert response.status_code == HTTP_204_NO_CONTENT

    list_url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.get(list_url, **api_kwargs)
    assert [n["id"] for n in response.json()] == [node_2.id, node_1.id]

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

    response = api_client.get(list_url, **api_kwargs)
    assert [n["id"] for n in response.json()] == [node_1.id, node_2.id]

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK

    response = api_client.get(list_url, **api_kwargs)
    assert [n["id"] for n in response.json()] == [node_2.id, node_1.id]


@pytest.mark.django_db
def test_delete_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    response = api_client.delete(delete_url, **api_kwargs)
    assert response.status_code == HTTP_204_NO_CONTENT

    assert workflow.automation_workflow_nodes.count() == 0


@pytest.mark.django_db
def test_delete_trigger_node_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, type="rows_created"
    )

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    response = api_client.delete(delete_url, **api_kwargs)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_DELETABLE",
        "detail": "Triggers can not be created, deleted or duplicated, "
        "they can only be replaced with a different type.",
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
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    response = api_client.delete(delete_url, **api_kwargs)
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
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)
    action = data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)

    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": action.id})
    response = api_client.post(duplicate_url, **get_api_kwargs(token))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] != action.id
    assert response_json["previous_node_output"] == ""
    assert response_json["previous_node_id"] == action.id


@pytest.mark.django_db
def test_duplicate_trigger_node_disallowed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, type="rows_created"
    )

    api_kwargs = get_api_kwargs(token)
    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": node.id})
    response = api_client.post(duplicate_url, **api_kwargs)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED",
        "detail": "Triggers can not be created, deleted or duplicated, "
        "they can only be replaced with a different type.",
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
def test_duplicate_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": node.id})
    response = api_client.post(duplicate_url, **api_kwargs)
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
def test_update_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert node.previous_node_output == ""

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    payload = {"previous_node_output": "foo", "type": "create_row"}
    response = api_client.patch(update_url, payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": node.id,
        "label": "",
        "order": AnyStr(),
        "service": AnyDict(),
        "previous_node_id": None,
        "previous_node_output": "foo",
        "type": "create_row",
        "workflow": workflow.id,
    }


@pytest.mark.django_db
def test_update_node_invalid_node(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": 100})
    payload = {"previous_node_output": "foo", "type": "update_row"}
    response = api_client.patch(update_url, payload, **api_kwargs)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested node does not exist.",
        "error": "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_update_node_undo_redo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    update_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    payload = {"previous_node_output": "foo", "type": "update_row"}
    response = api_client.patch(update_url, payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert response.json()["previous_node_output"] == "foo"

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
    assert node.previous_node_output == ""

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    node.refresh_from_db()
    assert node.previous_node_output == "foo"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "irreplaceable_types",
    (["create_row", "rows_created"], ["rows_created", "create_row"]),
)
def test_replace_node_type_with_irreplaceable_type(
    api_client, data_fixture, irreplaceable_types
):
    original_type, irreplaceable_type = irreplaceable_types
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
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
@pytest.mark.parametrize(
    "replaceable_types",
    (["update_row", "delete_row"], ["rows_created", "rows_updated"]),
)
def test_replace_node_type_with_replaceable_type(
    api_client, data_fixture, replaceable_types
):
    original_type, replaceable_type = replaceable_types
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
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
        "previous_node_id": None,
        "order": AnyStr(),
        "service": AnyDict(),
        "previous_node_output": "",
    }


@pytest.mark.django_db
def test_create_router_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "router"},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": AnyInt(),
        "order": AnyStr(),
        "label": "",
        "previous_node_id": None,
        "previous_node_output": "",
        "service": {
            "context_data": None,
            "context_data_schema": None,
            "default_edge_label": "",
            "edges": [
                {
                    "condition": "",
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
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    first_edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )
    AutomationNode.objects.filter(previous_node_output=first_edge.uid).delete()
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
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )
    assert AutomationNode.objects.filter(previous_node_output=edge.uid).exists()
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
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )
    assert AutomationNode.objects.filter(previous_node_output=edge.uid).exists()
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
    workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_router_service(default_edge_label="Default")
    router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=service
    )
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Do this", condition="'true'"
    )
    assert AutomationNode.objects.filter(previous_node_output=edge.uid).exists()
    response = api_client.post(
        reverse(API_URL_REPLACE, kwargs={"node_id": router.id}),
        {"new_type": "create_row"},
        **get_api_kwargs(token),
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_NODE_NOT_REPLACEABLE",
        "detail": "Router nodes cannot be replaced if they "
        "have one or more output nodes associated with them.",
    }
