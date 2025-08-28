from datetime import date, datetime, timedelta, timezone
from functools import partial
from io import BytesIO
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile
from zoneinfo import ZoneInfo

from django.core.files.storage import FileSystemStorage
from django.urls import reverse

import pytest
from baserow_premium.ical_utils import build_calendar
from baserow_premium.views.exceptions import CalendarViewHasNoDateField
from baserow_premium.views.handler import (
    generate_per_day_intervals,
    get_rows_grouped_by_date_field,
    to_midnight,
)
from baserow_premium.views.models import CalendarView, CalendarViewFieldOptions
from icalendar import Calendar
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.fields.exceptions import FieldNotInTable
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.management.commands.fill_table_rows import fill_table_rows
from baserow.contrib.database.views.actions import UpdateViewActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    setup_interesting_test_table,
)


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_date_field_same_table(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)
    date_field_diff_table = premium_data_fixture.create_date_field()

    view_handler = ViewHandler()

    with pytest.raises(FieldNotInTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="calendar",
            date_field=date_field_diff_table,
        )

    with pytest.raises(FieldNotInTable):
        view_handler.create_view(
            user=user,
            table=table,
            type_name="calendar",
            date_field=date_field_diff_table.id,
        )

    calendar_view = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )

    view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=None,
    )

    with pytest.raises(FieldNotInTable):
        view_handler.update_view(
            user=user,
            view=calendar_view,
            date_field=date_field_diff_table,
        )

    with pytest.raises(FieldNotInTable):
        view_handler.update_view(
            user=user,
            view=calendar_view,
            date_field=date_field_diff_table.id,
        )

    view_handler.update_view(
        user=user,
        view=calendar_view,
        date_field=date_field,
    )

    view_handler.update_view(
        user=user,
        view=calendar_view,
        date_field=None,
    )


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_import_export(premium_data_fixture, tmpdir):
    user = premium_data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    table = premium_data_fixture.create_database_table(user=user)
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )
    field_option = premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar_view, field=date_field, hidden=True, order=1
    )
    calendar_view_type = view_type_registry.get("calendar")

    files_buffer = BytesIO()
    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        serialized = calendar_view_type.export_serialized(
            calendar_view,
            ImportExportConfig(include_permission_data=False),
            files_zip=files_zip,
            storage=storage,
        )

    assert serialized["id"] == calendar_view.id
    assert serialized["type"] == "calendar"
    assert serialized["name"] == calendar_view.name
    assert serialized["order"] == 0
    assert serialized["date_field_id"] == date_field.id
    assert len(serialized["field_options"]) == 1
    assert serialized["field_options"][0]["id"] == field_option.id
    assert serialized["field_options"][0]["field_id"] == field_option.field_id
    assert serialized["field_options"][0]["hidden"] is True
    assert serialized["field_options"][0]["order"] == 1

    imported_date_field = premium_data_fixture.create_date_field(table=table)

    id_mapping = {
        "database_fields": {
            date_field.id: imported_date_field.id,
        }
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_calendar_view = calendar_view_type.import_serialized(
            calendar_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    assert calendar_view.id != imported_calendar_view.id
    assert calendar_view.name == imported_calendar_view.name
    assert calendar_view.order == imported_calendar_view.order
    assert calendar_view.date_field_id != imported_calendar_view.date_field_id

    imported_field_options = imported_calendar_view.get_field_options()
    assert len(imported_field_options) == 1
    imported_field_option = imported_field_options[0]
    assert field_option.id != imported_field_option.id
    assert imported_date_field.id == imported_field_option.field_id
    assert field_option.hidden == imported_field_option.hidden
    assert field_option.order == imported_field_option.order


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_created(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table, primary=True)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)
    premium_data_fixture.create_text_field(table=table)

    handler = ViewHandler()
    handler.create_view(user, table=table, type_name="calendar")

    all_field_options = (
        CalendarViewFieldOptions.objects.all()
        .order_by("field_id")
        .values_list("hidden", flat=True)
    )
    assert list(all_field_options) == [False, True, True, True]


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_convert_date_field_to_another(premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, _, _, context = setup_interesting_test_table(
        premium_data_fixture, user=user
    )
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, date_field=date_field
    )

    specific_fields = [f.specific for f in table.field_set.all()]
    can_represent_date_fields = [
        f
        for f in specific_fields
        if field_type_registry.get_by_model(f).can_represent_date(f)
    ]
    not_compatible_field_type = field_type_registry.get("text")

    for date_field in can_represent_date_fields:
        date_field_type = field_type_registry.get_by_model(date_field)
        FieldHandler().update_field(
            user=user, field=date_field, new_type_name=date_field_type.type
        )
        calendar_view.refresh_from_db()
        assert calendar_view.date_field_id is not None

    date_field = FieldHandler().update_field(
        user=user, field=date_field, new_type_name=not_compatible_field_type.type
    )
    calendar_view.refresh_from_db()
    with pytest.raises(CalendarViewHasNoDateField):
        get_rows_grouped_by_date_field(
            user,
            calendar_view,
            date_field,
            from_timestamp=datetime.now(tz=timezone.utc),
            to_timestamp=datetime.now(tz=timezone.utc) + timedelta(days=1),
            user_timezone="UTC",
        )


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_visible_fields_options_no_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False, order=3
    )

    calendar_field_type = view_type_registry.get("calendar")

    fields = calendar_field_type.get_visible_field_options_in_order(calendar)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_visible_fields_options_hidden_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar.date_field = date_field
    calendar.save()

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=date_field, hidden=True, order=0
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False, order=3
    )

    calendar_field_type = view_type_registry.get("calendar")

    fields = calendar_field_type.get_visible_field_options_in_order(calendar)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [date_field.id, field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_visible_fields_options_visible_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar.date_field = date_field
    calendar.save()

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=date_field, hidden=False, order=0
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False, order=3
    )

    calendar_field_type = view_type_registry.get("calendar")

    fields = calendar_field_type.get_visible_field_options_in_order(calendar)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [date_field.id, field_visible.id]


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_visible_fields_options_without_date_field_option(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    date_field = premium_data_fixture.create_date_field(table=table)
    calendar.date_field = date_field
    calendar.save()

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True, order=2
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False, order=3
    )

    calendar_field_type = view_type_registry.get("calendar")

    fields = calendar_field_type.get_visible_field_options_in_order(calendar)
    field_ids = [field.field_id for field in fields]
    assert field_ids == [field_visible.id, date_field.id]


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_no_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)
    calendar.calendarviewfieldoptions_set.all().delete()

    calendar_field_type = view_type_registry.get("calendar")
    assert len(calendar_field_type.get_hidden_fields(calendar)) == 0


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_without_date_field_option(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)
    calendar.calendarviewfieldoptions_set.all().delete()

    date_field = premium_data_fixture.create_date_field(table=table)

    calendar.date_field = date_field
    calendar.save()

    calendar_field_type = view_type_registry.get("calendar")
    assert len(calendar_field_type.get_hidden_fields(calendar)) == 0


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_with_hidden_date_field(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)
    calendar.calendarviewfieldoptions_set.all().delete()

    date_field = premium_data_fixture.create_date_field(table=table)

    calendar.date_field = date_field
    calendar.save()

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=date_field, hidden=True
    )

    calendar_field_type = view_type_registry.get("calendar")
    assert len(calendar_field_type.get_hidden_fields(calendar)) == 0


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_with_hidden_and_visible_fields(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table)
    calendar.calendarviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False
    )

    calendar_field_type = view_type_registry.get("calendar")

    results = calendar_field_type.get_hidden_fields(calendar)
    assert len(results) == 2
    assert field_hidden.id in results
    assert field_no_field_option.id in results


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_with_field_ids_to_check(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table)
    calendar.calendarviewfieldoptions_set.all().delete()

    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False
    )

    calendar_field_type = view_type_registry.get("calendar")

    results = calendar_field_type.get_hidden_fields(
        calendar, field_ids_to_check=[field_hidden.id, field_visible.id]
    )
    assert len(results) == 1
    assert field_hidden.id in results


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_get_hidden_fields_all_fields(
    premium_data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    calendar = premium_data_fixture.create_calendar_view(table=table, date_field=None)

    date_field = premium_data_fixture.create_date_field(table=table)
    field_hidden = premium_data_fixture.create_text_field(table=table)
    field_visible = premium_data_fixture.create_text_field(table=table)
    field_no_field_option = premium_data_fixture.create_text_field(table=table)

    calendar.date_field = date_field
    calendar.save()

    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=date_field, hidden=True
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_hidden, hidden=True
    )
    premium_data_fixture.create_calendar_view_field_option(
        calendar_view=calendar, field=field_visible, hidden=False
    )

    calendar_field_type = view_type_registry.get("calendar")

    with django_assert_num_queries(2):
        results = calendar_field_type.get_hidden_fields(calendar)
        assert len(results) == 2
        assert date_field.id not in results
        assert field_hidden.id in results
        assert field_no_field_option.id in results


