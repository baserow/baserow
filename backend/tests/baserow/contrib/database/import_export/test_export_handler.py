import csv
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import List
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.dateparse import parse_date, parse_datetime

import pytest
from freezegun import freeze_time

from baserow.contrib.database.api.export.serializers import (
    SUPPORTED_CSV_COLUMN_SEPARATORS,
    SUPPORTED_EXPORT_CHARSETS,
    BaseExporterOptionsSerializer,
)
from baserow.contrib.database.export.exceptions import (
    ExportJobCanceledException,
    TableOnlyExportUnsupported,
    ViewUnsupportedForExporterType,
)
from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.export.models import (
    EXPORT_JOB_CANCELLED_STATUS,
    EXPORT_JOB_EXPIRED_STATUS,
    EXPORT_JOB_EXPORTING_STATUS,
    EXPORT_JOB_FAILED_STATUS,
    EXPORT_JOB_FINISHED_STATUS,
    EXPORT_JOB_PENDING_STATUS,
    ExportJob,
)
from baserow.contrib.database.export.registries import (
    TableExporter,
    table_exporter_registry,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.exceptions import ViewNotInTable
from baserow.contrib.database.views.models import GridView, GridViewFieldOptions
from baserow.core.exceptions import PermissionDenied
from baserow.test_utils.helpers import setup_interesting_test_table


def _parse_datetime(datetime):
    return parse_datetime(datetime).replace(tzinfo=timezone.utc)


def _parse_date(date):
    return parse_date(date)


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_hidden_fields_are_excluded(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=1)
    grid_view = data_fixture.create_grid_view(table=table)
    hidden_text_field = data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "Something",
            f"field_{hidden_text_field.id}": "Should be hidden",
        },
    )
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=True
    )
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,text_field\r\n" f"1,Something\r\n"
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_csv_is_sorted_by_sorts(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(table=table)
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "A",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "Z",
        },
    )
    data_fixture.create_view_sort(view=grid_view, field=text_field, order="DESC")
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,text_field\r\n2,Z\r\n1,A\r\n"
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_csv_is_filtered_by_filters(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(table=table)
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello world",
        },
    )
    data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="world"
    )
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,text_field\r\n2,hello world\r\n"
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_exporting_table_ignores_view_filters_sorts_hides(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=1)
    hidden_text_field = data_fixture.create_text_field(
        table=table, name="text_field", order=2
    )
    grid_view = data_fixture.create_grid_view(table=table)
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
            f"field_{hidden_text_field.id}": "hidden in view",
        },
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello world",
            f"field_{hidden_text_field.id}": "hidden in view",
        },
    )
    data_fixture.create_view_sort(view=grid_view, field=text_field, order="DESC")
    data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="world"
    )
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=hidden_text_field, hidden=True
    )
    _, contents = run_export_job_with_mock_storage(table, None, storage_mock, user)
    bom = "\ufeff"
    expected = (
        bom + "id,text_field,text_field\r\n"
        "1,hello,hidden in view\r\n"
        "2,hello world,hidden in view\r\n"
    )
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_exporting_public_view_without_user_fails_if_not_publicly_shared_and_allowed(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=1)
    grid_view = data_fixture.create_grid_view(
        table=table, public=False, allow_public_export=False
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )

    with pytest.raises(PermissionDenied):
        run_export_job_with_mock_storage(table, grid_view, storage_mock, None)

    grid_view.public = True
    grid_view.allow_public_export = False
    grid_view.save()

    with pytest.raises(PermissionDenied):
        run_export_job_with_mock_storage(table, grid_view, storage_mock, None)

    grid_view.public = False
    grid_view.allow_public_export = True
    grid_view.save()

    with pytest.raises(PermissionDenied):
        run_export_job_with_mock_storage(table, grid_view, storage_mock, None)


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_exporting_public_view_without_user(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=1)
    grid_view = data_fixture.create_grid_view(
        table=table, public=True, allow_public_export=True
    )
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "hello",
        },
    )
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, None)
    bom = "\ufeff"
    expected = bom + "id,text_field\r\n" "1,hello\r\n"
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_columns_are_exported_by_order_then_field_id(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_a = data_fixture.create_text_field(table=table, name="field_a")
    field_b = data_fixture.create_text_field(
        table=table,
        name="field_b",
    )
    field_c = data_fixture.create_text_field(
        table=table,
        name="field_c",
    )
    grid_view = GridView.objects.create(table=table, order=0, name="grid_view")
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{field_a.id}": "a",
            f"field_{field_b.id}": "b",
            f"field_{field_c.id}": "c",
        },
    )
    # Create the option id's in the opposite order than the fields so their id's are
    # ordered backwards to ensure the test doesn't coincidentally pass if the option
    # ids were being used to sort.
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=field_c, order=0
    )
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=field_b, order=1
    )
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=field_a, order=1
    )
    assert field_a.id < field_b.id
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,field_c,field_a,field_b\r\n" "1,c,a,b\r\n"
    assert contents == expected


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_can_export_every_interesting_different_field_to_csv(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    contents = run_export_job_over_interesting_table(
        data_fixture, storage_mock, {"exporter_type": "csv"}
    )
    # noinspection HttpUrlsUsage
    fields = {
        "id": ["1", "2"],
        "text": ["", "text"],
        "long_text": ["", "long_text"],
        "url": ["", "https://www.google.com"],
        "email": ["", "test@example.com"],
        "negative_int": ["", "-1"],
        "positive_int": ["", "1"],
        "negative_decimal": ["", "-1.2"],
        "positive_decimal": ["", "1.2"],
        "decimal_with_default": ["1.8", "1.8"],
        "rating": ["0", "3"],
        "boolean": ["False", "True"],
        "boolean_with_default": ["True", "True"],
        "datetime_us": ["", "02/01/2020 01:23"],
        "date_us": ["", "02/01/2020"],
        "datetime_eu": ["", "01/02/2020 01:23"],
        "date_eu": ["", "01/02/2020"],
        "datetime_eu_tzone_visible": ["", "01/02/2020 02:23"],
        "datetime_eu_tzone_hidden": ["", "01/02/2020 02:23"],
        "last_modified_datetime_us": ["01/02/2021 12:00", "01/02/2021 12:00"],
        "last_modified_date_us": ["01/02/2021", "01/02/2021"],
        "last_modified_datetime_eu": ["02/01/2021 12:00", "02/01/2021 12:00"],
        "last_modified_date_eu": ["02/01/2021", "02/01/2021"],
        "last_modified_datetime_eu_tzone": ["02/01/2021 13:00", "02/01/2021 13:00"],
        "created_on_datetime_us": ["01/02/2021 12:00", "01/02/2021 12:00"],
        "created_on_date_us": ["01/02/2021", "01/02/2021"],
        "created_on_datetime_eu": ["02/01/2021 12:00", "02/01/2021 12:00"],
        "created_on_date_eu": ["02/01/2021", "02/01/2021"],
        "created_on_datetime_eu_tzone": ["02/01/2021 13:00", "02/01/2021 13:00"],
        "last_modified_by": ["user@example.com", "user@example.com"],
        "created_by": ["user@example.com", "user@example.com"],
        "duration_hm": ["", "1:01"],
        "duration_hms": ["", "1:01:06"],
        "duration_hms_s": ["", "1:01:06.6"],
        "duration_hms_ss": ["", "1:01:06.66"],
        "duration_hms_sss": ["", "1:01:06.666"],
        "duration_dh": ["", "1d 1h"],
        "duration_dhm": ["", "1d 1:01"],
        "duration_dhms": ["", "1d 1:01:06"],
        "link_row": ["", '"linked_row_1,linked_row_2,"'],
        "self_link_row": ["", "unnamed row 1"],
        "link_row_without_related": ["", '"linked_row_1,linked_row_2"'],
        "decimal_link_row": ["", '"1.234,-123.456,unnamed row 3"'],
        "file_link_row": [
            "",
            '"name.txt (http://localhost:8000/media/user_files/test_hash.txt),unnamed row 2"',
        ],
        "multiple_collaborators_link_row": [
            "",
            '"""User2 <user2@example.com>,User3 <user3@example.com>"",User2 <user2@example.com>"',
        ],
        "file": [
            "",
            '"a.txt (http://localhost:8000/media/user_files/hashed_name.txt),b.txt (http://localhost:8000/media/user_files/other_name.txt)"',
        ],
        "single_select": ["", "A"],
        "single_select_with_default": ["BB", "BB"],
        "multiple_select": ["", '"D,C,E"'],
        "multiple_select_with_default": ['"M-1,M-2"', '"M-1,M-2"'],
        "multiple_collaborators": [
            "",
            '"User2 <user2@example.com>,User3 <user3@example.com>"',
        ],
        "phone_number": ["", "'+4412345678"],
        "formula_text": ["test FORMULA", "test FORMULA"],
        "formula_int": ["1", "1"],
        "formula_bool": ["True", "True"],
        "formula_decimal": ["33.3333333333", "33.3333333333"],
        "formula_dateinterval": ["1d 0:00", "1d 0:00"],
        "formula_date": ["2020-01-01", "2020-01-01"],
        "formula_singleselect": ["", "A"],
        "formula_email": ["", "test@example.com"],
        "formula_link_with_label": [
            "label (https://google.com)",
            "label (https://google.com)",
        ],
        "formula_link_url_only": ["https://google.com", "https://google.com"],
        "formula_multipleselect": ["", '"C,D,E"'],
        "formula_multiple_collaborators": [
            "",
            '"User2 <user2@example.com>,User3 <user3@example.com>"',
        ],
        "count": ["0", "3"],
        "rollup": ["0.000", "-122.222"],
        "duration_rollup_sum": ["0:00", "0:04"],
        "duration_rollup_avg": ["0:00", "0:02"],
        "lookup": ["", '"linked_row_1,linked_row_2,"'],
        "multiple_collaborators_lookup": [
            "",
            '"""User2 <user2@example.com>,User3 <user3@example.com>"",User2 <user2@example.com>"',
        ],
        "uuid": [
            "00000000-0000-4000-8000-000000000001",
            "00000000-0000-4000-8000-000000000002",
        ],
        "autonumber": ["1", "2"],
        "password": ["", "True"],
        "ai": ["", "I'm an AI."],
        "ai_choice": ["", "Object"],
    }

    # Join headers
    headers = ",".join(fields.keys())

    # Join values for each row
    row1 = ",".join(fields[field][0] for field in fields)
    row2 = ",".join(fields[field][1] for field in fields)

    expected = f"\ufeff{headers}\r\n{row1}\r\n{row2}\r\n"

    def show_diff(actual, expected):
        expected_values = list(csv.reader(StringIO(expected[1:])))
        actual_values = list(csv.reader(StringIO(actual[1:])))
        diff = []
        for i, (actual_row, expected_row) in enumerate(
            zip(actual_values[1:], expected_values[1:])
        ):
            for j, (actual_value, expected_value) in enumerate(
                zip(actual_row, expected_row)
            ):
                if actual_value != expected_value:
                    diff.append(
                        (
                            actual_values[0][j],
                            f"Row {i+1}",
                            actual_value,
                            expected_value,
                        )
                    )
        return diff

    assert contents == expected, show_diff(contents, expected)


def run_export_job_over_interesting_table(data_fixture, storage_mock, options):
    table, user, _, _, context = setup_interesting_test_table(
        data_fixture, user_kwargs={"email": "user@example.com"}
    )
    grid_view = data_fixture.create_grid_view(table=table)
    job, contents = run_export_job_with_mock_storage(
        table, grid_view, storage_mock, user, options
    )
    return contents


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_can_export_special_characters_in_arabic_encoding_to_csv(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(user=user, table=table, name="text")

    special_character = "ê"
    special_character_exported_expected = "\\xea"

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": special_character})

    job, contents = run_export_job_with_mock_storage(
        table,
        grid_view,
        storage_mock,
        user,
        {
            "exporter_type": "csv",
            "export_charset": "iso-8859-6",
        },
    )

    assert (
        contents
        == f"id,{text_field.name}\r\n1,{special_character_exported_expected}\r\n"
    )


@pytest.mark.django_db
def test_creating_a_new_export_job_will_cancel_any_already_running_jobs_for_that_user(
    data_fixture,
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        workspace=table.database.workspace, user=other_user
    )
    handler = ExportHandler()
    first_job = handler.create_pending_export_job(
        user, table, None, {"exporter_type": "csv"}
    )
    other_users_job = handler.create_pending_export_job(
        other_user, table, None, {"exporter_type": "csv"}
    )
    second_job = handler.create_pending_export_job(
        user, table, None, {"exporter_type": "csv"}
    )
    first_job.refresh_from_db()
    other_users_job.refresh_from_db()
    assert first_job.state == EXPORT_JOB_CANCELLED_STATUS
    assert second_job.state == EXPORT_JOB_PENDING_STATUS
    assert other_users_job.state == EXPORT_JOB_PENDING_STATUS


@pytest.mark.django_db
@patch("baserow.contrib.database.export.handler.get_default_storage")
def test_a_complete_export_job_which_has_expired_will_have_its_file_deleted(
    get_storage_mock, data_fixture, settings
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    handler = ExportHandler()
    job_start = datetime.now(tz=timezone.utc)
    half_file_duration = timedelta(minutes=int(settings.EXPORT_FILE_EXPIRE_MINUTES / 2))
    second_job_start = job_start + half_file_duration
    time_when_first_job_will_have_expired = job_start + timedelta(
        minutes=settings.EXPORT_FILE_EXPIRE_MINUTES * 1.1
    )
    with freeze_time(job_start):
        first_job, _ = setup_table_and_run_export_decoding_result(
            data_fixture, storage_mock
        )
    with freeze_time(second_job_start):
        second_job, _ = setup_table_and_run_export_decoding_result(
            data_fixture, storage_mock
        )
    with freeze_time(time_when_first_job_will_have_expired):
        handler.clean_up_old_jobs()

    storage_mock.delete.assert_called_once_with(
        "export_files/" + first_job.exported_file_name
    )
    first_job.refresh_from_db()
    assert first_job.state == EXPORT_JOB_EXPIRED_STATUS
    assert first_job.exported_file_name is None
    second_job.refresh_from_db()
    assert second_job.state == EXPORT_JOB_FINISHED_STATUS
    assert second_job.exported_file_name is not None


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_a_pending_job_which_has_expired_will_be_cleaned_up(
    get_storage_mock,
    data_fixture,
    settings,
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        workspace=table.database.workspace, user=other_user
    )
    handler = ExportHandler()
    job_start = datetime.now(tz=timezone.utc)
    half_file_duration = timedelta(minutes=int(settings.EXPORT_FILE_EXPIRE_MINUTES / 2))
    second_job_start = job_start + half_file_duration
    time_when_first_job_will_have_expired = job_start + timedelta(
        minutes=settings.EXPORT_FILE_EXPIRE_MINUTES * 1.1
    )
    with freeze_time(job_start):
        old_pending_job = handler.create_pending_export_job(
            user, table, None, {"exporter_type": "csv"}
        )
    with freeze_time(second_job_start):
        unexpired_other_user_job = handler.create_pending_export_job(
            other_user, table, None, {"exporter_type": "csv"}
        )
    with freeze_time(time_when_first_job_will_have_expired):
        handler.clean_up_old_jobs()

    storage_mock.delete.assert_not_called()

    old_pending_job.refresh_from_db()
    assert old_pending_job.state == EXPORT_JOB_EXPIRED_STATUS
    unexpired_other_user_job.refresh_from_db()
    assert unexpired_other_user_job.state == EXPORT_JOB_PENDING_STATUS


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_a_running_export_job_which_has_expired_will_be_stopped(
    get_storage_mock, data_fixture, settings
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        workspace=table.database.workspace, user=other_user
    )
    handler = ExportHandler()
    job_start = datetime.now(tz=timezone.utc)
    half_file_duration = timedelta(minutes=int(settings.EXPORT_FILE_EXPIRE_MINUTES / 2))
    second_job_start = job_start + half_file_duration
    time_when_first_job_will_have_expired = job_start + timedelta(
        minutes=settings.EXPORT_FILE_EXPIRE_MINUTES * 1.1
    )
    with freeze_time(job_start):
        long_running_job = handler.create_pending_export_job(
            user, table, None, {"exporter_type": "csv"}
        )
        long_running_job.state = EXPORT_JOB_EXPORTING_STATUS
        long_running_job.save()
    with freeze_time(second_job_start):
        unexpired_other_user_job = handler.create_pending_export_job(
            other_user, table, None, {"exporter_type": "csv"}
        )
    with freeze_time(time_when_first_job_will_have_expired):
        handler.clean_up_old_jobs()

    storage_mock.delete.assert_not_called()

    long_running_job.refresh_from_db()
    assert long_running_job.state == EXPORT_JOB_EXPIRED_STATUS
    unexpired_other_user_job.refresh_from_db()
    assert unexpired_other_user_job.state == EXPORT_JOB_PENDING_STATUS


@pytest.mark.django_db
def test_attempting_to_export_a_table_for_a_type_which_doesnt_support_it_fails(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = ExportHandler()

    class CantExportTableExporter(TableExporter):
        type = "no_tables"

        @property
        def file_extension(self) -> str:
            return ".no_tables"

        @property
        def can_export_table(self) -> bool:
            return False

        @property
        def supported_views(self) -> List[str]:
            return []

        @property
        def option_serializer_class(self):
            return BaseExporterOptionsSerializer

        @property
        def queryset_serializer_class(self):
            raise Exception("This should not even be run")

    table_exporter_registry.register(CantExportTableExporter())
    with pytest.raises(TableOnlyExportUnsupported):
        handler.create_pending_export_job(
            user, table, None, {"exporter_type": "no_tables"}
        )

    assert not ExportJob.objects.exists()


@pytest.mark.django_db
def test_attempting_to_export_a_view_for_a_type_which_doesnt_support_it_fails(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    handler = ExportHandler()

    class CantExportViewExporter(TableExporter):
        type = "not_grid_view"

        @property
        def file_extension(self) -> str:
            return ".not_grid_view"

        @property
        def can_export_table(self) -> bool:
            return False

        @property
        def supported_views(self) -> List[str]:
            return ["not_grid_view"]

        @property
        def option_serializer_class(self):
            return BaseExporterOptionsSerializer

        @property
        def queryset_serializer_class(self):
            raise Exception("This should not even be run")

    table_exporter_registry.register(CantExportViewExporter())
    with pytest.raises(ViewUnsupportedForExporterType):
        handler.create_pending_export_job(
            user, table, grid_view, {"exporter_type": "not_grid_view"}
        )

    assert not ExportJob.objects.exists()


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_an_export_job_which_fails_will_be_marked_as_a_failed_job(
    get_storage_mock,
    data_fixture,
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = ExportHandler()

    class BrokenTestFileExporter(TableExporter):
        type = "broken"

        @property
        def file_extension(self) -> str:
            return ".broken"

        @property
        def can_export_table(self) -> bool:
            return True

        @property
        def supported_views(self) -> List[str]:
            return []

        @property
        def option_serializer_class(self):
            return BaseExporterOptionsSerializer

        @property
        def queryset_serializer_class(self):
            raise Exception("Failed")

    class CancelledTestFileExporter(BrokenTestFileExporter):
        type = "cancelled"

        @property
        def queryset_serializer_class(self):
            raise ExportJobCanceledException()

    table_exporter_registry.register(BrokenTestFileExporter())
    table_exporter_registry.register(CancelledTestFileExporter())

    job_which_fails = handler.create_pending_export_job(
        user, table, None, {"exporter_type": "broken"}
    )
    with pytest.raises(Exception, match="Failed"):
        handler.run_export_job(job_which_fails)

    job_which_fails.refresh_from_db()
    assert job_which_fails.state == EXPORT_JOB_FAILED_STATUS
    assert job_which_fails.error == "Failed"
    table_exporter_registry.unregister("broken")

    # We do not expect an error because cancelled errors should be ignored.
    job_which_fails = handler.create_pending_export_job(
        user, table, None, {"exporter_type": "cancelled"}
    )
    handler.run_export_job(job_which_fails)


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_can_export_csv_without_header(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    _, contents = setup_table_and_run_export_decoding_result(
        data_fixture,
        storage_mock,
        options={"exporter_type": "csv", "csv_include_header": False},
    )
    expected = (
        "\ufeff"
        f"2,atest,A,02/01/2020 01:23,,-10.20,linked_row_1\r\n"
        f'1,test,B,02/01/2020 01:23,,10.20,"linked_row_1,linked_row_2"\r\n'
    )
    assert expected == contents


@pytest.mark.django_db
@pytest.mark.once_per_day_in_ci
@patch("baserow.core.storage.get_default_storage")
def test_can_export_csv_with_different_charsets(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    for _, charset in SUPPORTED_EXPORT_CHARSETS:
        _, contents = setup_table_and_run_export_decoding_result(
            data_fixture,
            storage_mock,
            options={"exporter_type": "csv", "export_charset": charset},
        )
        if charset == "utf-8":
            bom = "\ufeff"
        else:
            bom = ""
        expected = (
            bom + "id,text_field,option_field,date_field,File,Price,Customer\r\n"
            f"2,atest,A,02/01/2020 01:23,,-10.20,linked_row_1\r\n"
            f'1,test,B,02/01/2020 01:23,,10.20,"linked_row_1,linked_row_2"\r\n'
        )
        assert expected == contents


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_can_export_csv_with_different_column_separators(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock

    for _, col_sep in SUPPORTED_CSV_COLUMN_SEPARATORS:
        _, contents = setup_table_and_run_export_decoding_result(
            data_fixture,
            storage_mock,
            options={"exporter_type": "csv", "csv_column_separator": col_sep},
        )
        bom = "\ufeff"
        expected = (
            bom + "id,text_field,option_field,date_field,File,Price,Customer\r\n"
            f"2,atest,A,02/01/2020 01:23,,-10.20,linked_row_1\r\n"
            f"1,test,B,02/01/2020 01:23,,10.20,quote_replace\r\n"
        )
        expected = expected.replace(",", col_sep)
        if col_sep == ",":
            expected = expected.replace("quote_replace", '"linked_row_1,linked_row_2"')
        else:
            expected = expected.replace("quote_replace", "linked_row_1,linked_row_2")
        assert expected == contents


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_adding_more_rows_doesnt_increase_number_of_queries_run(
    get_storage_mock, data_fixture, django_assert_num_queries
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    add_row, add_linked_row, user, table, grid_view = setup_testing_table(data_fixture)

    # Ensure we test with linked rows and select options as they are the fields which
    # might potentially cause django's orm to do extra lookup queries.
    linked_row_1 = add_linked_row("linked_row_1")
    linked_row_2 = add_linked_row("linked_row_2")
    add_row(
        "test",
        "2020-02-01 01:23",
        "B",
        10.2,
        [{"name": "hashed_name.txt", "visible_name": "a.txt"}],
        [linked_row_1.id, linked_row_2.id],
    )
    add_row(
        "atest",
        "2020-02-01 01:23",
        "A",
        -10.2,
        [
            {"name": "hashed_name.txt", "visible_name": "a.txt"},
            {"name": "hashed_name2.txt", "visible_name": "b.txt"},
        ],
        [linked_row_1.id],
    )

    data_fixture.warm_cache_before_counting_queries()

    with CaptureQueriesContext(connection) as captured:
        run_export_job_with_mock_storage(table, grid_view, storage_mock, user)

    add_row(
        "atest",
        "2020-02-01 01:23",
        "A",
        -10.2,
        [
            {"name": "hashed_name.txt", "visible_name": "a.txt"},
            {"name": "hashed_name2.txt", "visible_name": "b.txt"},
        ],
        [linked_row_1.id],
    )
    with django_assert_num_queries(len(captured.captured_queries)):
        run_export_job_with_mock_storage(table, grid_view, storage_mock, user)


@pytest.mark.django_db
def test_creating_job_with_view_that_is_not_in_the_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user)
    handler = ExportHandler()

    with pytest.raises(ViewNotInTable):
        handler.create_pending_export_job(user, table, view, {"exporter_type": "csv"})


def run_export_job_with_mock_storage(
    table, grid_view, storage_mock, user, options=None
):
    if options is None:
        options = {"exporter_type": "csv"}

    if "export_charset" not in options:
        options["export_charset"] = "utf-8"

    storage_instance = MagicMock()
    storage_mock.return_value = storage_instance

    stub_file = BytesIO()
    storage_mock.open.return_value = stub_file
    close = stub_file.close
    stub_file.close = lambda: None
    handler = ExportHandler()
    job = handler.create_pending_export_job(user, table, grid_view, options)
    handler.run_export_job(job)
    actual = stub_file.getvalue().decode(options["export_charset"])
    close()
    return job, actual


def setup_testing_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, name="text_field", order=0, primary=True
    )
    option_field = data_fixture.create_single_select_field(
        table=table,
        name="option_field",
        order=1,
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )
    option_map = {
        "A": option_a,
        "B": option_b,
    }
    date_field = data_fixture.create_date_field(
        table=table,
        date_include_time=True,
        date_format="US",
        name="date_field",
        order=2,
    )
    file_field = data_fixture.create_file_field(table=table, name="File", order=3)
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=True,
        order=4,
    )
    table_2 = data_fixture.create_database_table(database=table.database)
    other_table_primary_text_field = data_fixture.create_text_field(
        table=table_2, name="text_field", primary=True
    )
    link_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=table_2,
        order=5,
    )
    grid_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_sort(view=grid_view, field=text_field, order="ASC")
    row_handler = RowHandler()

    def add_linked_row(text):
        return row_handler.create_row(
            user=user,
            table=table_2,
            values={
                other_table_primary_text_field.id: text,
            },
        )

    model = table.get_model()

    def add_row(text, date, option, price, files, linked_row_ids):
        row = model.objects.create(
            **{
                f"field_{text_field.id}": text,
                f"field_{date_field.id}": _parse_datetime(date),
                f"field_{option_field.id}": option_map[option],
                f"field_{price_field.id}": price,
                f"field_{file_field.id}": files,
            },
        )
        getattr(row, f"field_{link_field.id}").add(*linked_row_ids)

    return add_row, add_linked_row, user, table, grid_view


def setup_table_and_run_export_decoding_result(
    data_fixture, storage_mock, options=None
):
    add_row, add_linked_row, user, table, grid_view = setup_testing_table(data_fixture)

    linked_row_1 = add_linked_row("linked_row_1")
    linked_row_2 = add_linked_row("linked_row_2")
    add_row(
        "test",
        "2020-02-01 01:23",
        "B",
        10.2,
        [],
        [linked_row_1.id, linked_row_2.id],
    )
    add_row(
        "atest",
        "2020-02-01 01:23",
        "A",
        -10.2,
        [],
        [linked_row_1.id],
    )

    return run_export_job_with_mock_storage(
        table, grid_view, storage_mock, user, options=options
    )


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_a_column_without_a_grid_view_option_has_an_option_made_and_is_exported(
    get_storage_mock, data_fixture
):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_with_an_option = data_fixture.create_text_field(table=table, name="field_a")
    field_without_an_option = data_fixture.create_text_field(
        table=table,
        name="field_b",
    )
    grid_view = GridView.objects.create(table=table, order=0, name="grid_view")
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{field_with_an_option.id}": "a",
            f"field_{field_without_an_option.id}": "b",
        },
    )
    data_fixture.create_grid_view_field_option(
        grid_view=grid_view, field=field_with_an_option, order=1
    )

    assert GridViewFieldOptions.objects.count() == 1

    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,field_a,field_b\r\n" "1,a,b\r\n"
    assert contents == expected

    assert GridViewFieldOptions.objects.count() == 2
    assert GridViewFieldOptions.objects.filter(field=field_without_an_option).exists()


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_action_done_is_emitted_when_the_export_finish(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    with patch("baserow.core.action.signals.action_done.send") as send_mock:
        run_export_job_with_mock_storage(table, None, storage_mock, user)

        assert send_mock.call_count == 1
        assert send_mock.call_args[1]["action_type"].type == "export_table"
        action_type = send_mock.call_args[1]["action_type"]
        params = send_mock.call_args[1]["action_params"]
        assert action_type.get_long_description(params).startswith("Table")

        grid_view = GridView.objects.create(table=table, order=0, name="grid_view")
        run_export_job_with_mock_storage(table, grid_view, storage_mock, user)

        assert send_mock.call_count == 2
        assert send_mock.call_args[1]["action_type"].type == "export_table"
        action_type = send_mock.call_args[1]["action_type"]
        params = send_mock.call_args[1]["action_params"]
        assert action_type.get_long_description(params).startswith("View")


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_csv_is_escaped(get_storage_mock, data_fixture):
    storage_mock = MagicMock()
    get_storage_mock.return_value = storage_mock
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    grid_view = data_fixture.create_grid_view(table=table)
    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "=1+2",
        },
    )
    _, contents = run_export_job_with_mock_storage(table, grid_view, storage_mock, user)
    bom = "\ufeff"
    expected = bom + "id,text_field\r\n1,'=1+2\r\n"
    assert contents == expected
