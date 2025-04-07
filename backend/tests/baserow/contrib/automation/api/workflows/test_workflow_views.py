from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.test_utils.helpers import AnyInt

API_URL_BASE_AUTOMATION = "api:automation:automation_id"
API_URL_CREATE = f"{API_URL_BASE_AUTOMATION}:workflows:create"
API_URL_ORDER = f"{API_URL_BASE_AUTOMATION}:workflows:order"
API_URL_BASE_WORKFLOW = "api:automation:workflows"
API_URL_WORKFLOW_ITEM = f"{API_URL_BASE_WORKFLOW}:item"
API_URL_WORKFLOW_DUPLICATE = f"{API_URL_BASE_WORKFLOW}:async_duplicate"


@pytest.mark.django_db
def test_create_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)

    name = "Foo automation"
    url = reverse(API_URL_CREATE, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"name": name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "automation_id": AnyInt(),
        "id": AnyInt(),
        "name": name,
        "order": AnyInt(),
    }


@pytest.mark.django_db
def test_create_workflow_user_not_in_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application()

    url = reverse(API_URL_CREATE, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"name": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "detail": "You don't have the required permission to execute this operation.",
        "error": "PERMISSION_DENIED",
    }


@pytest.mark.django_db
def test_create_workflow_automation_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_CREATE, kwargs={"automation_id": 1234})
    response = api_client.post(
        url,
        {"name": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_workflow_duplicate_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    url = reverse(API_URL_CREATE, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"name": workflow.name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] != "test"


@pytest.mark.django_db
def test_update_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})
    response = api_client.patch(
        url, {"name": "test-updated"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "test-updated"


@pytest.mark.django_db
def test_update_workflow_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": 9999})
    response = api_client.patch(
        url, {"name": "test"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_workflow_duplicate_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2"
    )

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow_2.id})
    response = api_client.patch(
        url,
        {"name": workflow.name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_NAME_NOT_UNIQUE"


@pytest.mark.django_db
def test_order_workflows(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=1
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=2
    )

    url = reverse(API_URL_ORDER, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"workflow_ids": [workflow_2.id, workflow_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_order_workflows_user_not_in_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=1
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=2
    )

    url = reverse(API_URL_ORDER, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"workflow_ids": [workflow_2.id, workflow_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_order_workflows_workflow_not_in_automation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=1
    )
    workflow_2 = data_fixture.create_automation_workflow(name="test2", order=2)

    url = reverse(API_URL_ORDER, kwargs={"automation_id": automation.id})
    response = api_client.post(
        url,
        {"workflow_ids": [workflow_2.id, workflow_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_NOT_IN_AUTOMATION"


@pytest.mark.django_db
def test_order_workflows_automation_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=1
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=2
    )

    url = reverse(API_URL_ORDER, kwargs={"automation_id": 1234})
    response = api_client.post(
        url,
        {"workflow_ids": [workflow_2.id, workflow_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_delete_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_workflow_user_not_in_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application()
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_workflow_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": 1234})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_duplicate_workflow(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    url = reverse(API_URL_WORKFLOW_DUPLICATE, kwargs={"workflow_id": workflow.id})
    response = api_client.post(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_202_ACCEPTED
    assert response.json() == {
        "duplicated_automation_workflow": None,
        "human_readable_error": "",
        "id": AnyInt(),
        "original_automation_workflow": {
            "automation_id": automation.id,
            "id": workflow.id,
            "name": "test",
            "order": AnyInt(),
        },
        "progress_percentage": 0,
        "state": "pending",
        "type": "duplicate_automation_workflow",
    }
