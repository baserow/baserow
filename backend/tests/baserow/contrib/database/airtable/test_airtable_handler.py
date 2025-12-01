import json
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage

import pytest
import responses
from rest_framework import serializers

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.exceptions import (
    AirtableBaseRequiresAuthentication,
    AirtableShareIsNotABase,
)
from baserow.contrib.database.airtable.handler import (
    AirtableFileImport,
    AirtableHandler,
)
from baserow.contrib.database.airtable.job_types import AirtableImportJobType
from baserow.contrib.database.airtable.models import AirtableImportJob
from baserow.contrib.database.fields.models import TextField
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import JOB_PENDING
from baserow.core.jobs.exceptions import JobDoesNotExist, MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.user_files.models import UserFile
from baserow.core.utils import Progress


@pytest.mark.django_db
@responses.activate
def test_fetch_publicly_shared_base():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    path = os.path.join(base_path, "airtable_base.html")

    with open(path, "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler,
            headers={"Set-Cookie": "brw=test;"},
        )

        request_id, init_data, cookies = AirtableHandler.fetch_publicly_shared_base(
            "appZkaH3aWX3ZjT3b",
            AirtableImportConfig(),
        )
        assert request_id == "req8wbZoh7Be65osz"
        assert init_data["pageLoadId"] == "pglUrFAGTNpbxUymM"
        assert cookies["brw"] == "test"


@pytest.mark.django_db
@responses.activate
def test_fetch_publicly_shared_base_not_base_request_id_missing():
    share_id = "appZkaH3aWX3ZjT3b"
    responses.add(
        responses.GET,
        f"https://airtable.com/{share_id}",
        status=200,
        body="not a base",
        headers={"Set-Cookie": "brw=test;"},
    )

    with pytest.raises(AirtableShareIsNotABase):
        AirtableHandler.fetch_publicly_shared_base(
            share_id,
            AirtableImportConfig(),
        )


@pytest.mark.django_db
@responses.activate
def test_fetch_publicly_shared_base_with_authentication():
    responses.add(
        responses.GET,
        "https://airtable.com/appZkaH3aWX3ZjT3b",
        status=302,
        body="Sign in",
        headers={"Location": "/login?test"},
    )
    with pytest.raises(AirtableBaseRequiresAuthentication):
        AirtableHandler.fetch_publicly_shared_base(
            "appZkaH3aWX3ZjT3b",
            AirtableImportConfig(),
        )


@pytest.mark.django_db
@responses.activate
def test_fetch_table():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    path = os.path.join(base_path, "airtable_base.html")
    application_response_path = os.path.join(base_path, "airtable_application.json")
    table_response_path = os.path.join(base_path, "airtable_table.json")

    with open(path, "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler,
            headers={"Set-Cookie": "brw=test;"},
        )
        request_id, init_data, cookies = AirtableHandler.fetch_publicly_shared_base(
            "appZkaH3aWX3ZjT3b",
            AirtableImportConfig(),
        )

    cookies = {
        "brw": "brw",
        "__Host-airtable-session": "__Host-airtable-session",
        "__Host-airtable-session.sig": "__Host-airtable-session.sig",
        "AWSELB": "AWSELB",
        "AWSELBCORS": "AWSELBCORS",
    }

    with open(application_response_path, "rb") as application_response_file:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=application_response_file,
        )
        application_response = AirtableHandler.fetch_table_data(
            "tblRpq315qnnIcg5IjI",
            init_data,
            request_id,
            cookies,
            fetch_application_structure=True,
            stream=False,
        )

    with open(table_response_path, "rb") as table_response_file:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=table_response_file,
        )
        table_response = AirtableHandler.fetch_table_data(
            "tbl7glLIGtH8C8zGCzb",
            init_data,
            request_id,
            cookies,
            fetch_application_structure=False,
            stream=False,
        )

    assert (
        application_response.json()["data"]["tableSchemas"][0]["id"]
        == "tblRpq315qnnIcg5IjI"
    )
    assert table_response.json()["data"]["id"] == "tbl7glLIGtH8C8zGCzb"


