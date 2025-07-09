from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, models
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time
from pyinstrument import Profiler

from baserow.contrib.database.api.utils import (
    extract_field_ids_from_list,
    extract_field_ids_from_string,
    extract_user_field_names_from_params,
    get_include_exclude_fields,
)
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.trash.handler import TrashHandler


def test_get_field_ids_from_dict():
    handler = RowHandler()
    fields_dict = {
        1: "Included",
        "field_2": "Included",
        "3": "Included",
        "abc": "Not included",
        "fieldd_3": "Not included",
    }
    assert handler.extract_field_ids_from_dict(fields_dict) == [1, 2, 3]


def test_extract_field_ids_from_list():
    assert extract_field_ids_from_list([]) == []
    assert extract_field_ids_from_list(["not", "something"]) == []
    assert extract_field_ids_from_list(["field_1", "field_2"]) == [1, 2]
    assert extract_field_ids_from_list(["field_22", "test_8", "999"]) == [22, 999]
    assert extract_field_ids_from_list(["field_22", "test_8", "999"], False) == [
        22,
        8,
        999,
    ]
    assert extract_field_ids_from_list(["is", "1", "one"]) == [1]


def test_extract_field_ids_from_string():
    assert extract_field_ids_from_string(None) == []
    assert extract_field_ids_from_string("not,something") == []
    assert extract_field_ids_from_string("field_1,field_2") == [1, 2]
    assert extract_field_ids_from_string("field_22,test_8,999") == [22, 8, 999]
    assert extract_field_ids_from_string("is,1,one") == [1]


def test_extract_user_field_names_from_params():
    assert extract_user_field_names_from_params({}) is False
    assert extract_user_field_names_from_params({"user_field_names": None}) is True
    assert extract_user_field_names_from_params({"user_field_names": ""}) is True
    assert extract_user_field_names_from_params({"user_field_names": "true"}) is True
    assert extract_user_field_names_from_params({"user_field_names": "false"}) is False


@pytest.mark.django_db
def test_get_include_exclude_fields(data_fixture):
    table = data_fixture.create_database_table()
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table, order=1)
    field_2 = data_fixture.create_text_field(table=table, order=2)
    field_3 = data_fixture.create_text_field(table=table_2, order=3)

    assert get_include_exclude_fields(table, include=None, exclude=None) is None

    assert get_include_exclude_fields(table, include="", exclude="") is None

    fields = get_include_exclude_fields(table, f"field_{field_1.id}")
    assert len(fields) == 1
    assert fields[0].id == field_1.id

    fields = get_include_exclude_fields(
        table, f"field_{field_1.id},field_9999,field_{field_2.id}"
    )
    assert len(fields) == 2
    assert fields[0].id == field_1.id
    assert fields[1].id == field_2.id

    fields = get_include_exclude_fields(table, None, f"field_{field_1.id},field_9999")
    assert len(fields) == 1
    assert fields[0].id == field_2.id

    fields = get_include_exclude_fields(
        table, f"field_{field_1.id},field_{field_2.id}", f"field_{field_1.id}"
    )
    assert len(fields) == 1
    assert fields[0].id == field_2.id

    fields = get_include_exclude_fields(table, f"field_{field_3.id}")
    assert len(fields) == 0

    fields = get_include_exclude_fields(table, None, f"field_{field_3.id}")
    assert len(fields) == 2


