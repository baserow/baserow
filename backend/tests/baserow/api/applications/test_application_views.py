from unittest.mock import patch

from django.db import connection
from django.db.models import QuerySet
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.models import Database
from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Template
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import application_type_registry


def stub_filter_queryset(u, o, q, **kwargs):
    return q


@pytest.mark.django_db()
@pytest.mark.parametrize("application_type", application_type_registry.get_all())
def test_can_create_different_application_types(
    application_type, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Test 1", "type": application_type.type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    application = application_type.model_class.objects.all()[0]

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == application_type.type
    assert response_json["id"] == application.id
    assert response_json["name"] == application.name
    assert response_json["order"] == application.order


@pytest.mark.django_db
def test_list_applications(api_client, data_fixture, django_assert_num_queries):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    workspace_3 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace_1, order=3
    )
    application_3 = data_fixture.create_database_application(
        workspace=workspace_1, order=2
    )
    data_fixture.create_database_application(workspace=workspace_2, order=1)
    application_4 = data_fixture.create_database_application(
        workspace=workspace_3, order=1
    )
    with patch(
        "baserow.core.handler.CoreHandler.filter_queryset",
        side_effect=stub_filter_queryset,
    ) as mock_filter_queryset:
        response = api_client.get(
            reverse("api:applications:list", kwargs={"workspace_id": workspace_1.id}),
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        assert len(mock_filter_queryset.mock_calls) <= 1 + 3, (
            "Should trigger 1 call for all the applications then max one call "
            "per application"
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 3

    _, args, kwargs = mock_filter_queryset.mock_calls[0]

    # Check that we call filter queryset with the right args
    assert args[0] == user
    assert args[1] == ListApplicationsWorkspaceOperationType.type
    assert isinstance(args[2], QuerySet)
    assert kwargs["workspace"] == workspace_1

    assert response_json[0]["id"] == application_1.id
    assert response_json[0]["type"] == "database"

    assert response_json[1]["id"] == application_3.id
    assert response_json[1]["type"] == "database"

    assert response_json[2]["id"] == application_2.id
    assert response_json[2]["type"] == "database"

    with patch(
        "baserow.core.handler.CoreHandler.filter_queryset",
        side_effect=stub_filter_queryset,
    ) as mock_filter_queryset:
        response = api_client.get(
            reverse("api:applications:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
        )

        assert (
            len(mock_filter_queryset.mock_calls) <= 2 + 4
        ), "Should trigger max 1 call by workspace + 1 by applications"

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 4
    assert response_json[0]["id"] == application_1.id
    assert response_json[1]["id"] == application_3.id
    assert response_json[2]["id"] == application_2.id
    assert response_json[3]["id"] == application_4.id

    response = api_client.get(
        reverse("api:applications:list", kwargs={"workspace_id": workspace_2.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:applications:list", kwargs={"workspace_id": 999999}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=workspace_1)
    workspace_1.has_template.cache_clear()
    url = reverse("api:applications:list", kwargs={"workspace_id": workspace_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK

    response = api_client.delete(
        reverse("api:workspaces:item", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace_1.id})
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse(
        "api:applications:list",
    )

    data_fixture.create_database_table(user, database=application_4)
    with CaptureQueriesContext(connection) as query_for_n_tables:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
    for application in response.json():
        assert application["workspace"]["id"] != workspace_1.id

    data_fixture.create_database_table(user, database=application_1)
    data_fixture.create_database_table(user, database=application_1)
    with CaptureQueriesContext(connection) as query_for_n_plus_one_tables:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    # the n +1 should have less or equal (because of some caching) queries
    assert len(query_for_n_tables.captured_queries) >= len(
        query_for_n_plus_one_tables.captured_queries
    )


@pytest.mark.django_db(transaction=True)
def test_list_applications_with_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    database_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace_2, order=1
    )

    response = api_client.get(
        reverse("api:applications:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()

    assert len(response_json) == 2

    assert [a["id"] for a in response_json] == [database_1.id, database_2.id]


@pytest.mark.django_db
def test_list_applications_without_workspace(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:applications:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response_json == []


@pytest.mark.django_db
def test_create_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Test 1", "type": "NOT_EXISTING"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_APPLICATION_TYPE_DOES_NOT_EXIST"
    assert (
        response_json["detail"] == "The application type NOT_EXISTING does not exist."
    )

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": 99999}),
        {"name": "Test 1", "type": "database"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace_2.id}),
        {"name": "Test 1", "type": "database"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace_2.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Test 1", "type": "database"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "database"

    database = Database.objects.filter()[0]
    assert response_json["id"] == database.id
    assert response_json["name"] == database.name
    assert response_json["order"] == database.order


@pytest.mark.django_db
def test_get_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user_2)
    application = data_fixture.create_database_application(workspace=workspace)
    application_2 = data_fixture.create_database_application(workspace=workspace_2)

    url = reverse("api:applications:item", kwargs={"application_id": application_2.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:applications:item", kwargs={"application_id": 99999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == application.id
    assert response_json["workspace"]["id"] == workspace.id

    response = api_client.delete(
        reverse(
            "api:workspaces:item", kwargs={"workspace_id": application.workspace.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user_2)
    application = data_fixture.create_database_application(workspace=workspace)
    application_2 = data_fixture.create_database_application(workspace=workspace_2)

    url = reverse("api:applications:item", kwargs={"application_id": application_2.id})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:applications:item", kwargs={"application_id": 999999})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    # Test that an empty payload doesn't cause any side effects.
    original_name = application.name
    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == application.id
    assert response_json["name"] == original_name
    application.refresh_from_db()
    assert application.name == original_name

    # Test that an unknown key in the payload is ignored.
    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.patch(
        url,
        {"name": "Test 1", "UNKNOWN_FIELD": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == application.id
    assert response_json["name"] == "Test 1"
    application.refresh_from_db()
    assert application.name == "Test 1"

    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == application.id
    assert response_json["name"] == "Test 1"

    application.refresh_from_db()
    assert application.name == "Test 1"


@pytest.mark.django_db
def test_delete_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user_2)
    application = data_fixture.create_database_application(workspace=workspace)
    application_2 = data_fixture.create_database_application(workspace=workspace_2)

    url = reverse("api:applications:item", kwargs={"application_id": application_2.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:applications:item", kwargs={"application_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    url = reverse("api:applications:item", kwargs={"application_id": application.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 204

    assert Database.objects.all().count() == 1


@pytest.mark.django_db
def test_order_applications(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace_1, order=2
    )
    application_3 = data_fixture.create_database_application(
        workspace=workspace_1, order=3
    )

    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": workspace_2.id}),
        {"application_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": 999999}),
        {"application_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": workspace_1.id}),
        {"application_ids": [0]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_APPLICATION_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": workspace_1.id}),
        {"application_ids": ["test"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:applications:order", kwargs={"workspace_id": workspace_1.id}),
        {"application_ids": [application_3.id, application_2.id, application_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    application_1.refresh_from_db()
    application_2.refresh_from_db()
    application_3.refresh_from_db()
    assert application_1.order == 3
    assert application_2.order == 2
    assert application_3.order == 1


@pytest.mark.django_db
def test_duplicate_application_errors(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user_1)
    _, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test2"
    )

    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    # user_2 cannot duplicate a table of other workspaces
    response = api_client.post(
        reverse(
            "api:applications:async_duplicate",
            kwargs={"application_id": application_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # cannot duplicate non-existent application
    response = api_client.post(
        reverse("api:applications:async_duplicate", kwargs={"application_id": 99999}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_duplicate_application_schedule_job(
    mock_run_async_job, api_client, data_fixture
):
    user_1, _ = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user_1)
    user_2, token_2 = data_fixture.create_user_and_token(
        email="test_3@test.nl",
        password="password",
        first_name="Test3",
        workspace=workspace_1,
    )
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    # user can duplicate an application created by other in the same workspace
    response = api_client.post(
        reverse(
            "api:applications:async_duplicate",
            kwargs={"application_id": application_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "duplicate_application"

    job = JobHandler.get_job(user_2, job["id"])
    assert job.user_id == user_2.id
    assert job.progress_percentage == 0
    assert job.state == "pending"
    assert job.error == ""

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == job.id


@pytest.mark.django_db(transaction=True)
def test_duplicate_job_response_serializer(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)

    job = JobHandler().create_and_start_job(
        user,
        DuplicateApplicationJobType.type,
        application_id=application.id,
    )

    # check that now the job ended correctly and the application was duplicated
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    job_rsp = response.json()
    assert job_rsp["state"] == "finished"
    assert job_rsp["type"] == "duplicate_application"
    assert job_rsp["original_application"]["id"] == application.id
    assert job_rsp["original_application"]["name"] == application.name
    assert job_rsp["original_application"]["type"] == "database"
    assert job_rsp["duplicated_application"]["id"] != application.id
    assert job_rsp["duplicated_application"]["name"] == f"{application.name} 2"
    assert job_rsp["duplicated_application"]["type"] == "database"


@pytest.mark.django_db
def test_anon_user_can_list_apps_of_app_in_template_workspace(
    api_client,
    data_fixture,
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    app = data_fixture.create_database_application(user, workspace=workspace)
    table = data_fixture.create_database_table(user, database=app)
    template = Template(
        workspace=workspace, slug="test", icon="test", export_hash="test"
    )
    template.save()

    response = api_client.get(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == app.id
    tables = response_json[0]["tables"]
    assert len(tables) == 1
    assert tables[0]["id"] == table.id
