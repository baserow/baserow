import json
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage

import pytest
import requests
import responses
from rest_framework import serializers

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.constants import (
    AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH,
    AIRTABLE_SHARE_TYPE_BASE,
    AIRTABLE_SHARE_TYPE_VIEW,
)
from baserow.contrib.database.airtable.exceptions import (
    AirtableBaseRequiresAuthentication,
    AirtableShareIsNotABase,
    FileDownloadFailed,
)
from baserow.contrib.database.airtable.handler import (
    AirtableFileImport,
    AirtableHandler,
    download_airtable_file,
)
from baserow.contrib.database.airtable.import_report import AirtableImportReport
from baserow.contrib.database.airtable.job_types import AirtableImportJobType
from baserow.contrib.database.airtable.models import AirtableImportJob, DownloadFile
from baserow.contrib.database.fields.models import (
    LinkRowField,
    LongTextField,
    TextField,
)
from baserow.contrib.database.views.models import GridViewFieldOptions
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import JOB_PENDING
from baserow.core.jobs.exceptions import JobDoesNotExist, MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.user_files.models import UserFile
from baserow.core.utils import Progress

STUB_AIRTABLE_FETCH_DOWNLOAD_FILE = DownloadFile(
    url="https://example.com/file.pdf",
    row_id="",
    column_id="",
    attachment_id="",
    type=AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH,
)


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
def test_fetch_publicly_shared_share_detects_base():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_base.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    (
        share_type,
        request_id,
        init_data,
        cookies,
    ) = AirtableHandler.fetch_publicly_shared_share(
        "appZkaH3aWX3ZjT3b",
        AirtableImportConfig(),
    )
    assert share_type == AIRTABLE_SHARE_TYPE_BASE
    assert request_id == "req8wbZoh7Be65osz"


@pytest.mark.django_db
@responses.activate
def test_fetch_publicly_shared_share_detects_view():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_view.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appC1QggQ2236mAAA/shr1YAA2t24xr444",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    (
        share_type,
        request_id,
        init_data,
        cookies,
    ) = AirtableHandler.fetch_publicly_shared_share(
        "appC1QggQ2236mAAA/shr1YAA2t24xr444",
        AirtableImportConfig(),
    )
    assert share_type == AIRTABLE_SHARE_TYPE_VIEW
    assert request_id == "reqKfV1kJQcXBGFmM"
    assert init_data["sharedViewId"] == "viwtwpf55H6mkh2s"
    assert cookies["brw"] == "test"


@pytest.mark.django_db
@responses.activate
def test_fetch_publicly_shared_base_raises_when_view():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_view.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appZkaH3aWX3ZjT3b",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with pytest.raises(AirtableShareIsNotABase):
        AirtableHandler.fetch_publicly_shared_base(
            "appZkaH3aWX3ZjT3b",
            AirtableImportConfig(),
        )