def case(**kwargs):
    return kwargs


def row_number(idx):
    return idx


GET_ROWS_GROUPED_BY_DATE_FIELD_CASES = [
    (
        "basic date field test case",
        case(
            field=("date", "date"),
            rows=["2023-01-10", "2023-01-12"],
            from_timestamp=datetime(2023, 1, 9, 0, 0, 0, 0),
            to_timestamp=datetime(2023, 1, 11, 0, 0, 0, 0),
            user_timezone="UTC",
            expected_result={
                "2023-01-09": {"count": 0, "results": []},
                "2023-01-10": {"count": 1, "results": [row_number(0)]},
                "2023-01-11": {"count": 0, "results": []},
            },
        ),
    ),
    (
        "basic datetime field test case",
        case(
            field=("datetime", {"type": "date", "date_include_time": True}),
            rows=["2023-01-10 00:00", "2023-01-09 23:59"],
            from_timestamp=datetime(2023, 1, 10, 0, 0, 0, 0),
            to_timestamp=datetime(2023, 1, 11, 0, 0, 0, 0),
            user_timezone="UTC",
            expected_result={
                "2023-01-10": {"count": 1, "results": [row_number(0)]},
            },
        ),
    ),
    (
        "basic datetime field test case where user timezone changes result",
        case(
            field=("datetime", {"type": "date", "date_include_time": True}),
            rows=["2023-01-09 23:59", "2023-01-10 00:00"],
            from_timestamp=datetime(2023, 1, 9, 23, 0, 0, 0),
            to_timestamp=datetime(2023, 1, 10, 1, 0, 0, 0),
            user_timezone="CET",
            expected_result={
                "2023-01-10": {"count": 2, "results": [row_number(0), row_number(1)]},
            },
        ),
    ),
    (
        "datetime field test case where user timezone overriden by field timezone",
        case(
            field=(
                "datetime",
                {
                    "type": "date",
                    "date_include_time": True,
                    "date_force_timezone": "Etc/GMT-2",
                },
            ),
            rows=["2023-01-09 23:59", "2023-01-10 00:00"],
            from_timestamp=datetime(2023, 1, 9, 23, 0, 0, 0),
            to_timestamp=datetime(2023, 1, 10, 1, 0, 0, 0),
            user_timezone="CET",
            expected_result={
                "2023-01-10": {"count": 2, "results": [row_number(0), row_number(1)]},
            },
        ),
    ),
    (
        "datetime field test case when CET clocks go forwards",
        case(
            field=(
                "datetime",
                {
                    "type": "date",
                    "date_include_time": True,
                },
            ),
            rows=[
                "2022-03-26 22:59",  # 26th Europe/Amsterdam (UTC+1)
                "2022-03-26 23:00",  # 27th Europe/Amsterdam (UTC+1)
                "2022-03-27 21:59",  # 27th Europe/Amsterdam (UTC+2)
                "2022-03-27 22:00",  # 28th Europe/Amsterdam (UTC+2)
            ],
            from_timestamp=datetime(2022, 3, 26, 0, 0, 0, 0),
            to_timestamp=datetime(2022, 3, 28, 1, 0, 0, 0),
            user_timezone="Europe/Amsterdam",
            expected_result={
                "2022-03-26": {"count": 1, "results": [row_number(0)]},
                "2022-03-27": {
                    "count": 2,
                    "results": [row_number(1), row_number(2)],
                },
                "2022-03-28": {"count": 1, "results": [row_number(3)]},
            },
        ),
    ),
    (
        "date field test case ignores user supplied timezone",
        case(
            field=(
                "datetime",
                {
                    "type": "date",
                    "date_include_time": False,
                },
            ),
            rows=[
                "2022-03-26",
                "2022-03-27",
            ],
            from_timestamp=datetime(2022, 3, 26, 0, 0, 0, 0),
            to_timestamp=datetime(2022, 3, 27, 23, 0, 0, 0),
            user_timezone="Europe/Amsterdam",
            expected_result={
                "2022-03-26": {"count": 1, "results": [row_number(0)]},
                "2022-03-27": {
                    "count": 1,
                    "results": [row_number(1)],
                },
            },
        ),
    ),
]


