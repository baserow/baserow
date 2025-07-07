from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

import pytest
from pytest_unordered import unordered

from baserow.contrib.database.fields.field_types import DateFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import DateField, TextField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.psycopg import is_psycopg3
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_date_field_type_prepare_value(data_fixture):
    d = DateFieldType()

    f = data_fixture.create_date_field(date_include_time=True, date_format="ISO")
    amsterdam = ZoneInfo("Europe/Amsterdam")
    utc = timezone.utc
    expected_date = datetime(2020, 4, 10, 0, 0, 0, tzinfo=utc)
    expected_datetime = datetime(2020, 4, 10, 12, 30, 30, tzinfo=utc)

    with pytest.raises(ValidationError):
        assert d.prepare_value_for_db(f, "TEST")

    assert d.prepare_value_for_db(f, None) is None

    unprepared_datetime = datetime(2020, 4, 10, 14, 30, 30, tzinfo=amsterdam)
    assert d.prepare_value_for_db(f, unprepared_datetime) == expected_datetime

    unprepared_datetime = datetime(2020, 4, 10, 12, 30, 30, tzinfo=utc)
    assert d.prepare_value_for_db(f, unprepared_datetime) == expected_datetime

    unprepared_datetime = datetime(2020, 4, 10, 12, 30, 30)
    assert d.prepare_value_for_db(f, unprepared_datetime) == expected_datetime

    unprepared_date = date(2020, 4, 10)
    assert d.prepare_value_for_db(f, unprepared_date) == expected_date

    assert d.prepare_value_for_db(f, "2020-04-10") == expected_date
    assert d.prepare_value_for_db(f, "2020-04-11") != expected_date
    assert d.prepare_value_for_db(f, "2020-04-10 12:30:30") == expected_datetime
    assert d.prepare_value_for_db(f, "2020-04-10 00:30:30 PM") == expected_datetime

    f = data_fixture.create_date_field(date_include_time=False, date_format="ISO")
    expected_date = date(2020, 4, 10)

    unprepared_datetime = datetime(2020, 4, 10, 14, 30, 30)
    assert d.prepare_value_for_db(f, unprepared_datetime) == expected_date

    unprepared_datetime = datetime(2020, 4, 10, 14, 30, 30, tzinfo=amsterdam)
    assert d.prepare_value_for_db(f, unprepared_datetime) == expected_date

    assert d.prepare_value_for_db(f, "2020-04-10") == expected_date
    assert d.prepare_value_for_db(f, "2020-04-11") != expected_date
    assert d.prepare_value_for_db(f, "2020-04-10 12:30:30") == expected_date
    assert d.prepare_value_for_db(f, "2020-04-10 00:30:30 PM") == expected_date
    assert d.prepare_value_for_db(f, "2020-04-10T12:30:30.12345") == expected_date
    assert d.prepare_value_for_db(f, "2020-04-10T12:30:30.12345+02:00") == expected_date

    f = data_fixture.create_date_field(date_include_time=False, date_format="US")
    assert d.prepare_value_for_db(f, "04/10/2020") == date(2020, 4, 10)
    assert d.prepare_value_for_db(f, "2020-04-10") == date(2020, 4, 10)

    f = data_fixture.create_date_field(date_include_time=False, date_format="EU")
    assert d.prepare_value_for_db(f, "04/10/2020") == date(2020, 10, 4)
    assert d.prepare_value_for_db(f, "2020-04-10") == date(2020, 4, 10)