@pytest.mark.django_db
def test_extract_manytomany_values(data_fixture):
    row_handler = RowHandler()

    class TemporaryModel1(models.Model):
        class Meta:
            app_label = "test"

    class TemporaryModel2(models.Model):
        field_1 = models.CharField()
        field_2 = models.ManyToManyField(TemporaryModel1)

        class Meta:
            app_label = "test"

    values = {"field_1": "Value 1", "field_2": ["Value 2"]}

    values, manytomany_values = row_handler.extract_manytomany_values(
        values, TemporaryModel2
    )

    assert len(values.keys()) == 1
    assert "field_1" in values
    assert len(manytomany_values.keys()) == 1
    assert "field_2" in manytomany_values


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_create_row(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.create_row(user=user_2, table=table)

    row_1 = handler.create_row(
        user=user,
        table=table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )
    assert getattr(row_1, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_1, f"field_{speed_field.id}") == 240
    assert getattr(row_1, f"field_{price_field.id}") == 59999.99
    assert not getattr(row_1, f"field_9999", None)
    assert row_1.order == 1
    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_1, f"field_{speed_field.id}") == 240
    assert getattr(row_1, f"field_{price_field.id}") == Decimal("59999.99")
    assert not getattr(row_1, f"field_9999", None)
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_1.last_modified_by == user

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["rows"][0].id == row_1.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["before"] is None
    assert send_mock.call_args[1]["model"]._generated_table_model

    row_2 = handler.create_row(user=user, table=table)
    assert getattr(row_2, f"field_{name_field.id}") == "Test"
    assert not getattr(row_2, f"field_{speed_field.id}")
    assert not getattr(row_2, f"field_{price_field.id}")
    row_1.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_2.last_modified_by == user

    row_3 = handler.create_row(user=user, table=table, before_row=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.50000000000000000000")
    assert send_mock.call_args[1]["before"].id == row_2.id

    row_4 = handler.create_row(user=user, table=table, before_row=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.50000000000000000000")
    assert row_4.order == Decimal("1.66666666666666674068")

    row_5 = handler.create_row(user=user, table=table, before_row=row_3)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.50000000000000000000")
    assert row_4.order == Decimal("1.66666666666666674068")
    assert row_5.order == Decimal("1.33333333333333325932")

    row_6 = handler.create_row(user=user, table=table, before_row=row_2)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.50000000000000000000")
    assert row_4.order == Decimal("1.66666666666666674068")
    assert row_5.order == Decimal("1.33333333333333325932")
    assert row_6.order == Decimal("1.75000000000000000000")

    row_7 = handler.create_row(user, table=table, before_row=row_1)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()
    row_6.refresh_from_db()
    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("1.50000000000000000000")
    assert row_4.order == Decimal("1.66666666666666674068")
    assert row_5.order == Decimal("1.33333333333333325932")
    assert row_6.order == Decimal("1.75000000000000000000")
    assert row_7.order == Decimal("0.50000000000000000000")

    with pytest.raises(ValidationError):
        handler.create_row(user=user, table=table, values={price_field.id: -10.22})

    model = table.get_model()

    rows = model.objects.all()
    assert len(rows) == 7
    rows_0, rows_1, rows_2, rows_3, rows_4, rows_5, rows_6 = rows
    assert rows_0.id == row_7.id
    assert rows_1.id == row_1.id
    assert rows_2.id == row_5.id
    assert rows_3.id == row_3.id
    assert rows_4.id == row_4.id
    assert rows_5.id == row_6.id
    assert rows_6.id == row_2.id

    row_2.delete()
    row_8 = handler.create_row(user, table=table)
    assert row_8.order == Decimal("3.00000000000000000000")


@pytest.mark.django_db
def test_get_row(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{name_field.id}": "Tesla",
            f"field_{speed_field.id}": 240,
            f"field_{price_field.id}": Decimal("59999.99"),
        },
    )

    with pytest.raises(UserNotInWorkspace):
        handler.get_row(user=user_2, table=table, row_id=row.id)

    with pytest.raises(RowDoesNotExist):
        handler.get_row(user=user, table=table, row_id=99999)

    row_tmp = handler.get_row(user=user, table=table, row_id=row.id)

    assert row_tmp.id == row.id
    assert getattr(row_tmp, f"field_{name_field.id}") == "Tesla"
    assert getattr(row_tmp, f"field_{speed_field.id}") == 240
    assert getattr(row_tmp, f"field_{price_field.id}") == Decimal("59999.99")


@pytest.mark.django_db
def test_get_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    table_model = table.get_model()
    handler = RowHandler()
    rows = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "Tesla",
            },
            {
                f"field_{name_field.id}": "Audi",
            },
            {
                f"field_{name_field.id}": "BMW",
            },
        ],
        model=table_model,
    ).created_rows

    next_row = handler.get_adjacent_row(table_model, rows[1].id)
    previous_row = handler.get_adjacent_row(table_model, rows[1].id, previous=True)

    assert next_row.id == rows[2].id
    assert previous_row.id == rows[0].id


@pytest.mark.django_db
def test_get_adjacent_row_with_custom_filters(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    table_model = table.get_model()
    handler = RowHandler()
    [row_1, row_2, row_3] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "Tesla",
            },
            {
                f"field_{name_field.id}": "Audi",
            },
            {
                f"field_{name_field.id}": "BMW",
            },
        ],
        model=table_model,
    ).created_rows

    base_queryset = (
        table.get_model()
        .objects.filter(id__in=[row_2.id, row_3.id])
        .order_by("order", "id")
    )

    with pytest.raises(RowDoesNotExist):
        handler.get_adjacent_row_in_queryset(base_queryset, row_1.id)

    next_row = handler.get_adjacent_row_in_queryset(base_queryset, row_2.id)
    previous_row = handler.get_adjacent_row_in_queryset(
        base_queryset, row_2.id, previous=True
    )

    assert next_row.id == row_3.id
    assert previous_row is None


@pytest.mark.django_db
def test_get_adjacent_row_with_view_sort(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    view = data_fixture.create_grid_view(table=table)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    data_fixture.create_view_sort(view=view, field=name_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_1, row_2, row_3] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "A",
            },
            {
                f"field_{name_field.id}": "B",
            },
            {
                f"field_{name_field.id}": "C",
            },
        ],
        model=table_model,
    ).created_rows

    next_row = handler.get_adjacent_row(table_model, row_2.id, view=view)
    previous_row = handler.get_adjacent_row(
        table_model, row_2.id, previous=True, view=view
    )

    assert next_row.id == row_1.id
    assert previous_row.id == row_3.id


@pytest.mark.django_db
def test_get_adjacent_row_with_view_group_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    view = data_fixture.create_grid_view(table=table)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    data_fixture.create_view_group_by(view=view, field=name_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_1, row_2, row_3] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "A",
            },
            {
                f"field_{name_field.id}": "B",
            },
            {
                f"field_{name_field.id}": "C",
            },
        ],
        model=table_model,
    ).created_rows

    next_row = handler.get_adjacent_row(table_model, row_2.id, view=view)
    previous_row = handler.get_adjacent_row(
        table_model, row_2.id, previous=True, view=view
    )

    assert next_row.id == row_1.id
    assert previous_row.id == row_3.id


