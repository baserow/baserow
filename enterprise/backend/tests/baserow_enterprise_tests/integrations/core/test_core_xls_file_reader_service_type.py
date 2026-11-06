from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

import pytest
from openpyxl import Workbook

from baserow.core.formula.service_file import ServiceFile
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.helpers import PEOPLE_XLS, AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext


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