@pytest.mark.django_db
@responses.activate
def test_extract_schema():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    user_table_path = os.path.join(base_path, "airtable_application.json")
    data_table_path = os.path.join(base_path, "airtable_table.json")
    user_table_json = json.loads(Path(user_table_path).read_text())
    data_table_json = json.loads(Path(data_table_path).read_text())

    schema, tables = AirtableHandler.extract_schema([user_table_json, data_table_json])

    assert "tableDatas" not in schema
    assert len(schema["tableSchemas"]) == 2
    assert schema["tableSchemas"][0]["id"] == "tblRpq315qnnIcg5IjI"
    assert schema["tableSchemas"][1]["id"] == "tbl7glLIGtH8C8zGCzb"
    assert tables["tblRpq315qnnIcg5IjI"]["id"] == "tblRpq315qnnIcg5IjI"
    assert tables["tbl7glLIGtH8C8zGCzb"]["id"] == "tbl7glLIGtH8C8zGCzb"


@pytest.mark.django_db
@responses.activate
def test_to_baserow_database_export():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/025730a04991a764bb3ace6d524b45e5/bd61798a/file_example_JPG_100kB.jpg",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    (
        init_data,
        request_id,
        cookies,
        schema,
        tables,
    ) = AirtableHandler.fetch_and_combine_airtable_data(
        "appZkaH3aWX3ZjT3b", AirtableImportConfig()
    )
    baserow_database_export, files_buffer = AirtableHandler.to_baserow_database_export(
        init_data, request_id, cookies, schema, tables, AirtableImportConfig()
    )

    assert isinstance(files_buffer, AirtableFileImport)
    assert len(files_buffer.files_to_download) == 3
    with files_buffer.open(
        "70e50b90fb83997d25e64937979b6b5b_f3f62d23_file-sample.txt"
    ) as file_handler:
        assert file_handler.read() == b"test\n"

    assert baserow_database_export["id"] == 1
    assert baserow_database_export["name"] == "Test"
    assert baserow_database_export["order"] == 1
    assert baserow_database_export["type"] == "database"
    assert len(baserow_database_export["tables"]) == 3  # 2 + import report table

    assert baserow_database_export["tables"][0]["id"] == "tblRpq315qnnIcg5IjI"
    assert baserow_database_export["tables"][0]["name"] == "Users"
    assert baserow_database_export["tables"][0]["order"] == 0
    assert len(baserow_database_export["tables"][0]["fields"]) == 4

    assert baserow_database_export["tables"][1]["id"] == "tbl7glLIGtH8C8zGCzb"
    assert baserow_database_export["tables"][1]["name"] == "Data"
    assert baserow_database_export["tables"][1]["order"] == 1
    assert len(baserow_database_export["tables"][1]["fields"]) == 26

    # We don't have to check all the fields and rows, just a single one, because we have
    # separate tests for mapping the Airtable fields and values to Baserow.
    assert (
        baserow_database_export["tables"][0]["fields"][0]["id"] == "fldG9y88Zw7q7u4Z7i4"
    )
    assert baserow_database_export["tables"][0]["fields"][0] == {
        "type": "text",
        "id": "fldG9y88Zw7q7u4Z7i4",
        "name": "Name",
        "description": None,
        "order": 0,
        "primary": True,
        "text_default": "",
        "read_only": False,
        "immutable_type": False,
        "immutable_properties": False,
        "db_index": False,
        "field_constraints": [],
    }
    assert baserow_database_export["tables"][0]["fields"][1] == {
        "type": "email",
        "id": "fldB7wkyR0buF1sRF9O",
        "name": "Email",
        "description": "This is an email",
        "order": 1,
        "primary": False,
        "read_only": False,
        "immutable_type": False,
        "immutable_properties": False,
        "db_index": False,
        "field_constraints": [],
    }
    assert len(baserow_database_export["tables"][0]["rows"]) == 3
    assert baserow_database_export["tables"][0]["rows"][0] == {
        "id": 1,
        "order": "1.00000000000000000000",
        "created_on": "2022-01-16T17:59:13+00:00",
        "updated_on": None,
        "field_fldB7wkyR0buF1sRF9O": "bram@email.com",
        "field_fldG9y88Zw7q7u4Z7i4": "Bram 1",
        "field_fldFh5wIL430N62LN6t": [1],
        "field_fldZBmr4L45mhjILhlA": "1",
    }
    assert baserow_database_export["tables"][0]["rows"][1] == {
        "id": 2,
        "order": "2.00000000000000000000",
        "created_on": "2022-01-16T17:59:13+00:00",
        "updated_on": None,
        "field_fldB7wkyR0buF1sRF9O": "bram@test.nl",
        "field_fldG9y88Zw7q7u4Z7i4": "Bram 2",
        "field_fldFh5wIL430N62LN6t": [2, 3, 1],
        "field_fldZBmr4L45mhjILhlA": "2",
    }
    assert baserow_database_export["tables"][0]["rows"][2] == {
        "id": 3,
        "order": "3.00000000000000000000",
        "created_on": "2022-01-17T17:59:13+00:00",
        "updated_on": None,
    }
    assert (
        baserow_database_export["tables"][1]["rows"][0]["field_fldEB5dp0mNjVZu0VJI"]
        == "2022-01-21T00:00:00+00:00"
    )
    assert baserow_database_export["tables"][0]["views"] == [
        {
            "id": "viwFSKLuVm97DnNVD91",
            "type": "grid",
            "name": "All",
            "order": 1,
            "row_identifier_type": "count",
            "row_height_size": "small",
            "filter_type": "AND",
            "filters_disabled": False,
            "filters": [],
            "filter_groups": [],
            "sortings": [],
            "decorations": [],
            "group_bys": [],
            "ownership_type": "collaborative",
            "public": False,
            "field_options": [
                {
                    "aggregation_raw_type": "",
                    "aggregation_type": "",
                    "field_id": "fldG9y88Zw7q7u4Z7i4",
                    "hidden": False,
                    "id": "viwFSKLuVm97DnNVD91_columnOrder_0",
                    "order": 1,
                    "width": 200,
                },
                {
                    "aggregation_raw_type": "",
                    "aggregation_type": "",
                    "field_id": "fldB7wkyR0buF1sRF9O",
                    "hidden": False,
                    "id": "viwFSKLuVm97DnNVD91_columnOrder_1",
                    "order": 2,
                    "width": 200,
                },
                {
                    "aggregation_raw_type": "",
                    "aggregation_type": "",
                    "field_id": "fldFh5wIL430N62LN6t",
                    "hidden": False,
                    "id": "viwFSKLuVm97DnNVD91_columnOrder_2",
                    "order": 3,
                    "width": 200,
                },
                {
                    "aggregation_raw_type": "",
                    "aggregation_type": "",
                    "field_id": "fldZBmr4L45mhjILhlA",
                    "hidden": False,
                    "id": "viwFSKLuVm97DnNVD91_columnOrder_3",
                    "order": 4,
                    "width": 200,
                },
            ],
            "owned_by": None,
        }
    ]

    assert baserow_database_export["tables"][2]["rows"][0] == {
        "id": 1,
        "order": "1.00000000000000000000",
        "created_on": None,
        "updated_on": None,
        "field_object_name": "Name lookup (from Users)",
        "field_scope": "scope_field",
        "field_table": "table_Data",
        "field_error_type": "error_type_unsupported_feature",
        "field_message": 'Field "Name lookup (from Users)" with field type lookup was not imported because it is not supported.',
    }


