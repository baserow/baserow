from datetime import timezone
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.dateparse import parse_datetime

import pytest
from freezegun import freeze_time
from rest_framework.fields import DateTimeField
from rest_framework.status import HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_exporting_json_writes_file_to_storage(
    premium_data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=0
    )
    option_field = premium_data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    option_a = premium_data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
        date_format="US",
        name="date_field",
        order=2,
    )

    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="test"
    )
    premium_data_fixture.create_view_sort(view=grid_view, field=text_field, order="ASC")

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "test",
            date_field.id: "2020-02-01 01:23",
            option_field.id: option_b.id,
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "atest",
            date_field.id: "2020-02-01 01:23",
            option_field.id: option_a.id,
        },
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage
        run_time = parse_datetime("2020-02-01 01:00").replace(tzinfo=timezone.utc)
        expected_created_at = DateTimeField().to_representation(run_time)
        with freeze_time(run_time):
            token = premium_data_fixture.generate_token(user)
            with django_capture_on_commit_callbacks(execute=True):
                response = api_client.post(
                    reverse(
                        "api:database:export:export_table",
                        kwargs={"table_id": table.id},
                    ),
                    data={
                        "view_id": grid_view.id,
                        "exporter_type": "json",
                        "json_charset": "utf-8",
                    },
                    format="json",
                    HTTP_AUTHORIZATION=f"JWT {token}",
                )
            response_json = response.json()
            assert "id" in response_json
            job_id = response_json["id"]
            assert response_json == {
                "id": job_id,
                "created_at": expected_created_at,
                "exported_file_name": None,
                "exporter_type": "json",
                "progress_percentage": 0.0,
                "state": "pending",
                "status": "pending",
                "table": table.id,
                "view": grid_view.id,
                "url": None,
            }
            response = api_client.get(
                reverse("api:database:export:get", kwargs={"job_id": job_id}),
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            response_json = response.json()
            assert "exported_file_name" in response_json
            filename = response_json["exported_file_name"]
            assert response_json == {
                "id": job_id,
                "created_at": expected_created_at,
                "exported_file_name": filename,
                "exporter_type": "json",
                "progress_percentage": 100.0,
                "state": "finished",
                "status": "finished",
                "table": table.id,
                "view": grid_view.id,
                "url": f"http://localhost:8000/media/export_files/{filename}",
            }

            file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
            assert file_path.isfile()
            expected = """[
{
    "id": 2,
    "text_field": "atest",
    "option_field": "A",
    "date_field": "02/01/2020 01:23"
},
{
    "id": 1,
    "text_field": "test",
    "option_field": "B",
    "date_field": "02/01/2020 01:23"
}
]
"""
            with open(file_path, "r", encoding="utf-8") as written_file:
                real = written_file.read()
                assert real == expected

            premium_data_fixture.remove_all_active_premium_licenses(user)
            response = api_client.post(
                reverse(
                    "api:database:export:export_table",
                    kwargs={"table_id": table.id},
                ),
                data={
                    "view_id": grid_view.id,
                    "exporter_type": "json",
                    "json_charset": "utf-8",
                },
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            assert response.status_code == HTTP_402_PAYMENT_REQUIRED
            assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_exporting_xml_writes_file_to_storage(
    premium_data_fixture,
    api_client,
    tmpdir,
    settings,
    django_capture_on_commit_callbacks,
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=0
    )
    option_field = premium_data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    option_a = premium_data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = premium_data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
        date_format="US",
        name="date_field",
        order=2,
    )

    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="test"
    )
    premium_data_fixture.create_view_sort(view=grid_view, field=text_field, order="ASC")

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "test",
            date_field.id: "2020-02-01 01:23",
            option_field.id: option_b.id,
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "atest",
            date_field.id: "2020-02-01 01:23",
            option_field.id: option_a.id,
        },
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage
        run_time = parse_datetime("2020-02-01 01:00").replace(tzinfo=timezone.utc)
        with freeze_time(run_time):
            token = premium_data_fixture.generate_token(user)
            expected_created_at = DateTimeField().to_representation(run_time)
            with django_capture_on_commit_callbacks(execute=True):
                response = api_client.post(
                    reverse(
                        "api:database:export:export_table",
                        kwargs={"table_id": table.id},
                    ),
                    data={
                        "view_id": grid_view.id,
                        "exporter_type": "xml",
                        "xml_charset": "utf-8",
                    },
                    format="json",
                    HTTP_AUTHORIZATION=f"JWT {token}",
                )
            response_json = response.json()
            assert "id" in response_json
            job_id = response_json["id"]
            assert response_json == {
                "id": job_id,
                "created_at": expected_created_at,
                "exported_file_name": None,
                "exporter_type": "xml",
                "progress_percentage": 0.0,
                "state": "pending",
                "status": "pending",
                "table": table.id,
                "view": grid_view.id,
                "url": None,
            }
            response = api_client.get(
                reverse("api:database:export:get", kwargs={"job_id": job_id}),
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            response_json = response.json()
            assert "exported_file_name" in response_json
            filename = response_json["exported_file_name"]
            assert response_json == {
                "id": job_id,
                "created_at": expected_created_at,
                "exported_file_name": filename,
                "exporter_type": "xml",
                "progress_percentage": 100.0,
                "state": "finished",
                "status": "finished",
                "table": table.id,
                "view": grid_view.id,
                "url": f"http://localhost:8000/media/export_files/{filename}",
            }

            file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
            assert file_path.isfile()
            expected = """<?xml version="1.0" encoding="utf-8" ?>
<rows>
<row>
    <id>2</id>
    <text-field>atest</text-field>
    <option-field>A</option-field>
    <date-field>02/01/2020 01:23</date-field>
</row>
<row>
    <id>1</id>
    <text-field>test</text-field>
    <option-field>B</option-field>
    <date-field>02/01/2020 01:23</date-field>
</row>
</rows>
"""
            with open(file_path, "r", encoding="utf-8") as written_file:
                xml = written_file.read()
                assert strip_indents_and_newlines(xml) == strip_indents_and_newlines(
                    expected
                )

            premium_data_fixture.remove_all_active_premium_licenses(user)
            response = api_client.post(
                reverse(
                    "api:database:export:export_table",
                    kwargs={"table_id": table.id},
                ),
                data={
                    "view_id": grid_view.id,
                    "exporter_type": "xml",
                    "xml_charset": "utf-8",
                },
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            assert response.status_code == HTTP_402_PAYMENT_REQUIRED
            assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


def strip_indents_and_newlines(xml):
    return "".join([line.strip() for line in xml.split("\n")])