@pytest.mark.django_db
@pytest.mark.view_calendar
@pytest.mark.parametrize("name,test_case", GET_ROWS_GROUPED_BY_DATE_FIELD_CASES)
def test_calendar_timezone_test_cases(
    premium_data_fixture, name, test_case, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table, fields, rows = premium_data_fixture.build_table(
        columns=[test_case["field"]], rows=[[v] for v in test_case["rows"]]
    )
    field = fields[0]
    calendar_view = premium_data_fixture.create_calendar_view(
        table=table, date_field=field
    )

    grouped_rows = get_rows_grouped_by_date_field(
        user,
        calendar_view,
        field,
        from_timestamp=test_case["from_timestamp"],
        to_timestamp=test_case["to_timestamp"],
        user_timezone=test_case["user_timezone"],
        model=type(rows[0]),
    )
    for date_bucket_key, result in test_case["expected_result"].items():
        test_case["expected_result"][date_bucket_key]["results"] = [
            rows[i] for i in test_case["expected_result"][date_bucket_key]["results"]
        ]
    assert dict(grouped_rows) == test_case["expected_result"]


@pytest.mark.view_calendar
def test_to_midnight():
    assert to_midnight(datetime(2023, 1, 9, 23, 0, 0, 0)) == datetime(
        2023, 1, 9, 0, 0, 0, 0
    )
    assert to_midnight(datetime(2023, 1, 9, 0, 0, 0, 0)) == datetime(
        2023, 1, 9, 0, 0, 0, 0
    )


@pytest.mark.view_calendar
def test_to_midnight_with_tz():
    amsterdam_tz = ZoneInfo("Europe/Amsterdam")
    tz_in_amsterdam_tz = datetime(2022, 1, 9, 23, 0, 0, 0, tzinfo=amsterdam_tz)

    # The time we are converting to midnight
    assert str(tz_in_amsterdam_tz) == "2022-01-09 23:00:00+01:00"
    assert (
        str(tz_in_amsterdam_tz.astimezone(timezone.utc)) == "2022-01-09 22:00:00+00:00"
    )

    midnight_amsterdam = to_midnight(tz_in_amsterdam_tz)
    assert str(midnight_amsterdam) == "2022-01-09 00:00:00+01:00"
    assert (
        str(midnight_amsterdam.astimezone(timezone.utc)) == "2022-01-08 23:00:00+00:00"
    )


@pytest.mark.view_calendar
def test_to_midnight_with_tz_on_dst_boundary():
    melbourne_tz = ZoneInfo("Australia/Melbourne")
    dt = datetime(2012, 4, 1, 3, 0, 0, 0, tzinfo=melbourne_tz)

    assert str(dt) == "2012-04-01 03:00:00+10:00"
    assert str(dt.astimezone(timezone.utc)) == "2012-03-31 17:00:00+00:00"

    midnight_amsterdam = to_midnight(dt)
    assert str(midnight_amsterdam) == "2012-04-01 00:00:00+11:00"
    assert (
        str(midnight_amsterdam.astimezone(timezone.utc)) == "2012-03-31 13:00:00+00:00"
    )


@pytest.mark.view_calendar
def test_generate_per_day_intervals_backwards_to_from():
    melbourne_tz = ZoneInfo("Australia/Melbourne")
    dt = datetime(2012, 4, 1, 3, 0, 0, 0, tzinfo=melbourne_tz)
    assert generate_per_day_intervals(dt, dt - timedelta(hours=1)) == []


@pytest.mark.view_calendar
def test_generate_per_day_intervals_same_date_without_tz():
    dt = datetime(2012, 4, 1, 3, 0, 0, 0)
    assert generate_per_day_intervals(dt, dt + timedelta(hours=1)) == [
        (
            datetime(2012, 4, 1, 3, 0),
            datetime(2012, 4, 1, 4, 0),
        )
    ]


@pytest.mark.view_calendar
def test_generate_per_day_intervals_same_date_with_tz():
    melbourne_tz = ZoneInfo("Australia/Melbourne")
    dt = datetime(2012, 4, 1, 3, 0, 0, 0, tzinfo=melbourne_tz)
    assert generate_per_day_intervals(dt, dt + timedelta(hours=1)) == [
        (
            datetime(2012, 4, 1, 3, 0, tzinfo=melbourne_tz),
            datetime(2012, 4, 1, 4, 0, tzinfo=melbourne_tz),
        )
    ]


@pytest.mark.view_calendar
def test_generate_per_day_intervals_crossing_one_midnight_with_tz():
    melbourne_tz = ZoneInfo("Australia/Melbourne")
    dt = datetime(2012, 3, 31, 23, 0, 0, 0, tzinfo=melbourne_tz)
    assert generate_per_day_intervals(dt, dt + timedelta(hours=2)) == [
        (
            datetime(
                2012,
                3,
                31,
                23,
                0,
                tzinfo=melbourne_tz,
            ),
            datetime(
                2012,
                4,
                1,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
        ),
        (
            datetime(
                2012,
                4,
                1,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
            datetime(
                2012,
                4,
                1,
                1,
                0,
                tzinfo=melbourne_tz,
            ),
        ),
    ]


@pytest.mark.view_calendar
def test_generate_per_day_intervals_crossing_two_midnights_with_tz():
    melbourne_tz = ZoneInfo("Australia/Melbourne")
    dt = datetime(2012, 3, 31, 23, 0, 0, 0, tzinfo=melbourne_tz)
    assert generate_per_day_intervals(dt, dt + timedelta(hours=26)) == [
        (
            datetime(
                2012,
                3,
                31,
                23,
                0,
                tzinfo=melbourne_tz,
            ),
            datetime(
                2012,
                4,
                1,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
        ),
        (
            datetime(
                2012,
                4,
                1,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
            datetime(
                2012,
                4,
                2,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
        ),
        (
            datetime(
                2012,
                4,
                2,
                0,
                0,
                tzinfo=melbourne_tz,
            ),
            datetime(
                2012,
                4,
                2,
                1,
                0,
                tzinfo=melbourne_tz,
            ),
        ),
    ]


@pytest.mark.view_calendar
def test_generate_per_day_intervals_for_dates():
    dt = date(2012, 3, 31)
    assert generate_per_day_intervals(dt, dt + timedelta(days=2)) == [
        (
            date(
                2012,
                3,
                31,
            ),
            date(
                2012,
                4,
                1,
            ),
        ),
        (
            date(
                2012,
                4,
                1,
            ),
            date(
                2012,
                4,
                2,
            ),
        ),
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.view_calendar
def test_can_undo_redo_update_calendar_view(data_fixture, premium_data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = premium_data_fixture.create_database_table(user=user)
    date_field_1 = premium_data_fixture.create_date_field(table=table)
    date_field_2 = premium_data_fixture.create_date_field(table=table)
    calendar_view = premium_data_fixture.create_calendar_view(table=table)

    original_calendar_data = {
        "name": "Test Original",
        "filter_type": "AND",
        "filters_disabled": False,
        "date_field": date_field_1,
    }

    calendar_view_with_changes = ViewHandler().update_view(
        user, calendar_view, **original_calendar_data
    )
    calendar_view = calendar_view_with_changes.updated_view_instance

    assert calendar_view.name == original_calendar_data["name"]
    assert calendar_view.date_field_id == original_calendar_data["date_field"].id

    new_calendar_data = {
        "name": "Test New",
        "filter_type": "OR",
        "filters_disabled": True,
        "date_field": date_field_2,
    }

    calendar_view = action_type_registry.get_by_type(UpdateViewActionType).do(
        user, calendar_view, **new_calendar_data
    )

    assert calendar_view.name == new_calendar_data["name"]
    assert calendar_view.date_field_id == new_calendar_data["date_field"].id

    action_undone = ActionHandler.undo(
        user, [ViewActionScopeType.value(calendar_view.id)], session_id
    )

    calendar_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_undone, [UpdateViewActionType])

    assert calendar_view.name == original_calendar_data["name"]
    assert calendar_view.date_field_id == original_calendar_data["date_field"].id

    action_redone = ActionHandler.redo(
        user, [ViewActionScopeType.value(calendar_view.id)], session_id
    )

    calendar_view.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_redone, [UpdateViewActionType])

    assert calendar_view.name == new_calendar_data["name"]
    assert calendar_view.date_field_id == new_calendar_data["date_field"].id


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_hierarchy(premium_data_fixture):
    user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(user=user)
    app = premium_data_fixture.create_database_application(
        workspace=workspace, name="Test 1"
    )
    table = premium_data_fixture.create_database_table(database=app)
    premium_data_fixture.create_text_field(table=table)

    calendar_view = premium_data_fixture.create_kanban_view(
        table=table,
        user=user,
    )

    assert calendar_view.get_parent() == table
    assert calendar_view.get_root() == workspace
    calendar_view_field_options = calendar_view.get_field_options()[0]
    assert calendar_view_field_options.get_parent() == calendar_view
    assert calendar_view_field_options.get_root() == workspace


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_timestamps(
    premium_data_fixture, api_client, data_fixture
):
    """
    Test ical feed with calendar with datetime field
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=True,
    )
    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()
    NUM_EVENTS = 5

    amsterdam = ZoneInfo("Europe/Amsterdam")
    start = datetime.now(tz=amsterdam).replace(microsecond=0)

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=1, hours=curr),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    make_values(NUM_EVENTS)

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url
    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )
    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]
    calendar_view.refresh_from_db()
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content
    # parse generated feed
    feed = Calendar.from_ical(resp.content)
    assert feed
    assert feed.get("PRODID") == "Baserow / baserow.io"
    evstart = [ev.get("DTSTART") for ev in feed.walk("VEVENT")]

    assert len(evstart) == NUM_EVENTS
    for idx, elm in enumerate(evstart):
        # elm.dt is tz-aware, but tz will be +00:00
        assert elm.dt.utcoffset() == timedelta(0), elm.dt.utcoffset()
        assert elm.dt - (start + timedelta(days=1, hours=idx)) == timedelta(0)


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_view_ical_feed_dates(premium_data_fixture, api_client, data_fixture):
    """
    Test ical feed with calendar with date field
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_text_field(table=table, user=user)
    field_extra = data_fixture.create_text_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )
    all_fields = [field_title, field_description, field_extra, field_num, date_field]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()
    NUM_EVENTS = 5

    start = date.today()

    def make_values(num):
        curr = 0
        field_names = [f"field_{f.id}" for f in all_fields]

        while curr < num:
            values = [
                f"title {curr}",
                f"description {curr}",
                f"extra {curr}",
                curr,
                start + timedelta(days=1 + curr),
            ]
            curr += 1
            row = dict(zip(field_names, values))
            tmodel.objects.create(**row)

    make_values(NUM_EVENTS)

    assert not calendar_view.ical_public
    assert not calendar_view.ical_feed_url
    req_get = partial(api_client.get, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    req_patch = partial(
        api_client.patch, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    # make ical feed public
    resp: Response = req_patch(
        reverse("api:database:views:item", kwargs={"view_id": calendar_view.id}),
        {"ical_public": True},
    )
    assert resp.status_code == HTTP_200_OK
    assert resp.data["ical_feed_url"]
    calendar_view.refresh_from_db()
    resp = req_get(
        reverse(
            "api:database:views:calendar:calendar_ical_feed",
            kwargs={"ical_slug": calendar_view.ical_slug},
        )
    )

    assert resp.status_code == HTTP_200_OK
    assert resp.headers.get("content-type") == "text/calendar", resp.headers
    assert resp.content
    # parse generated feed
    feed = Calendar.from_ical(resp.content)
    assert feed
    assert feed.get("PRODID") == "Baserow / baserow.io"
    evstart = [ev.get("DTSTART") for ev in feed.walk("VEVENT")]

    assert len(evstart) == NUM_EVENTS
    for idx, elm in enumerate(evstart):
        # elm.dt is a date
        assert isinstance(elm.dt, date)
        assert elm.dt == start + timedelta(days=1 + idx)


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_ical_utils_queries(
    premium_data_fixture, data_fixture, django_assert_num_queries
):
    """
    Test For ical utils queries issued.
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user)
    field_title = data_fixture.create_text_field(table=table, user=user)
    field_description = data_fixture.create_long_text_field(table=table, user=user)
    field_extra = data_fixture.create_rating_field(table=table, user=user)
    field_num = data_fixture.create_number_field(table=table, user=user)
    field_num_2 = data_fixture.create_number_field(table=table, user=user)
    field_num_3 = data_fixture.create_number_field(table=table, user=user)
    field_bool = data_fixture.create_boolean_field(table=table, user=user)
    field_duration = data_fixture.create_duration_field(table=table, user=user)
    field_ai = premium_data_fixture.create_ai_field(table=table, user=user)

    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )

    all_fields = [
        field_title,
        field_description,
        field_extra,
        field_num,
        date_field,
        field_num_2,
        field_num_3,
        field_bool,
        field_duration,
        field_ai,
    ]

    view_handler = ViewHandler()

    calendar_view: CalendarView = view_handler.create_view(
        user=user,
        table=table,
        type_name="calendar",
        date_field=date_field,
    )
    tmodel = table.get_model()
    NUM_EVENTS = 5

    def make_values(num, for_model, for_fields):
        fill_table_rows(num, table)

    make_values(NUM_EVENTS, tmodel, all_fields)
    calendar_view.date_field_id = None
    all_items_query = tmodel.objects.all().order_by("id")

    with django_assert_num_queries(0):
        with pytest.raises(CalendarViewHasNoDateField) as err:
            build_calendar(all_items_query, calendar_view)

    view_handler.update_field_options(
        view=calendar_view,
        field_options={f.id: {"hidden": True} for f in all_fields},
    )
    view_handler.update_field_options(
        view=calendar_view,
        field_options={
            field_title.id: {"hidden": False},
            field_num.id: {"hidden": False},
            field_duration.id: {"hidden": False},
        },
    )

    calendar_view.refresh_from_db()
    assert all_items_query.count() == NUM_EVENTS
    # 8 fields in total:
    # - 2 for resolve calendar_view.date_field.specific
    # - 1 for resolve calendar_view.table
    # - 1 for a visible fields list for this calendarview
    # - 1 for long text field related fields
    # - 1 for numberfield related fields
    # - 1 for durationfield related fields
    # - 1 for all_items_query
    with django_assert_num_queries(8) as ctx:
        cal = build_calendar(all_items_query, calendar_view)

    assert len(list(cal.walk("VEVENT"))) == len(all_items_query)
    for idx, evt in enumerate(cal.walk("VEVENT")):
        assert evt.get("uid")
        uid_url = urlparse(evt.get("uid"))
        assert uid_url.netloc
        assert uid_url.path == (
            f"/database/{table.database_id}/table/{table.id}/{calendar_view.id}/row/{idx+1}"
        )
        assert evt.get("summary")

    view_handler.update_field_options(
        view=calendar_view,
        field_options={
            field_title.id: {"hidden": False},
            field_num.id: {"hidden": False},
            field_extra.id: {"hidden": False},
            field_description.id: {"hidden": False},
            field_duration.id: {"hidden": False},
        },
    )

    calendar_view.refresh_from_db()
    # 10 queries:
    # - 2 for resolve calendar_view.date_field.specific
    # - 1 for resolve calendar_view.table
    # - 1 for a visible fields list for this calendarview
    # - 1 for long text field related fields
    # - 1 for text field
    # - 1 for rating field
    # - 1 for numberfield related fields
    # - 1 for durationfield related fields
    # - 1 for all_items_query
    with django_assert_num_queries(10) as ctx:
        cal = build_calendar(all_items_query.all(), calendar_view)


@pytest.mark.django_db
@pytest.mark.view_calendar
def test_calendar_after_delete_field_set_date_field_to_none(
    premium_data_fixture, data_fixture, django_assert_num_queries
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    date_field = premium_data_fixture.create_date_field(
        table=table,
        date_include_time=False,
    )

    view = premium_data_fixture.create_calendar_view(table=table, date_field=date_field)

    FieldHandler().delete_field(user, date_field)
    view.refresh_from_db()

    assert view.date_field is None
