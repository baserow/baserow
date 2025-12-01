from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.api.views.signers import export_public_view_signer
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

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
        password="12345678",
        allow_public_export=True,
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
def test_create_public_view_export_respecting_view_visible_fields(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    hidden_text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "Something",
            f"field_{hidden_text_field.id}": "Should be hidden",
        },
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=True
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field\n1,Something\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_view_filters(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    premium_data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="world"
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field\n2,world\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_ad_hoc_filters(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "filters": {
                        "filter_type": "AND",
                        "filters": [
                            {
                                "type": "contains",
                                "field": text_field.id,
                                "value": "world",
                            }
                        ],
                        "groups": [],
                    },
                    "order_by": "",
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field\n2,world\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_malformed_ad_hoc_filters(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "filters": {"test": ""},
                    "order_by": "",
                },
                format="json",
            )
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_ad_hoc_order_by(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "filters": None,
                    "order_by": f"-field_{text_field.id}",
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field\n2,world\n1,hello\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_malformed_order_by(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "filters": None,
                    "order_by": f"TEST",
                },
                format="json",
            )
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert response.json()["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_include_visible_fields_in_order(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    text_field_2 = premium_data_fixture.create_text_field(
        table=table, name="text_field2", order=2
    )
    text_field_3 = premium_data_fixture.create_text_field(
        table=table, name="text_field3", order=2
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "fields": [text_field_2.id, text_field.id],
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field2,text_field\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_respecting_include_visible_fields_in_order_wrong_field_id(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    text_field_2 = premium_data_fixture.create_text_field(
        table=table, name="text_field2", order=2
    )
    text_field_3 = premium_data_fixture.create_text_field(
        table=table, name="text_field3", order=2
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "fields": [9999999, text_field_2.id, text_field.id],
                },
                format="json",
            )

        job_id = response.json().pop("id")
        response = api_client.get(
            reverse(
                "api:premium:view:get_public_view_export", kwargs={"job_id": job_id}
            ),
        )
        response_json = response.json()
        filename = response_json["exported_file_name"]

        file_path = tmpdir.join(settings.EXPORT_FILES_DIRECTORY, filename)
        assert file_path.isfile()
        expected = "\ufeff" "id,text_field2,text_field\n"
        with open(file_path, "r", encoding="utf-8") as written_file:
            assert written_file.read() == expected


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_error_hidden_fields_in_order_by(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    hidden_text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=True
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "order_by": f"field_{hidden_text_field.id}",
                },
                format="json",
            )

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_can_sort_by_manually_hidden_view(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    hidden_text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=text_field, hidden=False
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=False
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "order_by": f"field_{hidden_text_field.id}",
                    "fields": [text_field.id],
                },
                format="json",
            )

        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_public_view_export_error_hidden_fields_in_filters(
    api_client, premium_data_fixture, django_capture_on_commit_callbacks, tmpdir
):
    storage = FileSystemStorage(location=(str(tmpdir)), base_url="http://localhost")

    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=1
    )
    grid_view = premium_data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    hidden_text_field = premium_data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=text_field, hidden=False
    )
    premium_data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{hidden_text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{hidden_text_field.id}": "world",
        },
    )

    with patch("baserow.core.storage.get_default_storage") as get_storage_mock:
        get_storage_mock.return_value = storage

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                reverse(
                    "api:premium:view:export_public_view",
                    kwargs={"slug": grid_view.slug},
                ),
                data={
                    "exporter_type": "csv",
                    "export_charset": "utf-8",
                    "csv_include_header": "True",
                    "csv_column_separator": ",",
                    "filters": {
                        "filter_type": "AND",
                        "filters": [
                            {
                                "type": "contains",
                                "field": hidden_text_field.id,
                                "value": "world",
                            }
                        ],
                        "groups": [],
                    },
                },
                format="json",
            )

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"


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
