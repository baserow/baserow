from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile

import pytest
import responses

from baserow.core.formula.service_file import ServiceFile
from baserow.core.models import UserFile
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.helpers import AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def stored_csv_file(data_fixture, monkeypatch, tmpdir, content):
    storage = FileSystemStorage(location=str(tmpdir), base_url="/media/")
    monkeypatch.setattr(
        "baserow.core.formula.service_file.get_default_storage", lambda: storage
    )
    user_file = data_fixture.create_user_file(original_name="data.csv")
    storage.save(UserFileHandler().user_file_path(user_file.name), ContentFile(content))
    return {
        "__file__": True,
        "name": user_file.name,
        "url": UserFileHandler().get_user_file_url(user_file),
    }


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_with_header(
    data_fixture, monkeypatch, tmpdir
):
    service = data_fixture.create_core_csv_file_reader_service(file="get('file')")

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "file": stored_csv_file(
                    data_fixture, monkeypatch, tmpdir, "Name,Age\nAda,36\nBob,40\n"
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
def test_core_csv_file_reader_service_type_dispatch_data_without_header(
    data_fixture, monkeypatch, tmpdir
):
    service = data_fixture.create_core_csv_file_reader_service(
        file="get('file')",
        first_line_is_header=False,
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "file": stored_csv_file(
                    data_fixture, monkeypatch, tmpdir, "Ada,36\nBob,40\n"
                )
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [
            {"column_1": "Ada", "column_2": "36"},
            {"column_1": "Bob", "column_2": "40"},
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_with_separator(
    data_fixture, monkeypatch, tmpdir
):
    service = data_fixture.create_core_csv_file_reader_service(
        file="get('file')",
        separator=";",
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "file": stored_csv_file(
                    data_fixture, monkeypatch, tmpdir, "Name;Age\nAda;36\n"
                )
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [{"Name": "Ada", "Age": "36"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_with_raw_csv(data_fixture):
    service = data_fixture.create_core_csv_file_reader_service(
        input_type="content",
        csv="get('csv')",
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "csv": "Name,Age\nAda,36\nBob,40\n",
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
def test_core_csv_file_reader_service_type_dispatch_data_content_ignores_file(
    data_fixture,
):
    service = data_fixture.create_core_csv_file_reader_service(
        input_type="content",
        file="get('not_a_file')",
        csv="get('csv')",
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "not_a_file": "not a valid file",
                "csv": "Name,Age\nAda,36\n",
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [{"Name": "Ada", "Age": "36"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_file_ignores_content(
    data_fixture, monkeypatch, tmpdir
):
    service = data_fixture.create_core_csv_file_reader_service(
        input_type="file",
        file="get('file')",
        csv="get('not_csv')",
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(
            context={
                "file": stored_csv_file(
                    data_fixture, monkeypatch, tmpdir, "Name,Age\nAda,36\n"
                ),
                "not_csv": "not a csv",
            },
        ),
    )

    assert dispatch_result.data == {
        "results": [{"Name": "Ada", "Age": "36"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
@responses.activate
def test_core_csv_file_reader_service_type_dispatch_data_with_url_string(data_fixture):
    url = "https://example.com/data.csv"
    responses.add(
        responses.GET,
        url,
        body=b"Name,Age\nAda,36\n",
        headers={"Content-Type": "text/csv"},
        status=200,
    )
    service = data_fixture.create_core_csv_file_reader_service(file="get('file')")

    assert UserFile.objects.count() == 0

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(context={"file": url}),
    )

    assert dispatch_result.data == {
        "results": [{"Name": "Ada", "Age": "36"}],
        "has_next_page": False,
    }
    assert UserFile.objects.count() == 0


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_decodes_bytes(data_fixture):
    service = data_fixture.create_core_csv_file_reader_service(
        file="",
        separator=";",
        encoding="latin-1",
    )

    dispatch_data = service.get_type().dispatch_data(
        service,
        {
            "file": ServiceFile(
                name="data.csv",
                file=SimpleUploadedFile(
                    "data.csv",
                    "Name;City\nAndré;Montréal\n".encode("latin-1"),
                ),
            )
        },
        FakeDispatchContext(),
    )

    assert dispatch_data == {
        "results": [{"Name": "André", "City": "Montréal"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_dispatch_data_fails_on_invalid_encoding(
    data_fixture,
):
    service = data_fixture.create_core_csv_file_reader_service(
        file="",
        encoding="utf-8",
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service.get_type().dispatch_data(
            service,
            {
                "file": ServiceFile(
                    name="data.csv", file=SimpleUploadedFile("data.csv", b"\xff")
                )
            },
            FakeDispatchContext(),
        )

    assert "couldn't be decoded using utf-8" in str(exc_info.value)


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_schema(data_fixture):
    service = data_fixture.create_core_csv_file_reader_service(
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
def test_core_csv_file_reader_service_type_extract_properties_with_path(
    data_fixture, path, expected
):
    service = data_fixture.create_core_csv_file_reader_service()

    assert service.get_type().extract_properties(service, path) == expected


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_extract_properties_with_empty_schema(
    data_fixture,
):
    service = data_fixture.create_core_csv_file_reader_service()

    assert service.get_type().extract_properties(service, []) == []


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_empty_schema(data_fixture):
    service = data_fixture.create_core_csv_file_reader_service(
        sample_data={"data": {"results": []}}
    )

    assert service.get_type().generate_schema(service) is None


@pytest.mark.django_db
def test_core_csv_file_reader_service_type_error_sample_data_schema(data_fixture):
    service = data_fixture.create_core_csv_file_reader_service(
        sample_data={
            "_error": "Value error for 'file' property: A valid file or url is required."
        }
    )

    assert service.get_type().generate_schema(service) is None