@pytest.mark.django_db
def test_get_adjacent_row_with_search(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    view = data_fixture.create_grid_view(table=table)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    table_model = table.get_model()
    handler = RowHandler()
    [row_1, row_2, row_3] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "a",
            },
            {
                f"field_{name_field.id}": "ab",
            },
            {
                f"field_{name_field.id}": "c",
            },
        ],
        model=table_model,
    ).created_rows

    search = "a"
    next_row = handler.get_adjacent_row(table_model, row_2.id, view=view, search=search)
    previous_row = handler.get_adjacent_row(
        table_model, row_2.id, previous=True, view=view, search=search
    )

    assert previous_row.id == row_1.id
    assert next_row is None

    search = "b"
    next_row = handler.get_adjacent_row(table_model, row_2.id, view=view, search=search)
    previous_row = handler.get_adjacent_row(
        table_model, row_2.id, previous=True, view=view, search=search
    )

    assert previous_row is None
    assert next_row is None


@pytest.mark.django_db
def test_get_adjacent_row_with_view_group_by_and_view_sort(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    view = data_fixture.create_grid_view(table=table)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    other_field = data_fixture.create_text_field(table=table, name="Other")

    data_fixture.create_view_sort(view=view, field=name_field, order="ASC")
    data_fixture.create_view_group_by(view=view, field=name_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_1, row_2, row_3] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{name_field.id}": "A",
                f"field_{other_field.id}": "C",
            },
            {
                f"field_{name_field.id}": "B",
                f"field_{other_field.id}": "B",
            },
            {
                f"field_{name_field.id}": "C",
                f"field_{other_field.id}": "A",
            },
        ],
        model=table_model,
    ).created_rows

    next_row = handler.get_adjacent_row(table_model, row_2.id, view=view)
    previous_row = handler.get_adjacent_row(
        table_model, row_2.id, previous=True, view=view
    )

    assert next_row.id == row_1.id
    assert previous_row.id == row_3.id


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_get_adjacent_row_performance_many_rows(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    handler = RowHandler()

    row_amount = 100000
    row_values = [{f"field_{name_field.id}": "Tesla"} for _ in range(row_amount)]

    table_model = table.get_model()
    rows = handler.create_rows(
        user=user, table=table, rows_values=row_values, model=table_model
    ).created_rows

    profiler = Profiler()
    profiler.start()
    next_row = handler.get_adjacent_row(table_model, rows[5].id)
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))

    assert next_row.id == rows[6].id
    assert table.get_model().objects.count() == row_amount


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_get_adjacent_row_performance_many_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)

    handler = RowHandler()

    field_amount = 1000
    fields = [
        data_fixture.create_text_field(table=table, name=f"Field_{i}")
        for i in range(field_amount)
    ]

    row_amount = 4000
    row_values = []
    for i in range(row_amount):
        row_value = {f"field_{field.id}": "Tesla" for field in fields}
        row_values.append(row_value)

    table_model = table.get_model()
    rows = handler.create_rows(
        user=user, table=table, rows_values=row_values, model=table_model
    ).created_rows

    profiler = Profiler()
    profiler.start()
    next_row = handler.get_adjacent_row(table_model, rows[5].id)
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))

    assert next_row.id == rows[6].id
    assert table.get_model().objects.count() == row_amount


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_update_row_by_id(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(user=user, table=table)

    with pytest.raises(UserNotInWorkspace):
        handler.update_row_by_id(user=user_2, table=table, row_id=row.id, values={})

    with pytest.raises(RowDoesNotExist):
        handler.update_row_by_id(user=user, table=table, row_id=99999, values={})

    with pytest.raises(ValidationError):
        handler.update_row_by_id(
            user=user, table=table, row_id=row.id, values={price_field.id: -10.99}
        )

    with patch(
        "baserow.contrib.database.rows.signals.before_rows_update.send"
    ) as before_send_mock:
        handler.update_row_by_id(
            user=user,
            table=table,
            row_id=row.id,
            values={
                name_field.id: "Tesla",
                speed_field.id: 240,
                f"field_{price_field.id}": 59999.99,
            },
        )
    row.refresh_from_db()

    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == Decimal("59999.99")

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["rows"][0].id == row.id
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["rows"][0].id == row.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value


@pytest.mark.django_db
def test_update_row_last_modified_by(data_fixture):
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    data_fixture.create_user_workspace(user=user, workspace=workspace)
    data_fixture.create_user_workspace(user=user_2, workspace=workspace)
    table = data_fixture.create_database_table(name="Car", user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    model = table.get_model()
    row = model.objects.create(
        **{f"field_{name_field.id}": "Test", "last_modified_by": user}
    )

    handler = RowHandler()
    updated_row = handler.update_row(user_2, table, row, {"Name": "Test 2"})

    assert updated_row.last_modified_by == user_2


@pytest.mark.django_db
def test_update_rows_return_original_values_and_fields_metadata(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test", order=1
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", order=2
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
        order=3,
    )
    handler = RowHandler()

    rows = handler.create_rows(
        user=user,
        table=table,
        rows_values=[{}, {}],
    ).created_rows

    result = handler.update_rows(
        user=user,
        table=table,
        rows_values=[
            {
                "id": rows[0].id,
                f"field_{name_field.id}": "Tesla",
                f"field_{speed_field.id}": 240,
                f"field_{price_field.id}": 59999.99,
            },
            {
                "id": rows[1].id,
                f"field_{name_field.id}": "Giulietta",
            },
        ],
    )

    assert len(result.updated_rows) == 2
    assert result.original_rows_values_by_id == {
        rows[0].id: {
            "id": rows[0].id,
            f"field_{name_field.id}": "Test",  # Original default value
            f"field_{speed_field.id}": None,
            f"field_{price_field.id}": None,
        },
        rows[1].id: {
            "id": rows[1].id,
            f"field_{name_field.id}": "Test",  # Original default value
            f"field_{speed_field.id}": None,
            f"field_{price_field.id}": None,
        },
    }
    assert result.updated_fields_metadata_by_row_id == {
        rows[0].id: {
            "id": rows[0].id,
            f"field_{name_field.id}": {
                "id": name_field.id,
                "type": "text",
            },
            f"field_{speed_field.id}": {
                "id": speed_field.id,
                "type": "number",
                "number_decimal_places": 0,
                "number_negative": False,
                "number_prefix": "",
                "number_separator": "",
                "number_suffix": "",
            },
            f"field_{price_field.id}": {
                "id": price_field.id,
                "type": "number",
                "number_decimal_places": 2,
                "number_negative": False,
                "number_prefix": "",
                "number_separator": "",
                "number_suffix": "",
            },
        },
        rows[1].id: {
            "id": rows[1].id,
            f"field_{name_field.id}": {
                "id": name_field.id,
                "type": "text",
            },
            f"field_{speed_field.id}": {
                "id": speed_field.id,
                "type": "number",
                "number_decimal_places": 0,
                "number_negative": False,
                "number_prefix": "",
                "number_separator": "",
                "number_suffix": "",
            },
            f"field_{price_field.id}": {
                "id": price_field.id,
                "type": "number",
                "number_decimal_places": 2,
                "number_negative": False,
                "number_prefix": "",
                "number_separator": "",
                "number_suffix": "",
            },
        },
    }


@pytest.mark.django_db
def test_create_rows_created_on_and_last_modified(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = RowHandler()

    with freeze_time("2020-01-01 12:00"):
        rows = handler.create_rows(
            user=user, table=table, rows_values=[{}]
        ).created_rows
        row = rows[0]
        assert row.created_on == datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert row.updated_on == datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_create_rows_last_modified_by(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    handler = RowHandler()

    rows = handler.create_rows(
        user,
        table,
        rows_values=[
            {f"field_{name_field.id}": "Test"},
            {f"field_{name_field.id}": "Test 2"},
        ],
    ).created_rows

    assert rows[0].last_modified_by == user
    assert rows[1].last_modified_by == user


@pytest.mark.django_db
def test_update_rows_created_on_and_last_modified(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    handler = RowHandler()

    with freeze_time("2020-01-01 12:00"):
        row = table.get_model().objects.create()

    with freeze_time("2020-01-02 12:00"):
        result = handler.update_rows(
            user,
            table,
            [{"id": row.id, f"field_" f"{field.id}": "Test"}],
        )
        row = result.updated_rows[0]
        assert row.created_on == datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert row.updated_on == datetime(2020, 1, 2, 12, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_update_rows_last_modified_by(data_fixture):
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    data_fixture.create_user_workspace(user=user, workspace=workspace)
    data_fixture.create_user_workspace(user=user_2, workspace=workspace)
    data_fixture.create_user_workspace(user=user_3, workspace=workspace)
    table = data_fixture.create_database_table(name="Car", user=user, database=database)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    model = table.get_model()

    row = model.objects.create(
        **{f"field_{name_field.id}": "Test", "last_modified_by": user}
    )
    row_2 = model.objects.create(
        **{f"field_{name_field.id}": "Test", "last_modified_by": user_2}
    )
    row_3 = model.objects.create(
        **{f"field_{name_field.id}": "Test", "last_modified_by": user_2}
    )

    handler = RowHandler()
    handler.update_rows(
        user_3,
        table,
        [
            {
                "id": row.id,
                f"field_{name_field.id}": "Test 2",
            },
            {
                "id": row_2.id,
                f"field_{name_field.id}": "Test 2",
            },
        ],
    )

    updated_rows = model.objects.all()

    assert updated_rows[0].last_modified_by == user_3
    assert updated_rows[1].last_modified_by == user_3
    assert updated_rows[2].last_modified_by == user_2


@pytest.mark.django_db
@patch("baserow.ws.tasks.broadcast_to_users.delay")
@patch("baserow.contrib.database.table.signals.table_updated.send")
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_import_rows(
    mocked_rows_created,
    mocked_table_updated,
    mocked_broadcast_to_users,
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test", order=1
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True, order=2
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
        order=3,
    )

    handler = RowHandler()

    rows, report = handler.import_rows(
        user=user,
        table=table,
        data=[
            [
                "Tesla",
                240,
                59999.99,
            ],
            [
                "Giulietta",
                210,
                34999.99,
            ],
            [
                "Panda",
                160,
                8999.99,
            ],
        ],
        send_realtime_update=False,
    )
    assert len(rows) == 3
    assert report == {}

    model = table.get_model()
    assert model.objects.count() == 3

    mocked_rows_created.assert_called_once()
    args = mocked_rows_created.call_args_list[0]
    assert args[1]["send_realtime_update"] is False
    mocked_broadcast_to_users.assert_not_called()
    mocked_table_updated.assert_not_called()

    rows, report = handler.import_rows(
        user=user,
        table=table,
        data=[
            [
                "Tesla",
                240,
                59999.999999,
            ],
            [
                "Giulietta",
                210.888,
                34999.99,
            ],
            [
                "Panda",
                160,
                8999.99,
            ],
        ],
    )

    assert len(rows) == 1
    assert sorted(report.keys()) == sorted([0, 1])

    model = table.get_model()
    assert model.objects.count() == 4

    # create_rows_by_batch put the send_realtime_update to False
    # for the rows_created signal anyway, but this time the
    # table_updated signal is called and broadcast_to_permitted_users
    assert mocked_rows_created.call_count == 2
    args = mocked_rows_created.call_args_list[1]
    assert args[1]["send_realtime_update"] is False
    mocked_table_updated.assert_called_once()

    rows, report = handler.import_rows(
        user=user,
        table=table,
        data=[
            [
                "Panda",
                160,
                8999.99,
            ],
            ["Tesla", 240, 59999.999999, "bli bloup"],
            [
                "Giulietta",
                210.888,
            ],
        ],
    )

    assert len(rows) == 1
    assert sorted(report.keys()) == sorted([1, 2])


@pytest.mark.django_db
def test_import_rows_with_read_only_field(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test", order=1, read_only=True
    )

    handler = RowHandler()

    rows, report = handler.import_rows(
        user=user,
        table=table,
        data=[
            [
                "Tesla",
            ],
        ],
        send_realtime_update=False,
    )

    model = table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 0


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
@patch("baserow.contrib.database.rows.signals.before_rows_update.send")
def test_move_row(before_send_mock, send_mock, data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    original_creator = data_fixture.create_user()
    data_fixture.create_user_workspace(workspace=workspace, user=user)
    data_fixture.create_user_workspace(workspace=workspace, user=original_creator)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(name="Car", user=user, database=database)

    handler = RowHandler()
    row_1 = handler.create_row(user=original_creator, table=table)
    row_2 = handler.create_row(user=original_creator, table=table)
    row_3 = handler.create_row(user=original_creator, table=table)

    with pytest.raises(UserNotInWorkspace):
        handler.move_row_by_id(user=user_2, table=table, row_id=row_1.id)

    with pytest.raises(RowDoesNotExist):
        handler.move_row_by_id(user=user, table=table, row_id=99999)

    handler.move_row_by_id(user=user, table=table, row_id=row_1.id)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("4.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")
    assert row_1.last_modified_by == original_creator
    assert row_2.last_modified_by == original_creator
    assert row_3.last_modified_by == original_creator

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["rows"][0].id == row_1.id
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["rows"][0].id == row_1.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value

    handler.move_row_by_id(user=user, table=table, row_id=row_1.id, before_row=row_3)
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("2.50000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    row_ids = table.get_model().objects.all()
    assert row_ids[0].id == row_2.id
    assert row_ids[1].id == row_1.id
    assert row_ids[2].id == row_3.id


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_deleted.send")
@patch("baserow.contrib.database.rows.signals.before_rows_delete.send")
def test_delete_row(before_send_mock, send_mock, data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    original_creator = data_fixture.create_user()
    data_fixture.create_user_workspace(workspace=workspace, user=user)
    data_fixture.create_user_workspace(workspace=workspace, user=original_creator)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(name="Car", user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row = handler.create_row(user=original_creator, table=table)
    handler.create_row(user=user, table=table)

    with pytest.raises(UserNotInWorkspace):
        handler.delete_row_by_id(user=user_2, table=table, row_id=row.id)

    with pytest.raises(RowDoesNotExist):
        handler.delete_row_by_id(user=user, table=table, row_id=99999)

    row_id = row.id
    handler.delete_row_by_id(user=user, table=table, row_id=row.id)
    assert model.objects.all().count() == 1
    assert model.trash.all().count() == 1
    row.refresh_from_db()
    assert row.trashed
    assert row.last_modified_by == original_creator

    before_send_mock.assert_called_once()
    assert before_send_mock.call_args[1]["rows"]
    assert before_send_mock.call_args[1]["user"].id == user.id
    assert before_send_mock.call_args[1]["table"].id == table.id
    assert before_send_mock.call_args[1]["model"]._generated_table_model

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["rows"][0].id == row_id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before_return"] == before_send_mock.return_value


@pytest.mark.django_db
def test_delete_rows_permanently_delete(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    row = handler.create_row(user=user, table=table)
    row2 = handler.create_row(user=user, table=table)

    handler.delete_rows(
        user=user, table=table, row_ids=[row.id, row2.id], permanently_delete=True
    )
    model = table.get_model()
    assert model.objects.all().count() == 0


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_deleted.send")
@patch("baserow.contrib.database.rows.signals.before_rows_delete.send")
def test_delete_rows_preserves_last_modified_by(
    before_rows_delete_mock, rows_deleted_mock, data_fixture
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user()
    original_creator = data_fixture.create_user()
    data_fixture.create_user_workspace(workspace=workspace, user=user)
    data_fixture.create_user_workspace(workspace=workspace, user=original_creator)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(name="Car", user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    row = handler.create_row(user=original_creator, table=table)
    row2 = handler.create_row(user=original_creator, table=table)

    handler.delete_rows(user=user, table=table, row_ids=[row.id, row2.id])
    row.refresh_from_db()
    row2.refresh_from_db()

    assert row.trashed
    assert row2.trashed
    assert row.last_modified_by == original_creator
    assert row2.last_modified_by == original_creator


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_restore_row(send_mock, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()

    row_1 = handler.create_row(
        user=user,
        table=table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
        },
    )

    handler.delete_row_by_id(user, table, row_1.id)
    TrashHandler.restore_item(user, "row", row_1.id, parent_trash_item_id=table.id)

    assert len(send_mock.call_args) == 2
    assert send_mock.call_args[1]["rows"][0].id == row_1.id
    assert send_mock.call_args[1]["user"] is None
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["before"] is None
    assert send_mock.call_args[1]["model"]._generated_table_model


@pytest.mark.django_db
def test_get_include_exclude_fields_with_user_field_names(data_fixture):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field(name="first", table=table, order=1)
    data_fixture.create_text_field(name="Test", table=table, order=2)
    data_fixture.create_text_field(name="Test_2", table=table, order=3)
    data_fixture.create_text_field(name="With Space", table=table, order=4)

    assert (
        get_include_exclude_fields(
            table, include=None, exclude=None, user_field_names=True
        )
        is None
    )

    assert (
        get_include_exclude_fields(table, include="", exclude="", user_field_names=True)
        is None
    )

    fields = get_include_exclude_fields(table, include="Test_2", user_field_names=True)
    assert list(fields.values_list("name", flat=True)) == ["Test_2"]

    fields = get_include_exclude_fields(
        table, "first,field_9999,Test", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == ["first", "Test"]

    fields = get_include_exclude_fields(
        table, None, "first,field_9999", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == [
        "Test",
        "Test_2",
        "With Space",
    ]

    fields = get_include_exclude_fields(
        table, "first,Test", "first", user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == ["Test"]

    fields = get_include_exclude_fields(
        table, 'first,"With Space",Test', user_field_names=True
    )
    assert list(fields.values_list("name", flat=True)) == [
        "first",
        "Test",
        "With Space",
    ]


@pytest.mark.django_db
def test_has_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )

    handler = RowHandler()
    row = handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{name_field.id}": "Tesla",
            f"field_{speed_field.id}": 240,
            f"field_{price_field.id}": Decimal("59999.99"),
        },
    )

    with pytest.raises(RowDoesNotExist):
        handler.has_row(user=user, table=table, row_id=99999, raise_error=True)
    assert not handler.has_row(user=user, table=table, row_id=99999, raise_error=False)

    assert handler.has_row(user=user, table=table, row_id=row.id, raise_error=False)
    assert handler.has_row(user=user, table=table, row_id=row.id, raise_error=True)


@pytest.mark.django_db
def test_get_unique_orders_without_before_row(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Table", user=user, database=database
    )

    model = table.get_model()
    model.objects.create(order=Decimal("1.00000000000000000000"))
    model.objects.create(order=Decimal("2.00000000000000000000"))
    model.objects.create(order=Decimal("3.00000000000000000000"))
    model.objects.create(order=Decimal("4.00000000000000000000"))

    handler = RowHandler()
    assert handler.get_unique_orders_before_row(None, model) == [
        Decimal("5.00000000000000000000")
    ]
    assert handler.get_unique_orders_before_row(None, model, 3) == [
        Decimal("5.00000000000000000000"),
        Decimal("6.00000000000000000000"),
        Decimal("7.00000000000000000000"),
    ]


@pytest.mark.django_db
def test_get_unique_orders_with_before_row(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Table", user=user, database=database
    )

    model = table.get_model()
    model.objects.create(order=Decimal("1.00000000000000000000"))
    row_2 = model.objects.create(order=Decimal("2.00000000000000000000"))
    model.objects.create(order=Decimal("3.00000000000000000000"))
    row_4 = model.objects.create(order=Decimal("4.00000000000000000000"))

    handler = RowHandler()
    assert handler.get_unique_orders_before_row(row_2, model) == [
        Decimal("1.50000000000000000000")
    ]
    assert handler.get_unique_orders_before_row(row_2, model, 3) == [
        Decimal("1.5"),
        Decimal("1.66666666666666674068"),
        Decimal("1.75"),
    ]
    assert handler.get_unique_orders_before_row(row_4, model) == [
        Decimal("3.50000000000000000000")
    ]


@pytest.mark.django_db
def test_get_unique_orders_first_before_row(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Table", user=user, database=database
    )

    model = table.get_model()
    row_1 = model.objects.create(order=Decimal("1.00000000000000000000"))

    handler = RowHandler()
    assert handler.get_unique_orders_before_row(row_1, model) == [
        Decimal("0.50000000000000000000")
    ]
    assert handler.get_unique_orders_before_row(row_1, model, 3) == [
        Decimal("0.5"),
        Decimal("0.66666666666666662966"),
        Decimal("0.75"),
    ]


@pytest.mark.django_db
def test_get_unique_orders_before_row_triggering_full_table_order_reset(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Table", user=user, database=database
    )

    model = table.get_model()
    row_1 = model.objects.create(order=Decimal("1.00000000000000000000"))
    row_2 = model.objects.create(order=Decimal("1.00000000000000001000"))
    row_3 = model.objects.create(order=Decimal("2.99999999999999999999"))
    row_4 = model.objects.create(order=Decimal("2.99999999999999999998"))

    handler = RowHandler()
    assert handler.get_unique_orders_before_row(row_3, model, 2) == [
        Decimal("3.50000000000000000000"),
        Decimal("3.66666666666666651864"),
    ]

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()

    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("4.00000000000000000000")
    assert row_4.order == Decimal("3.00000000000000000000")


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.row_orders_recalculated.send")
def test_recalculate_row_orders(send_mock, data_fixture):
    database = data_fixture.create_database_application()
    table = data_fixture.create_database_table(database=database)
    model = table.get_model()

    row_1 = model.objects.create(order="1.99999999999999999999")
    row_2 = model.objects.create(order="2.00000000000000000000")
    row_3 = model.objects.create(order="1.99999999999999999999")
    row_4 = model.objects.create(order="2.10000000000000000000")
    row_5 = model.objects.create(order="3.00000000000000000000")
    row_6 = model.objects.create(order="1.00000000000000000001")
    row_7 = model.objects.create(order="3.99999999999999999999")
    row_8 = model.objects.create(order="4.00000000000000000001")

    RowHandler().recalculate_row_orders(table)

    rows = model.objects.all()
    assert rows[0].id == row_6.id
    assert rows[0].order == Decimal("1.00000000000000000000")

    assert rows[1].id == row_1.id
    assert rows[1].order == Decimal("2.00000000000000000000")

    assert rows[2].id == row_3.id
    assert rows[2].order == Decimal("3.00000000000000000000")

    assert rows[3].id == row_2.id
    assert rows[3].order == Decimal("4.00000000000000000000")

    assert rows[4].id == row_4.id
    assert rows[4].order == Decimal("5.00000000000000000000")

    assert rows[5].id == row_5.id
    assert rows[5].order == Decimal("6.00000000000000000000")

    assert rows[6].id == row_7.id
    assert rows[6].order == Decimal("7.00000000000000000000")

    assert rows[7].id == row_8.id
    assert rows[7].order == Decimal("8.00000000000000000000")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == table.id


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_created.send")
@patch("baserow.contrib.database.views.handler.ViewHandler.field_value_updated")
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.schedule_update_search_data"
)
def test_formula_referencing_fields_add_additional_queries_on_rows_created(
    mock1, mock2, mock3, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    model = table.get_model()

    # The first time the dependency handler is making an additional for this statement
    # in the FieldDependencyHandler:
    # link_row_field_content_type = ContentType.objects.get_for_model(LinkRowField)
    # so let's create a row first to avoid counting that query
    RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    with CaptureQueriesContext(connection) as captured:
        RowHandler().force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    f"field_{name_field.id}": "Giulia",
                }
            ],
            model=model,
        )

    f1 = data_fixture.create_formula_field(
        table=table,
        name="F1",
        formula="field('Name') + '-a'",
    )
    model = table.get_model()

    # An UPDATE query to set the formula field value + 1 query due
    # to FormulaFieldType.after_rows_created
    with django_assert_num_queries(len(captured.captured_queries) + 2):
        (r,) = (
            RowHandler()
            .force_create_rows(
                user=user,
                table=table,
                rows_values=[
                    {
                        f"field_{name_field.id}": "Giulietta",
                    }
                ],
                model=model,
            )
            .created_rows
        )
    assert getattr(r, f"field_{f1.id}") == "Giulietta-a"

    # A second formula referencing the same field should set the value
    # in the same UPDATE query
    f2 = data_fixture.create_formula_field(
        table=table,
        name="F2",
        formula="field('Name') + '-b'",
    )
    model = table.get_model()

    with django_assert_num_queries(len(captured.captured_queries) + 2):
        (r,) = (
            RowHandler()
            .force_create_rows(
                user=user,
                table=table,
                rows_values=[
                    {
                        f"field_{name_field.id}": "Stelvio",
                    }
                ],
                model=model,
            )
            .created_rows
        )
    assert getattr(r, f"field_{f1.id}") == "Stelvio-a"
    assert getattr(r, f"field_{f2.id}") == "Stelvio-b"

    # But a formula referencing another formula requires an additional query
    # because it needs the result of the first formula to calculate the second
    f3 = data_fixture.create_formula_field(
        table=table,
        name="F3",
        formula="field('F1') + '-c'",
    )
    model = table.get_model()

    # Now a second UPDATE query is needed, so that F3 can use the result
    # of F1 to correctly calculate its value
    with django_assert_num_queries(len(captured.captured_queries) + 3):
        (r,) = (
            RowHandler()
            .force_create_rows(
                user=user,
                table=table,
                rows_values=[
                    {
                        f"field_{name_field.id}": "Tonale",
                    }
                ],
                model=model,
            )
            .created_rows
        )
    assert getattr(r, f"field_{f1.id}") == "Tonale-a"
    assert getattr(r, f"field_{f2.id}") == "Tonale-b"
    assert getattr(r, f"field_{f3.id}") == "Tonale-a-c"


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
@patch("baserow.contrib.database.views.handler.ViewHandler.field_value_updated")
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.schedule_update_search_data"
)
def test_formula_referencing_fields_add_additional_queries_on_rows_updated(
    mock1, mock2, mock3, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    model = table.get_model()

    # The first time the dependency handler is making an additional for this statement
    # in the FieldDependencyHandler:
    # link_row_field_content_type = ContentType.objects.get_for_model(LinkRowField)
    # so let's create a row first to avoid counting that query
    (r,) = (
        RowHandler()
        .force_create_rows(user=user, table=table, rows_values=[{}])
        .created_rows
    )

    with CaptureQueriesContext(connection) as captured:
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    "id": r.id,
                    f"field_{name_field.id}": "Giulia",
                }
            ],
            model=model,
        )

    f1 = data_fixture.create_formula_field(
        table=table,
        name="F1",
        formula="field('Name') + '-a'",
    )
    model = table.get_model()

    # An UPDATE query to set the formula field value
    with django_assert_num_queries(len(captured.captured_queries) + 1):
        res = RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    "id": r.id,
                    f"field_{name_field.id}": "Giulietta",
                }
            ],
            model=model,
        )
        (r,) = res.updated_rows
    assert getattr(r, f"field_{f1.id}") == "Giulietta-a"

    # A second formula referencing the same field should set the value
    # in the same UPDATE query
    f2 = data_fixture.create_formula_field(
        table=table,
        name="F2",
        formula="field('Name') + '-b'",
    )
    model = table.get_model()

    with django_assert_num_queries(len(captured.captured_queries) + 1):
        res = RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    "id": r.id,
                    f"field_{name_field.id}": "Stelvio",
                }
            ],
            model=model,
        )
        (r,) = res.updated_rows
    assert getattr(r, f"field_{f1.id}") == "Stelvio-a"
    assert getattr(r, f"field_{f2.id}") == "Stelvio-b"

    # But a formula referencing another formula requires an additional query
    # because it needs the result of the first formula to calculate the second
    f3 = data_fixture.create_formula_field(
        table=table,
        name="F3",
        formula="field('F1') + '-c'",
    )
    model = table.get_model()

    # Now a second UPDATE query is needed, so that F3 can use the result
    # of F1 to correctly calculate its value
    with django_assert_num_queries(len(captured.captured_queries) + 2):
        res = RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    "id": r.id,
                    f"field_{name_field.id}": "Tonale",
                }
            ],
            model=model,
        )
        (r,) = res.updated_rows
    assert getattr(r, f"field_{f1.id}") == "Tonale-a"
    assert getattr(r, f"field_{f2.id}") == "Tonale-b"
    assert getattr(r, f"field_{f3.id}") == "Tonale-a-c"


