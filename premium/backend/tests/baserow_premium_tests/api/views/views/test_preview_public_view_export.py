from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.api.views.signers import export_public_view_signer
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from baserow.contrib.database.export.models import ExportJob


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_of_not_existing_view(
    api_client, premium_data_fixture
):
    response = api_client.post(
        reverse(
            "api:premium:view:export_public_view", kwargs={"slug": "does_not_exist"}
        ),
        data={
            "exporter_type": "csv",
            "export_charset": "utf-8",
            "csv_include_header": "True",
            "csv_column_separator": ",",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_of_not_public_view(api_client, premium_data_fixture):
    grid = premium_data_fixture.create_grid_view(public=False)

    response = api_client.post(
        reverse("api:premium:view:export_public_view", kwargs={"slug": grid.slug}),
        data={
            "exporter_type": "csv",
            "export_charset": "utf-8",
            "csv_include_header": "True",
            "csv_column_separator": ",",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_view_password(
    api_client, premium_data_fixture
):
    (
        grid,
        public_view_token,
    ) = premium_data_fixture.create_public_password_protected_grid_view_with_token(
        password="12345678"
    )

    response = api_client.post(
        reverse("api:premium:view:export_public_view", kwargs={"slug": grid.slug}),
        data={
            "exporter_type": "csv",
            "export_charset": "utf-8",
            "csv_include_header": "True",
            "csv_column_separator": ",",
        },
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:premium:view:export_public_view", kwargs={"slug": grid.slug}),
        data={
            "exporter_type": "csv",
            "export_charset": "utf-8",
            "csv_include_header": "True",
            "csv_column_separator": ",",
        },
        format="json",
        HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {public_view_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    grid = premium_data_fixture.create_grid_view(public=True, allow_public_export=True)

    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view", kwargs={"slug": grid.slug}
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                },
                format="json",
            )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK

        job = ExportJob.objects.all().first()
        del response_json["created_at"]

        job_id = response_json.pop("id")
        assert export_public_view_signer.loads(job_id) == job.id

        assert response_json == {
            "table": grid.table_id,
            "view": grid.id,
            "exporter_type": "csv",
            "state": "pending",
            "status": "pending",
            "exported_file_name": None,
            "progress_percentage": 0.0,
            "url": None,
        }

        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()

        job_id = response_json.pop("id")
        del response_json["created_at"]
        assert export_public_view_signer.loads(job_id) == job.id
        filename = response_json["exported_file_name"]
        assert response_json == {
            "table": grid.table_id,
            "view": grid.id,
            "exporter_type": "csv",
            "state": "finished",
            "status": "finished",
            "exported_file_name": filename,
            "progress_percentage": 100.0,
            "url": f"http://localhost:8000/media/export_files/{filename}",
        }

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_view_filters_and_visible_fields(
    api_client, premium_data_fixture
):
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_filter_query_param(
    api_client, premium_data_fixture
):
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_sort_query_param(
    api_client, premium_data_fixture
):
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_include_fields_query_param(
    api_client, premium_data_fixture
):
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_public_view_export_job_not_found(api_client, premium_data_fixture):
    response = api_client.get(
        reverse(
            "api:premium:view:get_public_view_export",
            kwargs={"job_id": export_public_view_signer.dumps(0)},
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_EXPORT_JOB_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_public_view_export_invalid_signed_id(api_client, premium_data_fixture):
    response = api_client.get(
        reverse("api:premium:view:get_public_view_export", kwargs={"job_id": "test"}),
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_EXPORT_JOB_DOES_NOT_EXIST"