@pytest.mark.django_db
def test_date_field_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    amsterdam = ZoneInfo("Europe/Amsterdam")

    date_field_1 = field_handler.create_field(
        user=user, table=table, type_name="date", name="Date", date_format="ISO"
    )
    date_field_2 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        name="Datetime",
        date_include_time=True,
        date_format="ISO",
    )

    assert date_field_1.date_include_time is False
    assert date_field_2.date_include_time is True
    assert len(DateField.objects.all()) == 2

    model = table.get_model(attribute_names=True)

    row = row_handler.create_row(user=user, table=table, values={}, model=model)
    assert row.date is None
    assert row.datetime is None

    row = row_handler.create_row(
        user=user,
        table=table,
        values={"date": "2020-4-1", "datetime": "2020-4-1 12:30:30"},
        model=model,
    )
    row.refresh_from_db()
    assert row.date == date(2020, 4, 1)
    assert row.datetime == datetime(2020, 4, 1, 12, 30, 30, tzinfo=timezone.utc)

    row = row_handler.create_row(
        user=user,
        table=table,
        values={"datetime": datetime(2020, 4, 1, 12, 30, 30, tzinfo=amsterdam)},
        model=model,
    )
    row.refresh_from_db()
    assert row.date is None
    assert row.datetime == datetime(2020, 4, 1, 10, 30, 30, tzinfo=timezone.utc)

    date_field_1 = field_handler.update_field(
        user=user, field=date_field_1, date_include_time=True
    )
    date_field_2 = field_handler.update_field(
        user=user, field=date_field_2, date_include_time=False
    )

    assert date_field_1.date_include_time is True
    assert date_field_2.date_include_time is False

    model = table.get_model(attribute_names=True)
    rows = model.objects.all()
    row_0, row_1, row_2 = rows

    assert row_0.date is None
    assert row_0.datetime is None
    assert row_1.date == datetime(2020, 4, 1, tzinfo=timezone.utc)
    assert row_1.datetime == date(2020, 4, 1)
    assert row_2.date is None
    assert row_2.datetime == date(2020, 4, 1)

    field_handler.delete_field(user=user, field=date_field_1)
    field_handler.delete_field(user=user, field=date_field_2)

    assert len(DateField.objects.all()) == 0