@pytest.mark.django_db
def test_can_move_rows_and_formulas_are_updated_correctly(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    prim_b = data_fixture.create_text_field(table=table_b, primary=True, name="name")

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user, table_b, [{prim_b.db_column: "b1"}, {prim_b.db_column: "b2"}]
        )
        .created_rows
    )

    lookup_a = data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'name'), '')"
    )

    row_a1, row_a2 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_a_b.db_column: [row_b1.id]}, {link_a_b.db_column: [row_b2.id]}],
        )
        .created_rows
    )

    assert getattr(row_a1, lookup_a.db_column) == "b1"
    assert getattr(row_a2, lookup_a.db_column) == "b2"

    # moving rows up and down should mantain the formulas correct
    row_a2 = RowHandler().move_row(user, table_a, row_a2, before_row=row_a1)

    row_a1.refresh_from_db()
    row_a2.refresh_from_db()
    assert getattr(row_a1, lookup_a.db_column) == "b1"
    assert getattr(row_a2, lookup_a.db_column) == "b2"

    row_a1 = RowHandler().move_row(user, table_a, row_a1, before_row=row_a2)

    row_a1.refresh_from_db()
    row_a2.refresh_from_db()
    assert getattr(row_a1, lookup_a.db_column) == "b1"
    assert getattr(row_a2, lookup_a.db_column) == "b2"


