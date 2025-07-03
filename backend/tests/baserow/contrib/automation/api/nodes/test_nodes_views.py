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

API_URL_BASE = "api:automation:nodes"
API_URL_LIST = f"{API_URL_BASE}:list"
API_URL_ITEM = f"{API_URL_BASE}:item"
API_URL_ORDER = f"{API_URL_BASE}:order"
API_URL_DUPLICATE = f"{API_URL_BASE}:duplicate"
API_URL_REPLACE = f"{API_URL_BASE}:replace"
API_URL_UNDO = "api:user:undo"
API_URL_REDO = "api:user:redo"


def get_api_kwargs(token):
    return {
        "format": "json",
        "HTTP_AUTHORIZATION": f"JWT {token}",
        "HTTP_CLIENTSESSIONID": "test",
    }


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
        "order": "1.50000000000000000000",
        "previous_node_id": None,
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
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    api_kwargs = get_api_kwargs(token)
    response = api_client.post(url, {"type": "create_row"}, **api_kwargs)
    assert response.status_code == HTTP_200_OK

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
    assert workflow.automation_workflow_nodes.count() == 0

    response = api_client.patch(reverse(API_URL_REDO), payload, **api_kwargs)
    assert response.status_code == HTTP_200_OK
    assert workflow.automation_workflow_nodes.count() == 1


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
        "error": "ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED",
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
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    api_kwargs = get_api_kwargs(token)
    delete_url = reverse(API_URL_ITEM, kwargs={"node_id": node.id})
    response = api_client.delete(delete_url, **api_kwargs)
    assert workflow.automation_workflow_nodes.count() == 0

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
    assert workflow.automation_workflow_nodes.count() == 0


@pytest.mark.django_db
def test_duplicate_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert workflow.automation_workflow_nodes.count() == 1

    api_kwargs = get_api_kwargs(token)
    duplicate_url = reverse(API_URL_DUPLICATE, kwargs={"node_id": node.id})
    response = api_client.post(duplicate_url, **api_kwargs)
    assert response.status_code == HTTP_204_NO_CONTENT

    assert workflow.automation_workflow_nodes.count() == 2


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
    assert response.status_code == HTTP_204_NO_CONTENT

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
        "detail": "Automation nodes can only be updated with a type of the same "
        "category. Triggers cannot be updated with actions, and vice-versa.",
        "error": "ERROR_AUTOMATION_NODE_NOT_REPLACEABLE",
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
        "type": replaceable_type,
        "workflow": workflow.id,
        "previous_node_id": None,
        "order": AnyStr(),
        "service": AnyDict(),
        "previous_node_output": "",
    }