@pytest.mark.django_db
@responses.activate
def test_download_files_via_endpoint():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recAAA5JwFXBk4swkfB/downloadAttachment",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        body = file_handler.read()
        # Rename the `signedUserContentUrls`, so that it's not provided during the
        # import. It would then use the fetch attachment endpoint instead.
        body = body.replace(b"signedUserContentUrls", b"signedUserContentUrls_UNKNOWN")
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=body,
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        body = file_handler.read()
        # Rename the `signedUserContentUrls`, so that it's not provided during the
        # import. It would then use the fetch attachment endpoint instead.
        body = body.replace(b"signedUserContentUrls", b"signedUserContentUrls_UNKNOWN")
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=body,
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    (
        init_data,
        request_id,
        cookies,
        schema,
        tables,
    ) = AirtableHandler.fetch_and_combine_airtable_data(
        "appZkaH3aWX3ZjT3b", AirtableImportConfig()
    )
    baserow_database_export, files_buffer = AirtableHandler.to_baserow_database_export(
        init_data, request_id, cookies, schema, tables, AirtableImportConfig()
    )

    assert isinstance(files_buffer, AirtableFileImport)
    assert len(files_buffer.files_to_download) == 3
    with files_buffer.open(
        "70e50b90fb83997d25e64937979b6b5b_f3f62d23_file-sample.txt"
    ) as file_handler:
        assert file_handler.read() == b"test\n"


