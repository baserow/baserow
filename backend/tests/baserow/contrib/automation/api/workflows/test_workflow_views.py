import datetime

from django.urls import reverse
from django.utils import timezone

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.automation.workflows.constants import ALLOW_TEST_RUN_MINUTES
from baserow.contrib.database.rows.handler import RowHandler
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
        "allow_test_run_until": None,
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
            "allow_test_run_until": None,
            "automation_id": automation.id,
            "id": workflow.id,
            "name": "test",
            "order": AnyInt(),
        },
        "progress_percentage": 0,
        "state": "pending",
        "type": "duplicate_automation_workflow",
    }


@pytest.mark.django_db
def test_enable_workflow_test_run(api_client, data_fixture):
    frozen_time = "2025-06-04 11:00"
    with freeze_time(frozen_time):
        user, token = data_fixture.create_user_and_token()
        automation = data_fixture.create_automation_application(user=user)
        workflow = data_fixture.create_automation_workflow(
            automation=automation, name="test"
        )

    assert workflow.allow_test_run_until is None
    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})

    with freeze_time(frozen_time):
        response = api_client.patch(
            url,
            {"allow_test_run": True},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    assert (
        response.json()["allow_test_run_until"]
        == f"2025-06-04T11:0{ALLOW_TEST_RUN_MINUTES}:00Z"
    )
    workflow.refresh_from_db()
    assert workflow.allow_test_run_until == datetime.datetime(
        2025, 6, 4, 11, ALLOW_TEST_RUN_MINUTES, tzinfo=datetime.timezone.utc
    )


@pytest.mark.django_db
def test_disable_workflow_test_run(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )
    workflow.allow_test_run_until = timezone.now()
    workflow.save()

    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})
    response = api_client.patch(
        url, {"allow_test_run": False}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["allow_test_run_until"] is None
    workflow.refresh_from_db()
    assert workflow.allow_test_run_until is None


@pytest.mark.django_db
def test_run_workflow_in_test_mode(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    # First create a trigger node
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text"), ("Color", "text")],
        rows=[["BMW", "Blue"]],
    )

    trigger_node = data_fixture.create_automation_node(
        user=user, workflow=workflow, type="rows_created"
    )
    trigger_node.service.integration.authorized_user = user
    trigger_node.service.integration.save()

    trigger_node.service.table = table
    trigger_node.service.save()

    # Next create an action node
    table_2, fields_2, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )

    action_node = data_fixture.create_automation_node(
        user=user,
        workflow=workflow,
        type="create_row",
    )
    action_node.service.integration.authorized_user = user
    action_node.service.integration.save()

    action_node.service.table = table_2
    action_node.service.field_mappings.create(
        field=fields_2[0],
        value="'A new row'",
    )
    action_node.service.save()

    # Enable the test run
    url = reverse(API_URL_WORKFLOW_ITEM, kwargs={"workflow_id": workflow.id})
    api_client.patch(
        url, {"allow_test_run": True}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    workflow.refresh_from_db()
    assert workflow.allow_test_run_until is not None
    assert workflow.published is False

    # Insert a row to cause the trigger node to run
    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            fields[0].id: "New Name",
            fields[1].id: "New Color",
        },
    )

    # Now the 2nd table should have a new row entry
    model = table.get_model()
    row = model.objects.order_by("-id").first()
    assert getattr(row, f"field_{fields[0].id}") == "New Name"
    assert getattr(row, f"field_{fields[1].id}") == "New Color"
