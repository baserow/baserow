import json
import zipfile

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage
from baserow.core.user_files.models import UserFile
from baserow.test_utils.helpers import setup_interesting_test_database


@pytest.mark.export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_interesting_database(
    data_fixture, api_client, tmpdir, settings, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database_name = "To be exported"

    cli_import_export_config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=False
    )

    database = setup_interesting_test_database(
        data_fixture,
        user=user,
        workspace=workspace,
        name=database_name,
    )

    storage = get_default_storage()
    for user_file in UserFile.objects.all():
        data_fixture.save_content_in_user_file(user_file=user_file, storage=storage)

    file_name = ImportExportHandler().export_workspace_applications(
        applications=[database],
        import_export_config=cli_import_export_config,
        storage=storage,
        progress_builder=None,
    )

    file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, file_name)
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert "data/workspace_export.json" in zip_ref.namelist()

        with zip_ref.open("data/workspace_export.json") as json_file:
            json_data = json.load(json_file)
            assert len(json_data) == 1
            assert json_data[0]["name"] == database.name


@pytest.mark.export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_workspace_writes_file_to_storage(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #2",
        },
    )

    run_time = "2024-10-14T08:00:00Z"
    with freeze_time(run_time):
        token = data_fixture.generate_token(user)
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:workspaces:export_workspace_async",
                    kwargs={"workspace_id": table.database.workspace.id},
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
        "exported_file_name": "",
        "human_readable_error": "",
        "id": job_id,
        "progress_percentage": 0,
        "state": "pending",
        "type": "export_applications",
        "url": None,
        "workspace_id": table.database.workspace.id,
    }

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    file_name = response_json["exported_file_name"]

    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100
    assert (
        response_json["url"] == f"http://localhost:8000/media/export_files/{file_name}"
    )

    file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, file_name)
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert "data/workspace_export.json" in zip_ref.namelist()

        with zip_ref.open("data/workspace_export.json") as json_file:
            json_data = json.load(json_file)
            assert len(json_data) == 1
            assert json_data[0]["name"] == table.database.name

            assert len(json_data[0]["tables"]) == 1
            table = json_data[0]["tables"][0]
            assert len(table["fields"]) == 1
            assert table["fields"][0]["name"] == text_field.name
            assert len(table["rows"]) == 2
            assert table["rows"][0][f"field_{text_field.id}"] == "row #1"
            assert table["rows"][1][f"field_{text_field.id}"] == "row #2"
