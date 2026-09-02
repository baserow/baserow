from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from tests.baserow.contrib.automation.api.utils import get_api_kwargs

API_URL_NODE_HISTORIES = "api:automation:history:node_histories"
API_URL_NODE_RESULT = "api:automation:history:node_result"
API_URL_CANCEL_WORKFLOW_HISTORY = "api:automation:history:cancel_workflow_history"


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
def test_get_node_histories_surfaces_goto_destination(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger, label="destination node"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination
    )
    goto_node.service.specific.destination_service = destination.service
    goto_node.service.specific.save()

    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    goto_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=goto_node
    )

    url = reverse(
        API_URL_NODE_HISTORIES, kwargs={"workflow_history_id": workflow_history.id}
    )
    response = api_client.get(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    rows = {row["id"]: row for row in response.json()}
    row = rows[goto_history.id]
    assert row["destination_node_id"] == destination.id
    assert row["destination_node_type"] == destination.get_type().type
    assert row["destination_label"] == "destination node"


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
def test_cancel_workflow_history(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow, status=HistoryStatusChoices.STARTED
    )

    url = reverse(
        API_URL_CANCEL_WORKFLOW_HISTORY,
        kwargs={"workflow_history_id": workflow_history.id},
    )
    response = api_client.post(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == workflow_history.id
    # The run is only flagged: it stays running until the runner notices.
    assert response_json["status"] == "started"
    assert response_json["cancellation_requested_on"] is not None

    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED
    assert workflow_history.cancellation_requested_by == user
    assert workflow_history.cancellation_requested_on is not None


@pytest.mark.django_db
def test_cancel_workflow_history_permission_error(api_client, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow, status=HistoryStatusChoices.STARTED
    )

    _, token = data_fixture.create_user_and_token()

    url = reverse(
        API_URL_CANCEL_WORKFLOW_HISTORY,
        kwargs={"workflow_history_id": workflow_history.id},
    )
    response = api_client.post(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    workflow_history.refresh_from_db()
    assert workflow_history.cancellation_requested_on is None


@pytest.mark.django_db
def test_cancel_workflow_history_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(
        API_URL_CANCEL_WORKFLOW_HISTORY, kwargs={"workflow_history_id": 999999}
    )
    response = api_client.post(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert (
        response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST"
    )


@pytest.mark.django_db
def test_cancel_workflow_history_simulation_run_does_not_exist(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
        status=HistoryStatusChoices.STARTED,
        simulate_until_node=workflow.get_trigger(),
    )

    url = reverse(
        API_URL_CANCEL_WORKFLOW_HISTORY,
        kwargs={"workflow_history_id": workflow_history.id},
    )
    response = api_client.post(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert (
        response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_HISTORY_DOES_NOT_EXIST"
    )


@pytest.mark.django_db
def test_cancel_workflow_history_not_running(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
        status=HistoryStatusChoices.SUCCESS,
        completed_on=timezone.now(),
    )

    url = reverse(
        API_URL_CANCEL_WORKFLOW_HISTORY,
        kwargs={"workflow_history_id": workflow_history.id},
    )
    response = api_client.post(url, **get_api_kwargs(token))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_AUTOMATION_WORKFLOW_HISTORY_NOT_RUNNING",
        "detail": "The automation workflow history is not running anymore.",
    }


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