@pytest.mark.django_db
@responses.activate
def test_fetch_shared_view_data():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_view.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appC1QggQ2236mAAA/shr1YAA2t24xr444",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    (
        share_type,
        request_id,
        init_data,
        cookies,
    ) = AirtableHandler.fetch_publicly_shared_share(
        "appC1QggQ2236mAAA/shr1YAA2t24xr444",
        AirtableImportConfig(),
    )

    with open(
        os.path.join(base_path, "airtable_shared_view.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwtwpf55H6mkh2s/readSharedViewData",
            status=200,
            body=file_handler.read(),
        )

    response = AirtableHandler.fetch_shared_view_data(
        init_data["sharedViewId"], init_data, request_id, cookies, stream=False
    )
    json_decoded_content = response.json()

    request_url = responses.calls[-1].request.url
    assert "readSharedViewData" in request_url
    assert "shouldUseNestedResponseFormat" in request_url
    assert f"requestId={request_id}" in request_url
    assert "accessPolicy" in request_url
    assert json_decoded_content["data"]["table"]["id"] == "tbl2R4lt3QnjdlAtt"


def test_extract_shared_view_schema():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_shared_view.json"), "r") as file:
        payload = json.load(file)

    schema, tables = AirtableHandler.extract_shared_view_schema(payload["data"])

    assert len(schema["tableSchemas"]) == 1
    table = schema["tableSchemas"][0]
    assert table["id"] == "tbl2R4lt3QnjdlAtt"
    assert table["name"] == "Shared view table"
    assert "rows" not in table
    assert table["viewOrder"] == ["viwtwpf55H6mkh2s"]
    assert table["viewSectionsById"] == {}
    assert "typeOptions" not in table["columns"][0]
    assert "default" not in table["columns"][0]
    assert "symbol" not in table["columns"][2]["typeOptions"]

    table_data = tables["tbl2R4lt3QnjdlAtt"]
    assert [row["id"] for row in table_data["rows"]] == [
        "recSecondRow0000002",
        "recThirdRow00000003",
        "recFirstRow00000001",
    ]
    assert table_data["viewDatas"] == table["views"]
    assert (
        "https://dl.airtable.com/.attachments/anonymized1/anon1/file-a.txt"
        in table_data["signedUserContentUrls"]
    )


def test_extract_shared_view_schema_unsupported_view_type():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_shared_view.json"), "r") as file:
        payload = json.load(file)

    payload["data"]["table"]["views"][0]["type"] = "kanban"
    schema, tables = AirtableHandler.extract_shared_view_schema(payload["data"])

    view = schema["tableSchemas"][0]["views"][0]
    assert view["type"] == "grid"
    assert view["airtable_original_type"] == "kanban"


@pytest.mark.django_db
def test_parse_table_fields_reassigns_primary_when_fallback_primary_is_removed():
    table = {
        "id": "tblPrimaryTest00001",
        "name": "Primary test",
        "primaryColumnId": "fldFormula000000001",
        "meaningfulColumnOrder": [
            {"columnId": "fldFormula000000001", "visibility": True},
            {"columnId": "fldCount00000000002", "visibility": True},
        ],
        "columns": [
            {"id": "fldFormula000000001", "name": "Formula", "type": "formula"},
            {
                "id": "fldCount00000000002",
                "name": "Count",
                "type": "count",
                "typeOptions": {"relationColumnId": "fldMissingLink00001"},
            },
        ],
    }
    import_report = AirtableImportReport()

    field_mapping_per_table = AirtableHandler._parse_table_fields(
        {"tableSchemas": [table]},
        Progress(10),
        AirtableImportConfig(),
        import_report,
    )

    field_mapping = field_mapping_per_table["tblPrimaryTest00001"]
    # The count field was first promoted to primary because the formula field is
    # not supported, but it can't be imported because its link field is missing,
    # so a new primary field must have been created afterwards.
    assert "fldCount00000000002" not in field_mapping
    primary_fields = [
        field_object["baserow_field"]
        for field_object in field_mapping.values()
        if field_object["baserow_field"].primary
    ]
    assert len(primary_fields) == 1
    assert primary_fields[0].name == "Primary field (auto created)"


def test_extract_shared_view_schema_view_missing_in_view_order():
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )

    with open(os.path.join(base_path, "airtable_shared_view.json"), "r") as file:
        payload = json.load(file)

    payload["data"]["table"]["viewOrder"] = ["viwSomeOtherView0001"]
    schema, tables = AirtableHandler.extract_shared_view_schema(payload["data"])

    assert schema["tableSchemas"][0]["viewOrder"] == [
        "viwSomeOtherView0001",
        "viwtwpf55H6mkh2s",
    ]


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
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
            "frozen_column_count": 1,
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
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recAAA5JwFXBk4swkfB/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
    assert [s.priority for s in table_1_view_1_sorts] == [1, 2]
    table_1_view_1_group_bys = table_1_views[1].viewgroupby_set.all()
    assert len(table_1_view_1_group_bys) == 1
    assert table_1_view_1_group_bys[0].priority == 1

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
def test_import_from_airtable_to_workspace_file_size_over_limit(
    data_fixture, tmpdir, settings
):
    settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = 100 * 1024  # 100kB
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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

    # Oversized file is skipped
    assert UserFile.objects.all().count() == 2

    # Oversized file is in the report
    report_table = database.table_set.last()
    assert report_table.name == "Airtable import report"

    model = report_table.get_model(attribute_names=True)
    row = model.objects.last()
    assert row.object_name == "File"
    assert row.scope.value == "Cell"
    assert row.table is not None
    assert row.error_type.value == "Other"
    assert (
        row.message
        == "Field: Attachment, Row: 3, File: e93dc201ce27080d9ad9df5775527d09_93e85b28_file-sample_500kB.doc"
    )