@pytest.mark.django_db
def test_converting_date_field_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()
    utc = timezone.utc

    date_field_eu = data_fixture.create_text_field(table=table)
    date_field_us = data_fixture.create_text_field(table=table)
    date_field_iso = data_fixture.create_text_field(table=table)
    date_field_eu_12 = data_fixture.create_text_field(table=table)
    date_field_us_12 = data_fixture.create_text_field(table=table)
    date_field_iso_12 = data_fixture.create_text_field(table=table)
    date_field_eu_24 = data_fixture.create_text_field(table=table)
    date_field_us_24 = data_fixture.create_text_field(table=table)
    date_field_iso_24 = data_fixture.create_text_field(table=table)

    model = table.get_model()
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{date_field_eu.id}": "22/07/2021",
            f"field_{date_field_us.id}": "07/22/2021",
            f"field_{date_field_iso.id}": "2021-07-22",
            f"field_{date_field_eu_12.id}": "22/07/2021 12:45 PM",
            f"field_{date_field_us_12.id}": "07/22/2021 12:45 PM",
            f"field_{date_field_iso_12.id}": "2021-07-22 12:45 PM",
            f"field_{date_field_eu_24.id}": "22/07/2021 12:45",
            f"field_{date_field_us_24.id}": "07/22/2021 12:45",
            f"field_{date_field_iso_24.id}": "2021-07-22 12:45",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{date_field_eu.id}": "22-7-2021",
            f"field_{date_field_us.id}": "7-22-2021",
            f"field_{date_field_iso.id}": "2021/7/22",
            f"field_{date_field_eu_12.id}": "22-7-2021 12:45 am",
            f"field_{date_field_us_12.id}": "7-22-2021 12:45 am",
            f"field_{date_field_iso_12.id}": "2021/7/22 12:45 am",
            f"field_{date_field_eu_24.id}": "22-7-2021 7:45",
            f"field_{date_field_us_24.id}": "7-22-2021 7:45",
            f"field_{date_field_iso_24.id}": "2021/7/22 7:45",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{date_field_eu.id}": "22/07/2021 12:00",
            f"field_{date_field_us.id}": "07/22/2021 12:00am",
            f"field_{date_field_iso.id}": "2021-07-22 12:00 PM",
            f"field_{date_field_eu_12.id}": "INVALID",
            f"field_{date_field_us_12.id}": "2222-2222-2222",
            f"field_{date_field_iso_12.id}": "x-7--1",
            f"field_{date_field_eu_24.id}": "22-7-2021 7:45:12",
            f"field_{date_field_us_24.id}": "7-22-2021 7:45:23",
            f"field_{date_field_iso_24.id}": "2021/7/22 7:45:70",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{date_field_eu.id}": "2018-08-20T13:20:10",
            f"field_{date_field_us.id}": "2017 Mar 03 05:12:41.211",
            f"field_{date_field_iso.id}": "19/Apr/2017:06:36:15",
            f"field_{date_field_eu_12.id}": "Dec 2, 2017 2:39:58 AM",
            f"field_{date_field_us_12.id}": "Jun 09 2018 15:28:14",
            f"field_{date_field_iso_12.id}": "Apr 20 00:00:35 2010",
            f"field_{date_field_eu_24.id}": "Apr 20 00:00:35 2010",
            f"field_{date_field_us_24.id}": "2018-02-27 15:35:20.311",
            f"field_{date_field_iso_24.id}": "10-04-19 12:00:17",
        },
    )

    date_field_eu = field_handler.update_field(
        user=user, field=date_field_eu, new_type_name="date", date_format="EU"
    )
    date_field_us = field_handler.update_field(
        user=user, field=date_field_us, new_type_name="date", date_format="US"
    )
    date_field_iso = field_handler.update_field(
        user=user, field=date_field_iso, new_type_name="date", date_format="ISO"
    )
    date_field_eu_12 = field_handler.update_field(
        user=user,
        field=date_field_eu_12,
        new_type_name="date",
        date_format="EU",
        date_include_time=True,
        date_time_format="12",
    )
    date_field_us_12 = field_handler.update_field(
        user=user,
        field=date_field_us_12,
        new_type_name="date",
        date_format="US",
        date_include_time=True,
        date_time_format="12",
    )
    date_field_iso_12 = field_handler.update_field(
        user=user,
        field=date_field_iso_12,
        new_type_name="date",
        date_format="ISO",
        date_include_time=True,
        date_time_format="12",
    )
    date_field_eu_24 = field_handler.update_field(
        user=user,
        field=date_field_eu_24,
        new_type_name="date",
        date_format="EU",
        date_include_time=True,
        date_time_format="24",
    )
    date_field_us_24 = field_handler.update_field(
        user=user,
        field=date_field_us_24,
        new_type_name="date",
        date_format="US",
        date_include_time=True,
        date_time_format="24",
    )
    date_field_iso_24 = field_handler.update_field(
        user=user,
        field=date_field_iso_24,
        new_type_name="date",
        date_format="ISO",
        date_include_time=True,
        date_time_format="24",
    )

    model = table.get_model()
    rows = model.objects.all()
    row_0, row_1, row_2, row_3 = rows

    assert getattr(row_0, f"field_{date_field_eu.id}") == date(2021, 7, 22)
    assert getattr(row_0, f"field_{date_field_us.id}") == date(2021, 7, 22)
    assert getattr(row_0, f"field_{date_field_iso.id}") == date(2021, 7, 22)
    assert getattr(row_0, f"field_{date_field_eu_12.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )
    assert getattr(row_0, f"field_{date_field_us_12.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )
    assert getattr(row_0, f"field_{date_field_iso_12.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )
    assert getattr(row_0, f"field_{date_field_eu_24.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )
    assert getattr(row_0, f"field_{date_field_us_24.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )
    assert getattr(row_0, f"field_{date_field_iso_24.id}") == (
        datetime(2021, 7, 22, 12, 45, 0, tzinfo=utc)
    )

    assert getattr(row_1, f"field_{date_field_eu.id}") == date(2021, 7, 22)
    assert getattr(row_1, f"field_{date_field_us.id}") == date(2021, 7, 22)
    assert getattr(row_1, f"field_{date_field_iso.id}") == date(2021, 7, 22)
    assert getattr(row_1, f"field_{date_field_eu_12.id}") == (
        datetime(2021, 7, 22, 0, 45, 0, tzinfo=utc)
    )
    assert getattr(row_1, f"field_{date_field_us_12.id}") == (
        datetime(2021, 7, 22, 0, 45, 0, tzinfo=utc)
    )
    assert getattr(row_1, f"field_{date_field_iso_12.id}") == (
        datetime(2021, 7, 22, 0, 45, 0, tzinfo=utc)
    )
    assert getattr(row_1, f"field_{date_field_eu_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )
    assert getattr(row_1, f"field_{date_field_us_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )
    assert getattr(row_1, f"field_{date_field_iso_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )

    assert getattr(row_2, f"field_{date_field_eu.id}") == date(2021, 7, 22)
    assert getattr(row_2, f"field_{date_field_us.id}") == date(2021, 7, 22)
    assert getattr(row_2, f"field_{date_field_iso.id}") == date(2021, 7, 22)
    assert getattr(row_2, f"field_{date_field_eu_12.id}") is None
    assert getattr(row_2, f"field_{date_field_us_12.id}") is None
    assert getattr(row_2, f"field_{date_field_iso_12.id}") is None
    assert getattr(row_2, f"field_{date_field_eu_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )
    assert getattr(row_2, f"field_{date_field_us_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )
    assert getattr(row_2, f"field_{date_field_iso_24.id}") == (
        datetime(2021, 7, 22, 7, 45, 0, tzinfo=utc)
    )

    """
    f'field_{date_field_eu.id}': '2018-08-20T13:20:10',
    f'field_{date_field_us.id}': '2017 Mar 03 05:12:41.211',
    f'field_{date_field_iso.id}': '19/Apr/2017:06:36:15',
    f'field_{date_field_eu_12.id}': 'Dec 2, 2017 2:39:58 AM',
    f'field_{date_field_us_12.id}': 'Jun 09 2018 15:28:14',
    f'field_{date_field_iso_12.id}': 'Apr 20 00:00:35 2010',
    f'field_{date_field_eu_24.id}': 'Apr 20 00:00:35 2010',
    f'field_{date_field_us_24.id}': '2018-02-27 15:35:20.311',
    f'field_{date_field_iso_24.id}': '10-04-19 12:00:17'
    """

    assert getattr(row_3, f"field_{date_field_eu.id}") == date(2018, 8, 20)
    assert getattr(row_3, f"field_{date_field_us.id}") == date(2017, 3, 3)
    assert getattr(row_3, f"field_{date_field_iso.id}") == date(2017, 4, 19)
    assert getattr(row_3, f"field_{date_field_eu_12.id}") == (
        datetime(2017, 12, 2, 2, 39, 58, tzinfo=utc)
    )
    assert getattr(row_3, f"field_{date_field_us_12.id}") == (
        datetime(2018, 6, 9, 15, 28, 14, tzinfo=utc)
    )
    assert getattr(row_3, f"field_{date_field_iso_12.id}") == (
        datetime(2010, 4, 20, 0, 0, 35, tzinfo=utc)
    )
    assert getattr(row_3, f"field_{date_field_eu_24.id}") == (
        datetime(2010, 4, 20, 0, 0, 35, tzinfo=utc)
    )
    assert getattr(row_3, f"field_{date_field_us_24.id}") == (
        datetime(2018, 2, 27, 15, 35, 20, 311000, tzinfo=utc)
    )
    assert getattr(row_3, f"field_{date_field_iso_24.id}") == (
        datetime(10, 4, 19, 12, 0, tzinfo=utc)
    )

    date_field_eu = field_handler.update_field(
        user=user, field=date_field_eu, new_type_name="text"
    )
    date_field_us = field_handler.update_field(
        user=user, field=date_field_us, new_type_name="text"
    )
    date_field_iso = field_handler.update_field(
        user=user, field=date_field_iso, new_type_name="text"
    )
    date_field_eu_12 = field_handler.update_field(
        user=user, field=date_field_eu_12, new_type_name="text"
    )
    date_field_us_12 = field_handler.update_field(
        user=user, field=date_field_us_12, new_type_name="text"
    )
    date_field_iso_12 = field_handler.update_field(
        user=user, field=date_field_iso_12, new_type_name="text"
    )
    date_field_eu_24 = field_handler.update_field(
        user=user, field=date_field_eu_24, new_type_name="text"
    )
    date_field_us_24 = field_handler.update_field(
        user=user, field=date_field_us_24, new_type_name="text"
    )
    date_field_iso_24 = field_handler.update_field(
        user=user, field=date_field_iso_24, new_type_name="text"
    )

    model = table.get_model()
    rows = model.objects.all()
    row_0, _, row_2, _ = rows

    assert getattr(row_0, f"field_{date_field_eu.id}") == "22/07/2021"
    assert getattr(row_0, f"field_{date_field_us.id}") == "07/22/2021"
    assert getattr(row_0, f"field_{date_field_iso.id}") == "2021-07-22"
    assert getattr(row_0, f"field_{date_field_eu_12.id}") == "22/07/2021 12:45 PM"
    assert getattr(row_0, f"field_{date_field_us_12.id}") == "07/22/2021 12:45 PM"
    assert getattr(row_0, f"field_{date_field_iso_12.id}") == "2021-07-22 12:45 PM"
    assert getattr(row_0, f"field_{date_field_eu_24.id}") == "22/07/2021 12:45"
    assert getattr(row_0, f"field_{date_field_us_24.id}") == "07/22/2021 12:45"
    assert getattr(row_0, f"field_{date_field_iso_24.id}") == "2021-07-22 12:45"

    assert getattr(row_2, f"field_{date_field_eu_12.id}") is None


@pytest.mark.django_db
def test_negative_date_field_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_text_field(table=table)
    datetime_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{date_field.id}": "",
            f"field_{datetime_field.id}": "",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "INVALID",
            f"field_{datetime_field.id}": "INVALID",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": " ",
            f"field_{datetime_field.id}": " ",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "0",
            f"field_{datetime_field.id}": "0",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "-0",
            f"field_{datetime_field.id}": "-0",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "00000",
            f"field_{datetime_field.id}": "00000",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": None,
            f"field_{datetime_field.id}": None,
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "2010-02-03",
            f"field_{datetime_field.id}": "2010-02-03 12:30",
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": "28/01/2012",
            f"field_{datetime_field.id}": "28/01/2012 12:30",
        }
    )

    date_field = FieldHandler().update_field(user, date_field, new_type_name="date")
    datetime_field = FieldHandler().update_field(
        user, datetime_field, new_type_name="date", date_include_time=True
    )

    model = table.get_model()
    results = model.objects.all()

    assert getattr(results[0], f"field_{date_field.id}") is None
    assert getattr(results[0], f"field_{datetime_field.id}") is None
    assert getattr(results[1], f"field_{date_field.id}") is None
    assert getattr(results[1], f"field_{datetime_field.id}") is None
    assert getattr(results[2], f"field_{date_field.id}") is None
    assert getattr(results[2], f"field_{datetime_field.id}") is None
    assert getattr(results[3], f"field_{date_field.id}") is None
    assert getattr(results[3], f"field_{datetime_field.id}") is None
    assert getattr(results[4], f"field_{date_field.id}") is None
    assert getattr(results[4], f"field_{datetime_field.id}") is None
    assert getattr(results[5], f"field_{date_field.id}") is None
    assert getattr(results[5], f"field_{datetime_field.id}") is None
    assert getattr(results[6], f"field_{date_field.id}") is None
    assert getattr(results[6], f"field_{datetime_field.id}") is None
    assert getattr(results[7], f"field_{date_field.id}") == date(2010, 2, 3)
    assert getattr(results[7], f"field_{datetime_field.id}") == (
        datetime(2010, 2, 3, 12, 30, 0, tzinfo=timezone.utc)
    )
    assert getattr(results[8], f"field_{date_field.id}") == date(2012, 1, 28)
    assert getattr(results[8], f"field_{datetime_field.id}") == (
        datetime(2012, 1, 28, 12, 30, 0, tzinfo=timezone.utc)
    )


@pytest.mark.django_db
def test_import_export_date_field(data_fixture):
    date_field = data_fixture.create_date_field()
    date_field_type = field_type_registry.get_by_model(date_field)
    number_serialized = date_field_type.export_serialized(date_field)
    number_field_imported = date_field_type.import_serialized(
        date_field.table,
        number_serialized,
        ImportExportConfig(include_permission_data=True),
        {},
        DeferredForeignKeyUpdater(),
    )
    assert date_field.date_format == number_field_imported.date_format
    assert date_field.date_include_time == number_field_imported.date_include_time
    assert date_field.date_time_format == number_field_imported.date_time_format


@pytest.mark.django_db
def test_get_set_export_serialized_value_date_field(data_fixture):
    table = data_fixture.create_database_table()
    date_field = data_fixture.create_date_field(table=table)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)

    date_field_name = f"field_{date_field.id}"
    datetime_field_name = f"field_{datetime_field.id}"
    date_field_type = field_type_registry.get_by_model(date_field)

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": "2010-02-03",
            f"field_{datetime_field.id}": datetime(
                2010, 2, 3, 12, 30, 0, tzinfo=timezone.utc
            ),
        }
    )

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    old_row_1_date = getattr(row_1, date_field_name)
    old_row_1_datetime = getattr(row_1, datetime_field_name)
    old_row_2_date = getattr(row_2, date_field_name)
    old_row_2_datetime = getattr(row_2, datetime_field_name)

    date_field_type.set_import_serialized_value(
        row_1,
        date_field_name,
        date_field_type.get_export_serialized_value(
            row_1, date_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )
    date_field_type.set_import_serialized_value(
        row_1,
        datetime_field_name,
        date_field_type.get_export_serialized_value(
            row_1, datetime_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )
    date_field_type.set_import_serialized_value(
        row_2,
        date_field_name,
        date_field_type.get_export_serialized_value(
            row_2, date_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )
    date_field_type.set_import_serialized_value(
        row_2,
        datetime_field_name,
        date_field_type.get_export_serialized_value(
            row_2, datetime_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    assert old_row_1_date == getattr(row_1, date_field_name)
    assert old_row_1_datetime == getattr(row_1, datetime_field_name)
    assert old_row_2_date == getattr(row_2, date_field_name)
    assert old_row_2_datetime == getattr(row_2, datetime_field_name)


@pytest.mark.django_db
def test_date_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    date_field = data_fixture.create_date_field(table=table)

    data_fixture.create_view_sort(view=grid_view, field=date_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{date_field.id}": "2010-02-03",
            },
            {
                f"field_{date_field.id}": "2010-02-04",
            },
            {
                f"field_{date_field.id}": "2010-02-05",
            },
        ],
        model=table_model,
    ).created_rows

    previous_row = handler.get_adjacent_row(
        table_model, row_b.id, previous=True, view=grid_view
    )
    next_row = handler.get_adjacent_row(table_model, row_b.id, view=grid_view)

    assert previous_row.id == row_c.id
    assert next_row.id == row_a.id


@pytest.mark.django_db
def test_get_group_by_metadata_in_rows_with_date_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    date_field = data_fixture.create_date_field(table=table, date_include_time=True)
    handler = RowHandler()
    [row_empty, row_a, row_b, row_c, row_d] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {},
            {
                f"field_{date_field.id}": "2010-01-01 12:00:21",
            },
            {
                f"field_{date_field.id}": "2010-01-01 12:00:10",
            },
            {
                f"field_{date_field.id}": "2010-01-01 12:01:21",
            },
            {
                f"field_{date_field.id}": "2010-01-02 12:01:21",
            },
        ],
    ).created_rows

    model = table.get_model()

    queryset = model.objects.all().enhance_by_fields()
    rows = list(queryset)

    handler = ViewHandler()
    counts = handler.get_group_by_metadata_in_rows([date_field], rows, queryset)

    # Resolve the queryset, so that we can do a comparison.
    for c in counts.keys():
        counts[c] = list(counts[c])

    assert counts == {
        date_field: unordered(
            [
                {
                    "count": 2,
                    f"field_{date_field.id}": datetime(
                        2010, 1, 1, 12, 0, 0, tzinfo=timezone.utc
                    ),
                },
                {
                    "count": 1,
                    f"field_{date_field.id}": datetime(
                        2010, 1, 1, 12, 1, 0, tzinfo=timezone.utc
                    ),
                },
                {
                    "count": 1,
                    f"field_{date_field.id}": datetime(
                        2010, 1, 2, 12, 1, 0, tzinfo=timezone.utc
                    ),
                },
                {"count": 1, f"field_{date_field.id}": None},
            ]
        )
    }


@pytest.mark.django_db
def test_date_field_overflow(settings, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    date_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Date",
    )
    invalid_date_value = "19999-01-01"
    row = row_handler.create_row(
        user=user, table=table, values={date_field.db_column: invalid_date_value}
    )
    assert getattr(row, date_field.db_column, None) == invalid_date_value

    date_field = field_handler.update_field(
        user=user, field=date_field, new_type_name="date", date_format="ISO"
    )

    assert isinstance(
        table.get_model().get_field_object(date_field.db_column)["field"], DateField
    )
    out = row_handler.get_rows(table.get_model(), [row.id])
    assert len(out) == 1
    assert getattr(out[0], date_field.db_column, None) is None

    date_field = field_handler.update_field(
        user=user, field=date_field, new_type_name="text", date_format="ISO"
    )

    table.refresh_from_db()
    assert isinstance(
        table.get_model().get_field_object(date_field.db_column)["field"], TextField
    )
    out = row_handler.get_rows(table.get_model(), [row.id])
    assert len(out) == 1
    assert getattr(out[0], date_field.db_column, None) is None


@pytest.mark.django_db
def test_datetime_field_overflow(on_db_connection, data_fixture):
    if is_psycopg3:
        from baserow.contrib.database.fields.utils.pg_datetime import (
            register_on_connection,
        )

        # manually register adapters, as signal-based registration will be called
        # too late
        on_db_connection(register_on_connection)

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    date_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Date",
    )
    invalid_date_value = "19999-01-01 01:01"
    row = row_handler.create_row(
        user=user, table=table, values={date_field.db_column: invalid_date_value}
    )
    assert getattr(row, date_field.db_column, None) == invalid_date_value

    date_field = field_handler.update_field(
        user=user,
        field=date_field,
        new_type_name="date",
        date_format="ISO",
        date_include_time=True,
        date_time_format="24",
    )
    assert isinstance(
        table.get_model().get_field_object(date_field.db_column)["field"], DateField
    )
    out = row_handler.get_rows(table.get_model(), [row.id])
    assert len(out) == 1

    assert getattr(out[0], date_field.db_column, None) is None

    date_field = field_handler.update_field(
        user=user, field=date_field, new_type_name="text", date_format="ISO"
    )

    table.refresh_from_db()
    assert isinstance(
        table.get_model().get_field_object(date_field.db_column)["field"], TextField
    )
    out = row_handler.get_rows(table.get_model(), [row.id])
    assert len(out) == 1

    assert getattr(out[0], date_field.db_column, None) is None
