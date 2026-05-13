import base64
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

import pytest
from openpyxl import Workbook

from baserow.core.formula.service_file import ServiceFile
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.helpers import AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext

PEOPLE_XLS = base64.b64decode(
    "0M8R4KGxGuEAAAAAAAAAAAAAAAAAAAAAOwADAP7/CQAGAAAAAAAAAAAAAAABAAAACAAAAAAAAAAAEAAAAgAAAAEAAAD+////AAAAAAAAAAD////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////9//////////7///8EAAAABQAAAAYAAAAHAAAA/v///wkAAAD+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////1IAbwBvAHQAIABFAG4AdAByAHkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWAAUA////////////////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/v///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///////////////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD+////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///////////////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP7///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////////////////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/v///wAAAAAAAAAAAQAAAAIAAAADAAAABAAAAAUAAAAGAAAABwAAAAgAAAAJAAAACgAAAAsAAAAMAAAADQAAAA4AAAAPAAAAEAAAABEAAAASAAAAEwAAABQAAAAVAAAAFgAAABcAAAAYAAAAGQAAABoAAAD+////HAAAAP7////+////HwAAACAAAAAhAAAA/v///yMAAAAkAAAA/v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8JCBAAAAYFALsNzAcAAAAABgAAAOEAAgCwBMEAAgAAAOIAAABcAHAABAAAQ2FsYyAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIEIAAgCwBGEBAgAAAMABAAA9AQIAAQCcAAIADgCvAQIAAAC8AQIAAAA9ABIAAAAAAABAACA4AAAAAAABAFgCQAACAAAAjQACAAAAIgACAAAADgACAAEAtwECAAAA2gACAAAAMQAeANwAAAAIAJABAAAAAgEABwFDAGEAbABpAGIAcgBpADEAGgDIAAAA/3+QAQAAAAAAAAUBQQByAGkAYQBsADEAGgDIAAAA/3+QAQAAAAAAAAUBQQByAGkAYQBsADEAGgDIAAAA/3+QAQAAAAAAAAUBQQByAGkAYQBsAB4EDACkAAcAAEdlbmVyYWzgABQAAACkAPX/IAAAAAAAAAAAAAAAwCDgABQAAQAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAQAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAgAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAgAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAAwCDgABQAAAAAAPX/IAAA9AAAAAAAAAAA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"
)


def workbook_bytes(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)

    for sheet_name, rows in sheets:
        sheet = workbook.create_sheet(sheet_name)
        for row in rows:
            sheet.append(row)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def service_file(name, content):
    return ServiceFile(name=name, file=SimpleUploadedFile(name, content))


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_core_xls_file_reader_service_type_dispatch_data_with_xlsx(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()
    workspace = enterprise_data_fixture.create_workspace()
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service(
        file="get('file')"
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            workspace=workspace,
            context={
                "file": service_file(
                    "people.xlsx",
                    workbook_bytes(
                        [
                            (
                                "People",
                                [
                                    ["Name", "Age"],
                                    ["Ada", 36],
                                    ["Bob", 40],
                                ],
                            )
                        ]
                    ),
                )
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [
            {"Name": "Ada", "Age": "36"},
            {"Name": "Bob", "Age": "40"},
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_xls_file_reader_service_type_dispatch_data_with_legacy_xls(
    enterprise_data_fixture,
):
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service()

    dispatch_data = service.get_type().dispatch_data(
        service,
        {"file": service_file("people.xls", PEOPLE_XLS)},
        FakeDispatchContext(),
    )

    assert dispatch_data == {
        "results": [
            {"Name": "Ada", "Age": "36"},
            {"Name": "Bob", "Age": "40"},
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_xls_file_reader_service_type_dispatch_data_without_header(
    enterprise_data_fixture,
):
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service(
        first_line_is_header=False,
    )

    dispatch_data = service.get_type().dispatch_data(
        service,
        {
            "file": service_file(
                "people.xlsx",
                workbook_bytes([("People", [["Ada", 36], ["Bob", 40]])]),
            )
        },
        FakeDispatchContext(),
    )

    assert dispatch_data == {
        "results": [
            {"column_1": "Ada", "column_2": "36"},
            {"column_1": "Bob", "column_2": "40"},
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_core_xls_file_reader_service_type_dispatch_data_with_sheet_name(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()
    workspace = enterprise_data_fixture.create_workspace()
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service(
        file="get('file')", sheet_name="'People'"
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            workspace=workspace,
            context={
                "file": service_file(
                    "people.xlsx",
                    workbook_bytes(
                        [
                            ("Other", [["Name"], ["Wrong"]]),
                            ("People", [["Name"], ["Ada"]]),
                        ]
                    ),
                )
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [{"Name": "Ada"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_xls_file_reader_service_type_dispatch_data_with_missing_sheet(
    enterprise_data_fixture,
):
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service.get_type().dispatch_data(
            service,
            {
                "file": service_file(
                    "people.xlsx",
                    workbook_bytes([("People", [["Name"], ["Ada"]])]),
                ),
                "sheet_name": "Missing",
            },
            FakeDispatchContext(),
        )

    assert 'The sheet "Missing" does not exist.' in str(exc_info.value)


@pytest.mark.django_db
def test_core_xls_file_reader_service_type_schema(enterprise_data_fixture):
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service(
        sample_data={
            "data": {
                "results": [
                    {"Name": "Ada", "Age": "36"},
                    {"Name": "Bob", "Age": "40"},
                ],
                "has_next_page": False,
            }
        }
    )

    assert service.get_type().generate_schema(service) == {
        "$schema": AnyStr(),
        "title": AnyStr(),
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"Name": {"type": "string"}, "Age": {"type": "string"}},
            "required": ["Age", "Name"],
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,expected",
    [
        (["Name"], ["Name"]),
        (["Name", "0", "value"], ["Name"]),
        (["Age", ""], ["Age"]),
    ],
)
def test_core_xls_file_reader_service_type_extract_properties_with_path(
    enterprise_data_fixture, path, expected
):
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service()

    assert service.get_type().extract_properties(service, path) == expected