@pytest.mark.django_db
@responses.activate
def test_import_from_airtable_to_workspace_with_report_table(data_fixture, tmpdir):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signed/file-sample.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample_500kB.doc"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/rec9Imz1INvNXgRIXn1/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(
        os.path.join(base_path, "file_example_JPG_100kB.jpg"), "rb"
    ) as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recyANUudYjDqIXdq9Z/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
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
def test_import_publicly_shared_view_to_workspace(data_fixture, tmpdir):
    workspace = data_fixture.create_workspace()
    base_path = os.path.join(
        settings.BASE_DIR, "../../../tests/airtable_responses/basic"
    )
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with open(os.path.join(base_path, "airtable_view.html"), "rb") as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/appC1QggQ2236mAAA/shr1YAA2t24xr444",
            status=200,
            body=file_handler.read(),
            headers={"Set-Cookie": "brw=test;"},
        )

    with open(
        os.path.join(base_path, "airtable_shared_view.json"), "rb"
    ) as file_handler:
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/view/viwtwpf55H6mkh2s/readSharedViewData",
            status=200,
            body=file_handler.read(),
        )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://dl.airtable.com/.signedUserContent/file-a.txt",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    with open(os.path.join(base_path, "file-sample.txt"), "rb") as file_handler:
        body = file_handler.read()
        responses.add(
            responses.GET,
            "https://airtable.com/v0.3/row/recFirstRow00000001/downloadAttachment",
            status=206,
            body=body,
            headers={"Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}"},
        )

    progress = Progress(1000)

    database = AirtableHandler.import_from_airtable_to_workspace(
        workspace,
        "appC1QggQ2236mAAA/shr1YAA2t24xr444",
        storage=storage,
        progress_builder=progress.create_child_builder(represents_progress=1000),
    )

    assert progress.progress == progress.total
    assert UserFile.objects.all().count() == 2

    assert database.name == "Shared view base"
    all_tables = database.table_set.all()
    assert len(all_tables) == 2
    table = all_tables[0]
    assert table.name == "Shared view table"
    assert all_tables[1].name == "Airtable import report"

    fields = {field.name: field.specific for field in table.field_set.all()}
    assert sorted(fields.keys()) == [
        "Attachments",
        "Companies",
        "Name",
        "Notes",
        "Number",
        "Related rows",
        "Status",
    ]
    assert fields["Name"].primary is True
    assert isinstance(fields["Name"], TextField)
    assert isinstance(fields["Companies"], LongTextField)
    assert isinstance(fields["Related rows"], LinkRowField)
    assert fields["Related rows"].link_row_table_id == table.id

    views = table.view_set.all()
    assert len(views) == 1
    assert views[0].name == "Grid view"
    hidden_field_options = GridViewFieldOptions.objects.get(
        grid_view_id=views[0].id, field_id=fields["Notes"].id
    )
    assert hidden_field_options.hidden is True

    model = table.get_model(attribute_names=True)
    rows = list(model.objects.all())
    # The view row order is leading, so "Row 1" is imported last.
    assert [row.name for row in rows] == ["Row 2", "Row 3", "Row 1"]
    assert rows[2].companies == "Company A, Company B"
    assert rows[1].companies == "Company C"
    assert [r.id for r in rows[2].related_rows.all()] == [rows[0].id]
    assert len(rows[2].attachments) == 2

    report_model = all_tables[1].get_model(attribute_names=True)
    report_rows = [row.object_name for row in report_model.objects.all()]
    assert "Companies" in report_rows
    assert "Company count" in report_rows
    assert "Company names" in report_rows


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