@pytest.mark.django_db
def test_rows_created_is_not_sent_if_there_are_no_rows_to_create(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table()
    with patch("baserow.contrib.database.rows.signals.rows_created.send") as mock:
        RowHandler().force_create_rows(user, table, [])

        assert mock.call_count == 0


@pytest.mark.django_db
def test_update_rows_only_create_or_delete_differences_for_m2m_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user_2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table_a, name="multiple_select"
    )
    select_options = SelectOption.objects.bulk_create(
        [
            SelectOption(field=multiple_select_field, value="a", order=1),
            SelectOption(field=multiple_select_field, value="b", order=2),
        ]
    )
    multiple_collaborator_field = data_fixture.create_multiple_collaborators_field(
        table=table_a, name="multiple_collaborator"
    )

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}] * 3).created_rows
    )

    model_a = table_a.get_model()
    (row_a1,) = (
        RowHandler()
        .force_create_rows(
            user,
            table_a,
            [
                {
                    multiple_select_field.db_column: [select_options[0].id],
                    multiple_collaborator_field.db_column: [{"id": user_2.id}],
                    link_a_b.db_column: [row_b1.id],
                }
            ],
            model=model_a,
        )
        .created_rows
    )

    assert row_a1.id is not None
    multiselect_through = model_a._meta.get_field(
        multiple_select_field.db_column
    ).remote_field.through

    multicollab_through = model_a._meta.get_field(
        multiple_collaborator_field.db_column
    ).remote_field.through

    link_through = model_a._meta.get_field(link_a_b.db_column).remote_field.through

    assert set(multiselect_through.objects.values_list("id", flat=True)) == {1}
    assert set(multicollab_through.objects.values_list("id", flat=True)) == {1}
    assert set(link_through.objects.values_list("id", flat=True)) == {1}

    # If we update the rows adding a new relation, the previous items should be kept
    # and the new ones added

    RowHandler().force_update_rows(
        user,
        table_a,
        [
            {
                "id": row_a1.id,
                multiple_select_field.db_column: [
                    select_options[0].id,
                    select_options[1].id,
                ],
                multiple_collaborator_field.db_column: [
                    {"id": user_2.id},
                    {"id": user.id},
                ],
                link_a_b.db_column: [row_b1.id, row_b2.id, row_b3.id],
            }
        ],
        model=model_a,
    )

    assert set(multiselect_through.objects.values_list("id", flat=True)) == {1, 2}
    assert set(multicollab_through.objects.values_list("id", flat=True)) == {1, 2}
    assert set(link_through.objects.values_list("id", flat=True)) == {1, 2, 3}

    # If we update the rows removing the relations, only those items should be removed

    RowHandler().force_update_rows(
        user,
        table_a,
        [
            {
                "id": row_a1.id,
                multiple_select_field.db_column: [select_options[1].id],
                multiple_collaborator_field.db_column: [{"id": user.id}],
                link_a_b.db_column: [row_b3.id],
            }
        ],
        model=model_a,
    )

    assert set(multiselect_through.objects.values_list("id", flat=True)) == {2}
    assert set(multicollab_through.objects.values_list("id", flat=True)) == {2}
    assert set(link_through.objects.values_list("id", flat=True)) == {3}
