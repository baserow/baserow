import json
import zipfile

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.import_export.handler import EXPORT_FORMAT_VERSION, MANIFEST_NAME
from baserow.version import VERSION


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_exporting_missing_workspace_returns_error(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    response = api_client.post(
        reverse(
            "api:workspaces:export_workspace_async",
            kwargs={"workspace_id": 999999},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_exporting_workspace_with_no_permissions_returns_error(
    data_fixture, api_client, tmpdir
):
    user, token = data_fixture.create_user_and_token()
    _, token2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    response = api_client.post(
        reverse(
            "api:workspaces:export_workspace_async",
            kwargs={"workspace_id": workspace.id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_exporting_workspace_with_application_without_permissions_returns_error(
    data_fixture, api_client, tmpdir
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    user2, token2 = data_fixture.create_user_and_token()
    workspace2 = data_fixture.create_workspace(user=user2)
    database2 = data_fixture.create_database_application(workspace=workspace2)

    response = api_client.post(
        reverse(
            "api:workspaces:export_workspace_async",
            kwargs={"workspace_id": workspace.id},
        ),
        data={"application_ids": [database.id, database2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_empty_workspace(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    run_time = "2024-10-14T08:00:00Z"
    with django_capture_on_commit_callbacks(execute=True), freeze_time(run_time):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": workspace.id},
            ),
            data={
                "application_ids": [],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()

    job_id = response_json["id"]
    assert response_json == {
        "created_on": run_time,
        "updated_on": run_time,
        "exported_file_name": None,
        "human_readable_error": "",
        "id": job_id,
        "progress_percentage": 0,
        "state": "pending",
        "type": "export_applications",
        "url": None,
        "workspace_id": workspace.id,
    }

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    file_name = response_json["exported_file_name"].replace("export_", "")

    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100

    assert (
        response_json["url"] == f"http://localhost:8000/media/export_files/{file_name}"
    )

    file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, file_name)
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert MANIFEST_NAME in zip_ref.namelist()

        with zip_ref.open(MANIFEST_NAME) as json_file:
            json_data = json.load(json_file)
            assert json_data == {
                "version": EXPORT_FORMAT_VERSION,
                "baserow_version": VERSION,
                "checksums": {},
                "applications": {},
                "configuration": {"only_structure": False},
                "total_files": 2,
            }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_workspace_with_single_empty_database(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    database_name = "To be exported"
    database = data_fixture.create_database_application(user=user, name=database_name)

    run_time = "2024-10-14T08:00:00Z"
    with django_capture_on_commit_callbacks(execute=True), freeze_time(run_time):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": database.workspace.id},
            ),
            data={
                "application_ids": [],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()

    job_id = response_json["id"]
    assert response_json == {
        "created_on": run_time,
        "updated_on": run_time,
        "exported_file_name": None,
        "human_readable_error": "",
        "id": job_id,
        "progress_percentage": 0,
        "state": "pending",
        "type": "export_applications",
        "url": None,
        "workspace_id": database.workspace.id,
    }

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    file_name = response_json["exported_file_name"].replace("export_", "")

    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100
    assert (
        response_json["url"] == f"http://localhost:8000/media/export_files/{file_name}"
    )

    file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, file_name)
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert MANIFEST_NAME in zip_ref.namelist()

        with zip_ref.open(MANIFEST_NAME) as json_file:
            json_data = json.load(json_file)
            assert json_data["version"] == EXPORT_FORMAT_VERSION
            assert json_data["baserow_version"] == VERSION
            assert json_data["configuration"] == {"only_structure": False}
            assert len(json_data["applications"]["database"]["items"]) == 1
            assert (
                json_data["applications"]["database"]["version"]
                == EXPORT_FORMAT_VERSION
            )
            assert json_data["applications"]["database"]["configuration"] == {}
            exported_database = json_data["applications"]["database"]["items"][0]
            assert exported_database["id"] == database.id
            assert exported_database["type"] == "database"
            assert exported_database["name"] == database_name
            assert exported_database["files"]["schema"] is not None
            assert exported_database["files"]["schema"] in json_data["checksums"]


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_list_exports_with_missing_workspace(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    response = api_client.get(
        reverse(
            "api:workspaces:export_workspace_list",
            kwargs={"workspace_id": 999999},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_list_exports_for_invalid_user(
    data_fixture,
    api_client,
    tmpdir,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    user2 = data_fixture.create_user()

    run_time = "2024-10-14T08:00:00Z"
    with django_capture_on_commit_callbacks(execute=True), freeze_time(run_time):
        token = data_fixture.generate_token(user)
        api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": database.workspace.id},
            ),
            data={
                "application_ids": [],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    token2 = data_fixture.generate_token(user2)
    response = api_client.get(
        reverse(
            "api:workspaces:export_workspace_list",
            kwargs={"workspace_id": database.workspace.id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_list_exports_for_valid_user(
    data_fixture,
    api_client,
    tmpdir,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    run_time = "2024-10-14T08:00:00Z"
    with django_capture_on_commit_callbacks(execute=True), freeze_time(run_time):
        token = data_fixture.generate_token(user)
        api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": database.workspace.id},
            ),
            data={
                "application_ids": [],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:workspaces:export_workspace_list",
            kwargs={"workspace_id": database.workspace.id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "results" in response_json
    assert len(response_json["results"]) == 1

    export = response_json["results"][0]
    file_name = export["exported_file_name"].replace("export_", "")

    assert export["state"] == "finished"
    assert export["progress_percentage"] == 100
    assert export["url"] == f"http://localhost:8000/media/export_files/{file_name}"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_export_specific_application_ids_filters_correctly(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database1 = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    database2 = data_fixture.create_database_application(
        workspace=workspace, name="Database 2"
    )

    data_fixture.create_database_table(database=database1, name="Table 1")
    data_fixture.create_database_table(database=database2, name="Table 2")

    run_time = "2024-10-14T08:00:00Z"
    with django_capture_on_commit_callbacks(execute=True), freeze_time(run_time):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": workspace.id},
            ),
            data={
                "application_ids": [database1.id],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_202_ACCEPTED
    job_id = response.json()["id"]

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100

    file_name = response_json["exported_file_name"].replace("export_", "")
    file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, file_name)
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert MANIFEST_NAME in zip_ref.namelist()

        with zip_ref.open(MANIFEST_NAME) as json_file:
            manifest_data = json.load(json_file)

            applications = manifest_data["applications"]
            assert "database" in applications
            database_items = applications["database"]["items"]
            assert len(database_items) == 1

            exported_db = database_items[0]
            assert exported_db["name"] == "Database 1"
            assert exported_db["name"] != "Database 2"

            db_schema_path = exported_db["files"]["schema"]
            with zip_ref.open(db_schema_path) as db_file:
                db_data = json.load(db_file)
                assert db_data["name"] == "Database 1"
                assert len(db_data["tables"]) == 1
                assert db_data["tables"][0]["name"] == "Table 1"