@responses.activate
def test_download_airtable_file_chunked_no_content_length():
    file_content = b"%PDF-1.4 fake pdf content" * 1000
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=file_content,
        status=200,
        headers={"Transfer-Encoding": "chunked"},
    )

    response = download_airtable_file(
        name="test.pdf",
        download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
        init_data={},
        request_id="req1",
        cookies={},
    )
    assert response.content == file_content


@responses.activate
def test_download_airtable_file_with_content_length():
    file_content = b"some file bytes"
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=file_content,
        status=200,
        headers={"Content-Length": str(len(file_content))},
    )

    response = download_airtable_file(
        name="file.txt",
        download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
        init_data={},
        request_id="req1",
        cookies={},
    )
    assert response.content == file_content


@responses.activate
def test_download_airtable_file_partial_content_range():
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=b"012345",
        status=206,
        headers={"Content-Range": "bytes 0-5/500000"},
    )

    response = download_airtable_file(
        name="file.pdf",
        download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
        init_data={},
        request_id="req1",
        cookies={},
    )
    assert response.status_code == 206


@responses.activate
def test_download_airtable_file_exceeds_size_limit():
    file_content = b"x" * 100
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=file_content,
        status=200,
        headers={"Content-Length": str(len(file_content))},
    )

    with patch("baserow.contrib.database.airtable.handler.settings") as mock_settings:
        mock_settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = 50
        with pytest.raises(FileDownloadFailed, match="exceeds the size limit"):
            download_airtable_file(
                name="big.bin",
                download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
                init_data={},
                request_id="req1",
                cookies={},
            )


@responses.activate
def test_download_airtable_file_chunked_exceeds_size_limit():
    file_content = b"x" * 100
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=file_content,
        status=200,
        headers={"Transfer-Encoding": "chunked"},
    )

    with patch("baserow.contrib.database.airtable.handler.settings") as mock_settings:
        mock_settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = 50
        with pytest.raises(FileDownloadFailed, match="exceeds the size limit"):
            download_airtable_file(
                name="big.bin",
                download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
                init_data={},
                request_id="req1",
                cookies={},
            )


@responses.activate
def test_download_airtable_file_http_error():
    responses.add(responses.GET, STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url, status=404)

    with pytest.raises(FileDownloadFailed, match="HTTP 404"):
        download_airtable_file(
            name="missing.pdf",
            download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
            init_data={},
            request_id="req1",
            cookies={},
        )


@responses.activate
def test_airtable_file_import_open_download_failure_raises_key_error():
    responses.add(responses.GET, STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url, status=500)

    file_import = AirtableFileImport(
        init_data={},
        request_id="req1",
        cookies={},
    )
    file_import.add_files({"broken.pdf": STUB_AIRTABLE_FETCH_DOWNLOAD_FILE})

    with pytest.raises(KeyError, match="could not be downloaded"):
        with file_import.open("broken.pdf"):
            pass


@responses.activate
def test_download_airtable_file_request_exception_wraps_to_file_download_failed():
    responses.add(
        responses.GET,
        STUB_AIRTABLE_FETCH_DOWNLOAD_FILE.url,
        body=requests.exceptions.ConnectionError("Connection refused"),
    )

    with pytest.raises(FileDownloadFailed, match="could not be downloaded"):
        download_airtable_file(
            name="unreachable.pdf",
            download_file=STUB_AIRTABLE_FETCH_DOWNLOAD_FILE,
            init_data={},
            request_id="req1",
            cookies={},
        )