@pytest.mark.django_db
@responses.activate
def test_config_skip_files(tmpdir, data_fixture):
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/025730a04991a764bb3ace6d524b45e5/bd61798a/file_example_JPG_100kB.jpg",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    (
        init_data,
        request_id,
        cookies,
        schema,
        tables,
    ) = AirtableHandler.fetch_and_combine_airtable_data(
        "appZkaH3aWX3ZjT3b", AirtableImportConfig()
    )
    baserow_database_export, files_buffer = AirtableHandler.to_baserow_database_export(
        init_data,
        request_id,
        cookies,
        schema,
        tables,
        AirtableImportConfig(skip_files=True),
    )

    assert isinstance(files_buffer, AirtableFileImport)
    assert len(files_buffer.files_to_download) == 0


@pytest.mark.django_db
@responses.activate
def test_to_baserow_database_export_without_primary_value():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/025730a04991a764bb3ace6d524b45e5/bd61798a/file_example_JPG_100kB.jpg",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    (
        init_data,
        request_id,
        cookies,
        schema,
        tables,
    ) = AirtableHandler.fetch_and_combine_airtable_data(
        "appZkaH3aWX3ZjT3b", AirtableImportConfig()
    )

    # Rename the primary column so that we depend on the fallback in the migrations.
    schema["tableSchemas"][0]["primaryColumnId"] = "fldG9y88Zw7q7u4Z7i4_unknown"

    baserow_database_export, files_buffer = AirtableHandler.to_baserow_database_export(
        init_data,
        request_id,
        cookies,
        schema,
        tables,
        AirtableImportConfig(skip_files=True),
    )
    assert baserow_database_export["tables"][0]["fields"][0]["primary"] is True
    assert baserow_database_export["tables"][2]["rows"][0] == {
        "id": 1,
        "order": "1.00000000000000000000",
        "created_on": None,
        "updated_on": None,
        "field_object_name": "Name",
        "field_scope": "scope_field",
        "field_table": "table_Users",
        "field_error_type": "error_type_unsupported_feature",
        "field_message": 'Changed primary field to "Name" because the original primary field is incompatible.',
    }

    schema["tableSchemas"][0]["columns"] = []
    baserow_database_export, files_buffer = AirtableHandler.to_baserow_database_export(
        init_data,
        request_id,
        cookies,
        schema,
        tables,
        AirtableImportConfig(skip_files=True),
    )
    assert baserow_database_export["tables"][0]["fields"] == [
        {
            "type": "text",
            "id": "primary_field",
            "name": "Primary field (auto created)",
            "description": None,
            "order": 32767,
            "primary": True,
            "text_default": "",
            "read_only": False,
            "immutable_type": False,
            "immutable_properties": False,
            "db_index": False,
            "field_constraints": [],
        }
    ]
    assert baserow_database_export["tables"][2]["rows"][0] == {
        "id": 1,
        "order": "1.00000000000000000000",
        "created_on": None,
        "updated_on": None,
        "field_object_name": "Primary field (auto created)",
        "field_scope": "scope_field",
        "field_table": "table_Users",
        "field_error_type": "error_type_unsupported_feature",
        "field_message": 'Created new primary field "Primary field (auto created)" because none of the provided fields are compatible.',
    }


