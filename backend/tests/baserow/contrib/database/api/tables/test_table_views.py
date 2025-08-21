import json
from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.file_import.models import FileImportJob
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.jobs.models import Job
from baserow.test_utils.helpers import (
    assert_serialized_rows_contain_same_values,
    independent_test_db_connection,
    setup_interesting_test_table,
)


@pytest.mark.django_db
def test_list_all_tables_access_to_one_specific_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=[table_1],
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 1
    assert response_json == [
        {
            "id": table_1.id,
            "database_id": table_1.database_id,
            "name": table_1.name,
            "order": table_1.order,
        }
    ]
    assert response_json[0]["id"] == table_1.id


@pytest.mark.django_db
def test_list_all_tables_access_to_two_specific_tables(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=[table_1, table_3],
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 2
    assert response_json[0]["id"] == table_1.id
    assert response_json[1]["id"] == table_3.id


@pytest.mark.django_db
def test_list_all_tables_access_to_one_specific_database(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=[database],
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 2
    assert response_json[0]["id"] == table_1.id
    assert response_json[1]["id"] == table_2.id


@pytest.mark.django_db
def test_list_all_tables_access_to_specific_database_and_table(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=[table_1, database_2],
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 2
    assert response_json[0]["id"] == table_1.id
    assert response_json[1]["id"] == table_3.id


@pytest.mark.django_db
def test_list_all_tables_access_to_specific_all_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=True,
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 3
    assert response_json[0]["id"] == table_1.id
    assert response_json[1]["id"] == table_2.id
    assert response_json[2]["id"] == table_3.id


@pytest.mark.django_db
def test_list_all_tables_access_to_none(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, workspace_1, "Good")
    TokenHandler().update_token_permissions(
        user=user,
        token=token,
        create=False,
        read=False,
        update=False,
        delete=False,
    )

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    response_json = response.json()

    assert len(response_json) == 0


@pytest.mark.django_db
def test_list_all_tables_access_no_authentication(api_client, data_fixture):
    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url)
    response_json = response.json()
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_list_all_tables_access_jwt_token(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database_2, order=3)
    table_4 = data_fixture.create_database_table(user=user)
    table_5 = data_fixture.create_database_table()

    url = reverse("api:database:tables:all_tables")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_list_tables(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    database_2 = data_fixture.create_database_application()
    table_1 = data_fixture.create_database_table(database=database, order=2)
    table_2 = data_fixture.create_database_table(database=database, order=1)
    data_fixture.create_database_table(database=database_2)

    url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0]["id"] == table_2.id
    assert response_json[1]["id"] == table_1.id

    url = reverse("api:database:tables:list", kwargs={"database_id": database_2.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tables:list", kwargs={"database_id": 9999})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse("api:workspaces:item", kwargs={"workspace_id": database.workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_list_tables_with_data_sync(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    data_sync_1 = DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://localhost",
    )
    fields = data_sync_1.table.field_set.all().order_by("id")

    with CaptureQueriesContext(connection) as query_for_n_tables:
        url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert len(response_json) == 1
        assert response_json[0]["data_sync"] == {
            "id": data_sync_1.id,
            "type": "ical_calendar",
            "last_sync": None,
            "last_error": None,
            "auto_add_new_properties": False,
            "two_way_sync": False,
            "synced_properties": [
                {"field_id": fields[0].id, "key": "uid", "unique_primary": True},
                {"field_id": fields[1].id, "key": "dtstart", "unique_primary": False},
                {"field_id": fields[2].id, "key": "dtend", "unique_primary": False},
                {"field_id": fields[3].id, "key": "summary", "unique_primary": False},
            ],
        }

    DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://localhost",
    )

    with CaptureQueriesContext(connection) as query_for_n_plus_one_tables:
        url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK

    assert len(query_for_n_tables.captured_queries) >= len(
        query_for_n_plus_one_tables.captured_queries
    )


@pytest.mark.django_db
def test_list_tables_doesnt_do_n_queries_per_tables(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    database_2 = data_fixture.create_database_application()
    table_1 = data_fixture.create_database_table(database=database, order=2)
    table_2 = data_fixture.create_database_table(database=database, order=1)
    data_fixture.create_database_table(database=database_2)

    with CaptureQueriesContext(connection) as query_for_n_tables:
        url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK

    table_3 = data_fixture.create_database_table(database=database, order=1)

    with CaptureQueriesContext(connection) as query_for_n_plus_one_tables:
        url = reverse("api:database:tables:list", kwargs={"database_id": database.id})
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK

    assert len(query_for_n_tables.captured_queries) >= len(
        query_for_n_plus_one_tables.captured_queries
    )


@pytest.mark.django_db
def test_create_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    database_2 = data_fixture.create_database_application()

    url = reverse(
        "api:database:tables:async_create", kwargs={"database_id": database_2.id}
    )
    response = api_client.post(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse(
        "api:database:tables:async_create", kwargs={"database_id": database.id}
    )
    response = api_client.post(
        url, {"not_a_name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tables:async_create", kwargs={"database_id": 9999})
    response = api_client.post(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    # Should create an example database
    url = reverse(
        "api:database:tables:async_create", kwargs={"database_id": database.id}
    )
    response = api_client.post(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    json_response = response.json()

    job = FileImportJob.objects.get(id=json_response["id"])

    assert job.table is not None
    assert job.table.name == "Test 1"

    model = job.table.get_model()

    assert job.table.field_set.count() == 3
    assert model.objects.count() == 2


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_create_table_with_data(
    mock_run_async_job, api_client, data_fixture, patch_filefield_storage
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    url = reverse(
        "api:database:tables:async_create", kwargs={"database_id": database.id}
    )

    response = api_client.post(
        url,
        {"name": "Test 1", "data": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["data"][0]["code"] == "min_length"

    with patch_filefield_storage():
        response = api_client.post(
            url,
            {
                "name": "Test 1",
                "data": [
                    ["A", "B", "C", "D"],
                    ["1-1", "1-2", "1-3", "1-4", "1-5"],
                    ["2-1", "2-2", "2-3"],
                    ["3-1", "3-2"],
                ],
                "first_row_header": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    mock_run_async_job.delay.assert_called_with(response_json["id"])

    job = FileImportJob.objects.get(id=response_json["id"])

    assert job.table is None
    assert job.name == "Test 1"
    assert job.first_row_header
    assert job.database == database

    with patch_filefield_storage():
        with job.data_file.open("r") as fin:
            data = json.load(fin)
            assert data.get("data") == [
                ["A", "B", "C", "D"],
                ["1-1", "1-2", "1-3", "1-4", "1-5"],
                ["2-1", "2-2", "2-3"],
                ["3-1", "3-2"],
            ]


@pytest.mark.django_db(transaction=True)
def test_create_table_with_data_sync(api_client, data_fixture, patch_filefield_storage):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    url = reverse("api:database:tables:list", kwargs={"database_id": database.id})

    with override_settings(
        BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT=2
    ), patch_filefield_storage():
        response = api_client.post(
            url,
            {
                "name": "Test 1",
                "data": [
                    ["A", "B", "C", "D"],
                    ["1-1", "1-2", "1-3", "1-4", "1-5"],
                    ["2-1", "2-2", "2-3"],
                    ["3-1", "3-2"],
                ],
                "first_row_header": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INITIAL_SYNC_TABLE_DATA_LIMIT_EXCEEDED"

    with patch_filefield_storage():
        response = api_client.post(
            url,
            {
                "name": "Test 1",
                "data": [
                    ["A", "B", "C", "D"],
                    ["1-1", "1-2", "1-3", "1-4", "1-5"],
                    ["2-1", "2-2", "2-3"],
                    ["3-1", "3-2"],
                ],
                "first_row_header": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json["name"] == "Test 1"

    table = Table.objects.get(id=response_json["id"])

    model = table.get_model()
    assert model.objects.count() == 3

    # Test empty data
    with patch_filefield_storage():
        response = api_client.post(
            url,
            {
                "name": "Test 2",
                "first_row_header": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert response_json["name"] == "Test 2"

    table = Table.objects.get(id=response_json["id"])

    model = table.get_model()
    assert model.objects.count() == 2


@pytest.mark.django_db
def test_get_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    url = reverse("api:database:tables:item", kwargs={"table_id": table_1.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    json_response = response.json()
    assert json_response["id"] == table_1.id
    assert json_response["name"] == table_1.name
    assert json_response["order"] == table_1.order
    assert json_response["database_id"] == table_1.database_id

    url = reverse("api:database:tables:item", kwargs={"table_id": table_2.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    json_response = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert json_response["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tables:item", kwargs={"table_id": 9999})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    url = reverse("api:database:tables:item", kwargs={"table_id": table_1.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    table_1.refresh_from_db()

    assert response_json["id"] == table_1.id
    assert response_json["name"] == table_1.name == "New name"

    url = reverse("api:database:tables:item", kwargs={"table_id": table_2.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tables:item", kwargs={"table_id": table_1.id})
    response = api_client.patch(
        url,
        {"not_a_name": "New name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tables:item", kwargs={"table_id": 999})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_order_tables(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database_1 = data_fixture.create_database_application(user=user)
    database_2 = data_fixture.create_database_application()
    table_1 = data_fixture.create_database_table(database=database_1, order=1)
    table_2 = data_fixture.create_database_table(database=database_1, order=2)
    table_3 = data_fixture.create_database_table(database=database_1, order=3)

    response = api_client.post(
        reverse("api:database:tables:order", kwargs={"database_id": database_2.id}),
        {"table_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse("api:database:tables:order", kwargs={"database_id": 999999}),
        {"table_ids": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:tables:order", kwargs={"database_id": database_1.id}),
        {"table_ids": [0]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TABLE_NOT_IN_DATABASE"

    response = api_client.post(
        reverse("api:database:tables:order", kwargs={"database_id": database_1.id}),
        {"table_ids": ["test"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:database:tables:order", kwargs={"database_id": database_1.id}),
        {"table_ids": [table_3.id, table_2.id, table_1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    table_1.refresh_from_db()
    table_2.refresh_from_db()
    table_3.refresh_from_db()
    assert table_1.order == 3
    assert table_2.order == 2
    assert table_3.order == 1


@pytest.mark.django_db
def test_delete_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    assert Table.objects.all().count() == 2
    url = reverse("api:database:tables:item", kwargs={"table_id": table_1.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 204
    assert Table.objects.all().count() == 1

    url = reverse("api:database:tables:item", kwargs={"table_id": table_2.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tables:item", kwargs={"table_id": 9999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_database_application_with_tables(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table_1 = data_fixture.create_database_table(database=database, order=0)
    table_2 = data_fixture.create_database_table(database=database, order=1)
    data_fixture.create_database_table()

    url = reverse("api:applications:item", kwargs={"application_id": database.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["tables"]) == 2
    assert response_json["tables"][0]["id"] == table_1.id
    assert response_json["tables"][1]["id"] == table_2.id


@pytest.mark.django_db(transaction=True)
def test_update_table_works_if_locked_for_key_share(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    new_name = "Test 1"
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR KEY SHARE "
            )
            response = api_client.patch(
                reverse("api:database:tables:item", kwargs={"table_id": table.id}),
                {"name": new_name},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == new_name


@pytest.mark.django_db(transaction=True)
def test_delete_table_still_if_locked_for_key_share(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR KEY SHARE"
            )
            response = api_client.delete(
                reverse("api:database:tables:item", kwargs={"table_id": table.id}),
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db(transaction=True)
def test_async_duplicate_interesting_table(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user_1)
    _, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test2"
    )
    _, token_3 = data_fixture.create_user_and_token(
        email="test_3@test.nl",
        password="password",
        first_name="Test3",
        workspace=workspace_1,
    )

    database = data_fixture.create_database_application(workspace=workspace_1)
    table_1, _, _, _, context = setup_interesting_test_table(
        data_fixture, database=database, user=user_1
    )

    # user_2 cannot duplicate a table of other workspaces
    response = api_client.post(
        reverse("api:database:tables:async_duplicate", kwargs={"table_id": table_1.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # cannot duplicate non-existent application
    response = api_client.post(
        reverse("api:database:tables:async_duplicate", kwargs={"table_id": 99999}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    # user can duplicate an application created by other in the same workspace
    response = api_client.post(
        reverse("api:database:tables:async_duplicate", kwargs={"table_id": table_1.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "duplicate_table"

    # check that now the job ended correctly and the application was duplicated
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "duplicate_table"
    assert job["original_table"]["id"] == table_1.id
    assert job["original_table"]["name"] == table_1.name
    assert job["duplicated_table"]["id"] != table_1.id
    assert job["duplicated_table"]["name"] == f"{table_1.name} 2"

    # check that old tables rows are still accessible
    rows_url = reverse("api:database:rows:list", kwargs={"table_id": table_1.id})
    response = api_client.get(
        f"{rows_url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) > 0
    original_rows = response_json["results"]

    # check the new rows have the same values of the old
    duplicated_table_id = job["duplicated_table"]["id"]
    rows_url = reverse(
        "api:database:rows:list", kwargs={"table_id": duplicated_table_id}
    )
    response = api_client.get(
        f"{rows_url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) > 0
    duplicated_rows = response_json["results"]

    for original_row, duplicated_row in zip(original_rows, duplicated_rows):
        assert_serialized_rows_contain_same_values(original_row, duplicated_row)


@pytest.mark.django_db
def test_import_table_call(api_client, data_fixture):
    """
    A simple test to check import table validation
    """

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, user=user)
    data_fixture.create_number_field(table=table, user=user)

    url = reverse("api:database:tables:import_async", kwargs={"table_id": table.id})

    valid_data_no_configuration = {"data": [["1", 1], ["2", 1]]}

    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data=valid_data_no_configuration,
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    rdata = response.json()

    assert isinstance(rdata.get("id"), int)
    assert rdata.get("type") == "file_import"
    Job.objects.all().delete()

    valid_data_with_configuration = {"data": [["1", 1], ["2", 1]], "configuration": {}}
    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data=valid_data_with_configuration,
        format="json",
    )
    rdata = response.json()

    assert response.status_code == HTTP_200_OK
    assert isinstance(rdata.get("id"), int)
    assert rdata.get("type") == "file_import"
    Job.objects.all().delete()

    invalid_data_with_configuration = {
        "data": [["1", 1], ["2", 1]],
        "configuration": {"upsert_fields": []},
    }
    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data=invalid_data_with_configuration,
        format="json",
    )
    rdata = response.json()

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert rdata == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "configuration": {
                "upsert_fields": [
                    {
                        "error": "Ensure this field has at least 1 elements.",
                        "code": "min_length",
                    }
                ]
            }
        },
    }
    Job.objects.all().delete()

    invalid_data = {}
    response = api_client.post(
        url, HTTP_AUTHORIZATION=f"JWT {token}", data=invalid_data
    )
    rdata = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert rdata == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {"data": [{"error": "This field is required.", "code": "required"}]},
    }

    invalid_data = {
        "data": [["1", 1], ["2", 1]],
        "configuration": {"upsert_fields": [1, 2]},
    }
    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data=invalid_data,
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    rdata = response.json()

    assert rdata == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "configuration": {
                "upsert_value": [
                    {
                        "error": "upsert_values must not be empty when upsert_fields are provided.",
                        "code": "invalid",
                    }
                ]
            }
        },
    }

    invalid_data = {
        "data": [["1", 1], ["2", 1]],
        "configuration": {"upsert_fields": [1, 2], "upsert_values": [["a"]]},
    }
    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data=invalid_data,
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    rdata = response.json()

    assert rdata == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "data": [
                {
                    "error": "`data` and `configuration.upsert_values` should have the same length.",
                    "code": "invalid",
                }
            ],
            "configuration": {
                "upsert_values": {
                    "error": "`data` and `configuration.upsert_values` should have the same length.",
                    "code": "invalid",
                }
            },
        },
    }
