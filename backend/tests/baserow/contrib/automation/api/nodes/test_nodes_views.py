from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.test_utils.helpers import AnyInt, AnyStr

API_URL_BASE = "api:automation:nodes"
API_URL_LIST = f"{API_URL_BASE}:list"
API_URL_ITEM = f"{API_URL_BASE}:item"
API_URL_ORDER = f"{API_URL_BASE}:order"


@pytest.mark.django_db
def test_create_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"type": "row_created"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": 1,
        "order": AnyStr(),
        "previous_node_output": "",
        "service": AnyInt(),
        "type": "row_created",
        "workflow": AnyInt(),
    }
    assert workflow.automation_workflow_nodes.count() == 1


@pytest.mark.django_db
def test_create_node_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, name="test")
    assert workflow.automation_workflow_nodes.count() == 0

    url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    response = api_client.post(
        url,
        {"foo": "bar"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
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
        {"type": "row_created"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json() == {
        "detail": "The requested workflow does not exist.",
        "error": "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_get_node(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    url = reverse(API_URL_LIST, kwargs={"workflow_id": node.workflow.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "id": node.id,
            "order": AnyStr(),
            "previous_node_output": "",
            "service": AnyInt(),
            "type": "row_created",
            "workflow": node.workflow.id,
        },
    ]


@pytest.mark.django_db
def test_get_node_invalid_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_LIST, kwargs={"workflow_id": 999})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_order_nodes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    list_url = reverse(API_URL_LIST, kwargs={"workflow_id": workflow.id})
    api_kwargs = {
        "format": "json",
        "HTTP_AUTHORIZATION": f"JWT {token}",
    }
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
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "detail": f"The node id {node.id} does not belong to the workflow.",
        "error": "ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW",
    }
