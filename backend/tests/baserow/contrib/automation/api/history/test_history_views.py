from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from tests.baserow.contrib.automation.api.utils import get_api_kwargs

API_URL_NODE_HISTORIES = "api:automation:history:node_histories"
API_URL_NODE_RESULT = "api:automation:history:node_result"


@pytest.mark.django_db
def test_get_node_histories(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    trigger_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=trigger,
        status=HistoryStatusChoices.SUCCESS,
    )

    url = reverse(
        API_URL_NODE_HISTORIES, kwargs={"workflow_history_id": workflow_history.id}
    )
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == trigger_history.id
    assert row["node"] == trigger.id
    assert row["edge_label"] == ""
    assert row["status"] == "success"


@pytest.mark.django_db
def test_get_node_histories_surfaces_router_edge_label(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    core_router = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    router_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=core_router.router
    )
    data_fixture.create_automation_node_result(
        node_history=router_history,
        result={"edge": {"label": "Foo label"}},
    )

    url = reverse(
        API_URL_NODE_HISTORIES, kwargs={"workflow_history_id": workflow_history.id}
    )
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    rows = {row["id"]: row for row in response.json()}
    assert rows[router_history.id]["edge_label"] == "Foo label"


@pytest.mark.django_db
def test_get_node_histories_permission_error(api_client, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )

    _, token = data_fixture.create_user_and_token()

    url = reverse(
        API_URL_NODE_HISTORIES, kwargs={"workflow_history_id": workflow_history.id}
    )
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_node_histories_workflow_history_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_NODE_HISTORIES, kwargs={"workflow_history_id": 999999})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert (
        response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST"
    )


@pytest.mark.django_db
def test_get_node_result(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )
    data_fixture.create_automation_node_result(
        node_history=node_history, result={"rows": [1, 2]}
    )

    url = reverse(API_URL_NODE_RESULT, kwargs={"node_history_id": node_history.id})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"result": {"rows": [1, 2]}}


@pytest.mark.django_db
def test_get_node_result_permission_error(api_client, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )
    data_fixture.create_automation_node_result(node_history=node_history)

    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_NODE_RESULT, kwargs={"node_history_id": node_history.id})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_node_result_node_history_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_NODE_RESULT, kwargs={"node_history_id": 999999})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AUTOMATION_NODE_HISTORY_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_node_result_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )

    url = reverse(API_URL_NODE_RESULT, kwargs={"node_history_id": node_history.id})
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AUTOMATION_NODE_RESULT_DOES_NOT_EXIST"