@pytest.mark.django_db
@responses.activate
def test_import_from_airtable_to_workspace(
    data_fixture, tmpdir, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/025730a04991a764bb3ace6d524b45e5/bd61798a/file_example_JPG_100kB.jpg",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    progress = Progress(1000)

    database = AirtableHandler.import_from_airtable_to_workspace(
        workspace,
        "appZkaH3aWX3ZjT3b",
        storage=storage,
        progress_builder=progress.create_child_builder(represents_progress=1000),
    )

    assert progress.progress == progress.total
    assert UserFile.objects.all().count() == 3
    file_path = tmpdir.join("user_files", UserFile.objects.all()[0].name)
    assert file_path.isfile()
    assert file_path.open().read() == "test\n"

    assert database.name == "Test"
    all_tables = database.table_set.all()
    assert len(all_tables) == 3  # 2 + import report

    assert all_tables[0].name == "Users"
    assert all_tables[1].name == "Data"
    assert all_tables[2].name == "Airtable import report"

    table_0_views = all_tables[0].view_set.all()
    assert table_0_views[0].name == "All"
    table_1_views = all_tables[1].view_set.all()
    assert table_1_views[0].name == "Grid view"
    assert table_1_views[1].name == "With filters and sorts"
    table_1_view_1_sorts = table_1_views[1].viewsort_set.all()
    assert len(table_1_view_1_sorts) == 2
    table_1_view_1_group_bys = table_1_views[1].viewgroupby_set.all()
    assert len(table_1_view_1_group_bys) == 1

    user_fields = all_tables[0].field_set.all()
    assert len(user_fields) == 4

    assert user_fields[0].name == "Name"
    assert isinstance(user_fields[0].specific, TextField)

    user_model = all_tables[0].get_model(attribute_names=True)
    row_0, row_1, _ = user_model.objects.all()
    assert row_0.id == 1
    assert str(row_0.order) == "1.00000000000000000000"
    assert row_0.name == "Bram 1"
    assert row_0.email == "bram@email.com"
    assert str(row_0.number) == "1"
    assert [r.id for r in row_0.data.all()] == [1]

    data_model = all_tables[1].get_model(attribute_names=True)
    row_0, row_1, *_ = data_model.objects.all()
    assert row_0.checkbox is True
    assert row_1.checkbox is False


@pytest.mark.django_db
@responses.activate
def test_import_from_airtable_to_workspace_with_report_table(data_fixture, tmpdir):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/e93dc201ce27080d9ad9df5775527d09/93e85b28/file-sample_500kB.doc",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.attachments/025730a04991a764bb3ace6d524b45e5/bd61798a/file_example_JPG_100kB.jpg",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appZkaH3aWX3ZjT3b/read",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "airtable_table.json"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/table/tbl7glLIGtH8C8zGCzb/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwDgBCKTEdCQoHTQKH.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwDgBCKTEdCQoHTQKH/readData",
            status=200,
            body=file_handler.read(),
        )

    with open(
        os.path.join(base_path, "airtable_view_viwBAGnUgZ6X5Eyg5Wf.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwBAGnUgZ6X5Eyg5Wf/readData",
            status=200,
            body=file_handler.read(),
        )

    progress = Progress(1000)

    database = AirtableHandler.import_from_airtable_to_workspace(
        workspace,
        "appZkaH3aWX3ZjT3b",
        storage=storage,
        progress_builder=progress.create_child_builder(represents_progress=1000),
    )

    report_table = database.table_set.last()
    assert report_table.name == "Airtable import report"

    model = report_table.get_model(attribute_names=True)
    row = model.objects.last()
    assert row.object_name == "All interfaces"
    assert row.scope.value == "Interfaces"
    assert row.table is None
    assert row.error_type.value == "Unsupported feature"
    assert row.message == "Baserow doesn't support interfaces."


@pytest.mark.django_db
@responses.activate
def test_import_from_airtable_to_workspace_duplicated_single_select(
    data_fixture, tmpdir, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/single_select_duplicated"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/shra2B9gmVj6kxvNz",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appHI27Un8BKJ9iKA/read",
            status=200,
            body=file_handler.read(),
        )

    progress = Progress(1000)

    database = AirtableHandler.import_from_airtable_to_workspace(
        workspace,
        "shra2B9gmVj6kxvNz",
        storage=storage,
        progress_builder=progress.create_child_builder(represents_progress=1000),
    )

    table = database.table_set.all()[0]
    data = table.get_model(attribute_names=True)
    row1, row2, row3, row4 = data.objects.all()
    assert row1.so.value == "o1"
    assert row1.so_copy.value == "o11"

    assert row2.so.value == "o2"
    assert row2.so_copy.value == "o21"

    assert row3.so is None
    assert row3.so_copy.value == "o31"

    assert row4.so.value == "o4"
    assert row4.so_copy is None


@pytest.mark.django_db
@responses.activate
def test_import_from_airtable_to_workspace_duplicated_multi_select(
    data_fixture, tmpdir, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/multi_select_duplicated"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/shra2B9gmVj6kxvNz",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_application.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/application/appHI27Un8BKJ9iKA/read",
            status=200,
            body=file_handler.read(),
        )

    progress = Progress(1000)

    database = AirtableHandler.import_from_airtable_to_workspace(
        workspace,
        "shra2B9gmVj6kxvNz",
        storage=storage,
        progress_builder=progress.create_child_builder(represents_progress=1000),
    )

    table = database.table_set.all()[0]
    data = table.get_model(attribute_names=True)
    row1, row2, row3, row4 = data.objects.all()

    assert list(row1.mo.values_list("value", flat=True)) == ["mo1"]
    assert list(row1.mo_copy.values_list("value", flat=True)) == ["mo11"]

    assert list(row2.mo.values_list("value", flat=True)) == ["mo1", "mo3"]
    assert list(row2.mo_copy.values_list("value", flat=True)) == ["mo11", "mo33"]

    assert row3.mo.count() == 0
    assert row3.mo_copy.count() == 0

    assert list(row4.mo.values_list("value", flat=True)) == ["mo2"]
    assert list(row4.mo_copy.values_list("value", flat=True)) == [
        "mo22",
        "mo33",
        "mo11",
    ]


@pytest.mark.django_db
@responses.activate
def test_import_unsupported_publicly_shared_view(data_fixture, tmpdir):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "airtable_view.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with pytest.raises(AirtableShareIsNotABase):
        AirtableHandler.import_from_airtable_to_workspace(
            workspace, "appZkaH3aWX3ZjT3b", storage=storage
        )


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch("baserow.core.jobs.handler.run_async_job")
def test_create_and_start_airtable_import_job(mock_run_async_job, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    with pytest.raises(UserNotInWorkspace):
        JobHandler().create_and_start_job(
            user,
            AirtableImportJobType.type,
            workspace_id=workspace_2.id,
            airtable_share_url="https://airtable.com/shrXxmp0WmqsTkFWTz",
        )

    job = JobHandler().create_and_start_job(
        user,
        AirtableImportJobType.type,
        workspace_id=workspace.id,
        airtable_share_url="https://airtable.com/shrXxmp0WmqsTkFWTz",
    )
    assert job.user_id == user.id
    assert job.workspace_id == workspace.id
    assert job.airtable_share_id == "shrXxmp0WmqsTkFWTz"
    assert job.progress_percentage == 0
    assert job.state == "pending"
    assert job.error == ""

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == job.id


@pytest.mark.django_db
@responses.activate
def test_create_and_start_airtable_import_job_while_other_job_is_running(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_airtable_import_job(user=user, state=JOB_PENDING)

    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user,
            AirtableImportJobType.type,
            workspace_id=workspace.id,
            airtable_share_url="https://airtable.com/shrXxmp0WmqsTkFWTz",
        )


@pytest.mark.django_db
@responses.activate
def test_create_and_start_airtable_import_job_without_both_session_and_signature(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(serializers.ValidationError):
        JobHandler().create_and_start_job(
            user,
            AirtableImportJobType.type,
            workspace_id=workspace.id,
            airtable_share_url="https://airtable.com/shrXxmp0WmqsTkFWTz",
            session="test",
        )

    with pytest.raises(serializers.ValidationError):
        JobHandler().create_and_start_job(
            user,
            AirtableImportJobType.type,
            workspace_id=workspace.id,
            airtable_share_url="https://airtable.com/shrXxmp0WmqsTkFWTz",
            session_signature="test",
        )


@pytest.mark.django_db
def test_get_airtable_import_job(data_fixture):
    user = data_fixture.create_user()

    job_1 = data_fixture.create_airtable_import_job(user=user)
    job_2 = data_fixture.create_airtable_import_job()

    with pytest.raises(JobDoesNotExist):
        JobHandler.get_job(user, job_2.id)

    job = JobHandler.get_job(user, job_1.id, job_model=AirtableImportJob)
    assert isinstance(job, AirtableImportJob)
    assert job.id == job_1.id
