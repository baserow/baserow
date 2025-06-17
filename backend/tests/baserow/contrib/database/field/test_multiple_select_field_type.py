import os
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Dict, List, Type

from django.apps.registry import apps
from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from faker import Faker
from pytest_unordered import unordered

from baserow.contrib.database.fields.exceptions import (
    AllProvidedMultipleSelectValuesMustBeSelectOption,
    AllProvidedValuesMustBeIntegersOrStrings,
)
from baserow.contrib.database.fields.field_converters import (
    MultipleSelectConversionConfig,
)
from baserow.contrib.database.fields.field_types import MultipleSelectFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    EmailField,
    Field,
    MultipleSelectField,
    NumberField,
    SelectOption,
    SingleSelectField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GridView
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_call_apps_registry_pending_operations(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    field_handler = FieldHandler()
    field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Test",
    )
    table.get_model()
    # Make sure that there are no pending operations in the app registry. Because a
    # Django ManyToManyField registers pending operations every time a table model is
    # generated, which can causes a memory leak if they are not triggered.
    assert len(apps._pending_operations) == 0


@pytest.mark.django_db
def test_multi_select_field_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    select_options_initial = [{"value": "Option 1", "color": "blue"}]
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multiple Select",
        select_options=select_options_initial,
    )
    field_id = field.db_column

    assert MultipleSelectField.objects.all().first().id == field.id
    assert SelectOption.objects.all().count() == 1

    select_options = field.select_options.all()
    assert len(select_options) == 1
    assert select_options[0].order == 0
    assert select_options[0].field_id == field.id
    assert select_options[0].value == "Option 1"
    assert select_options[0].color == "blue"

    select_options = field.select_options.all()
    row = row_handler.create_row(
        user=user, table=table, values={field_id: [select_options[0].id]}
    )
    assert row.id
    row_multi_select_field_list = getattr(row, field_id).order_by("order").all()
    assert len(row_multi_select_field_list) == 1
    assert row_multi_select_field_list[0].id == select_options[0].id
    assert row_multi_select_field_list[0].value == select_options[0].value
    assert row_multi_select_field_list[0].color == select_options[0].color
    assert row_multi_select_field_list[0].field_id == select_options[0].field_id

    field_handler.update_field(
        user=user,
        field=field,
        table=table,
        select_options=[
            {"id": select_options[0].id, "value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "green"},
        ],
    )

    row_multi_select_field_list = getattr(row, field_id).order_by("order").all()
    assert len(row_multi_select_field_list) == 1

    select_options = field.select_options.all()
    assert len(select_options) == 2
    assert SelectOption.objects.all().count() == 2

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        values={field_id: [select_options[0].id, select_options[1].id]},
    )

    assert row_2.id
    row_multi_select_field_list = getattr(row_2, field_id).order_by("order").all()
    assert len(row_multi_select_field_list) == 2
    assert row_multi_select_field_list[0].id == select_options[0].id
    assert row_multi_select_field_list[0].value == select_options[0].value
    assert row_multi_select_field_list[0].color == select_options[0].color
    assert row_multi_select_field_list[0].field_id == select_options[0].field_id
    assert row_multi_select_field_list[1].id == select_options[1].id
    assert row_multi_select_field_list[1].value == select_options[1].value
    assert row_multi_select_field_list[1].color == select_options[1].color
    assert row_multi_select_field_list[1].field_id == select_options[1].field_id

    through_model = row_2._meta.get_field(field_id).remote_field.through
    through_model_fields = through_model._meta.get_fields()
    row_field_name = through_model_fields[1].name

    assert len(through_model.objects.filter(**{row_field_name: row_2.id})) == 2

    # Test option removal behaviour
    field_handler.update_field(
        user=user,
        field=field,
        table=table,
        select_options=[
            {"id": select_options[0].id, "value": "Option 1", "color": "blue"},
        ],
    )

    select_options = field.select_options.all()
    assert len(select_options) == 1
    assert SelectOption.objects.all().count() == 1

    row_multi_select_field_list = getattr(row_2, field_id).order_by("order").all()
    assert len(row_multi_select_field_list) == 1
    # Check that no link exist anymore with the deleted option
    assert len(through_model.objects.filter(**{row_field_name: row.id})) == 1
    assert len(through_model.objects.filter(**{row_field_name: row_2.id})) == 1


@pytest.mark.django_db
def test_multiple_select_field_type_rows(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    other_select_option_multiple_select_field = data_fixture.create_select_option()

    field_handler = FieldHandler()
    row_handler = RowHandler()

    other_multiple_field = field_handler.create_field(
        user=user,
        table=table,
        name="Other Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 3", "color": "blue"},
        ],
    )
    other_multiple_field_select_options = other_multiple_field.select_options.all()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "red"},
            {"value": "Option 2", "color": "blue"},
        ],
    )

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_row(
            user=user, table=table, values={f"field_{field.id}": [999999]}
        )

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_row(
            user=user,
            table=table,
            values={
                f"field_{field.id}": [other_select_option_multiple_select_field.id]
            },
        )

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": [other_multiple_field_select_options[0].id]},
        )

    select_options = field.select_options.all()

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": [select_options[0].id, 9999]},
        )

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": [select_options[0].id, "not existing option"]},
        )

    with pytest.raises(AllProvidedValuesMustBeIntegersOrStrings):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": [select_options[0].id, []]},
        )

    with pytest.raises(AllProvidedValuesMustBeIntegersOrStrings):
        row_handler.create_row(
            user=user,
            table=table,
            values={f"field_{field.id}": [{}]},
        )

    row_0 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": [select_options[0].id]}
    )

    row_0_field = getattr(row_0, f"field_{field.id}").all()
    assert len(row_0_field) == 1
    assert row_0_field[0].id == select_options[0].id
    assert row_0_field[0].value == select_options[0].value
    assert row_0_field[0].color == select_options[0].color

    # Use the name of the option instead of the id
    row_1 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": [select_options[1].value]}
    )

    row_1_field = getattr(row_1, f"field_{field.id}").all()
    assert len(row_1_field) == 1
    assert row_1_field[0].id == select_options[1].id
    assert row_1_field[0].value == select_options[1].value
    assert row_1_field[0].color == select_options[1].color

    field = field_handler.update_field(
        user=user,
        field=field,
        select_options=[
            {"value": "Option 3", "color": "orange"},
            {"value": "Option 4", "color": "purple"},
        ],
    )

    select_options = field.select_options.all()
    assert len(select_options) == 2
    row_2 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": [select_options[0].id]}
    )
    row_2_field = getattr(row_2, f"field_{field.id}").all()
    assert len(row_2_field) == 1
    assert getattr(row_2_field[0], "id") == select_options[0].id
    assert getattr(row_2_field[0], "value") == select_options[0].value
    assert getattr(row_2_field[0], "color") == select_options[0].color

    row_3 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": [select_options[1].id]}
    )
    row_3_field = getattr(row_3, f"field_{field.id}").all()
    assert len(row_3_field) == 1
    assert getattr(row_3_field[0], "id") == select_options[1].id
    assert getattr(row_3_field[0], "value") == select_options[1].value

    row_4 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": [select_options[0].id]}
    )
    row_4_field = getattr(row_4, f"field_{field.id}").all()
    assert len(row_4_field) == 1
    assert getattr(row_4_field[0], "id") == select_options[0].id
    assert getattr(row_4_field[0], "value") == select_options[0].value

    row_5 = row_handler.create_row(user=user, table=table)
    row_5_field = getattr(row_5, f"field_{field.id}").all()
    assert len(row_5_field) == 0

    model = table.get_model()

    with django_assert_num_queries(3):
        rows = list(model.objects.all().enhance_by_fields())

    assert len(getattr(rows[0], f"field_{field.id}").all()) == 0
    assert len(getattr(rows[1], f"field_{field.id}").all()) == 0
    assert getattr(rows[2], f"field_{field.id}").all()[0].id == select_options[0].id
    assert getattr(rows[3], f"field_{field.id}").all()[0].id == select_options[1].id
    assert getattr(rows[4], f"field_{field.id}").all()[0].id == select_options[0].id

    row_0.refresh_from_db()
    assert len(getattr(row_0, f"field_{field.id}").all()) == 0

    row_4 = row_handler.update_row_by_id(
        user=user, table=table, row_id=row_4.id, values={f"field_{field.id}": []}
    )
    assert len(getattr(row_4, f"field_{field.id}").all()) == 0

    # Check that text value mixed with ids works and select the right id in case of
    # duplicate
    field = field_handler.update_field(
        user=user,
        field=field,
        select_options=[
            {"value": "Option 3", "color": "orange"},
            {"value": "Option 4", "color": "purple"},
            {"value": "Option 3", "color": "blue"},
        ],
    )

    select_options = field.select_options.all()
    row_5 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": [
                select_options[1].id,
                select_options[2].value,  # option 0 should be selected
            ]
        },
    )
    row_5_field = getattr(row_5, f"field_{field.id}").all()
    assert len(row_5_field) == 2
    assert set([getattr(row_5_field[0], "id"), getattr(row_5_field[1], "id")]) == set(
        [select_options[1].id, select_options[0].id]
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_multiple_select_field_type_multiple_rows(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "red"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "orange"},
            {"value": "Option 1", "color": "black"},
        ],
    )

    select_options = field.select_options.all()

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": [select_options[0].id]},
                {f"field_{field.id}": [select_options[0].id, 999999]},
                {f"field_{field.id}": [select_options[1].id]},
            ],
        )

    with pytest.raises(AllProvidedMultipleSelectValuesMustBeSelectOption):
        row_handler.create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": [select_options[0].id]},
                {f"field_{field.id}": [select_options[0].id, "Missing option"]},
                {f"field_{field.id}": [select_options[1].id]},
            ],
        )

    row_handler.create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": [select_options[0].id, select_options[1].value]},
            {f"field_{field.id}": [select_options[2].value, select_options[0].id]},
            {f"field_{field.id}": [select_options[2].id, select_options[3].value]},
            {f"field_{field.id}": [select_options[3].id, select_options[3].value]},
            {f"field_{field.id}": [select_options[0].id, select_options[3].value]},
            {f"field_{field.id}": [select_options[0].id, select_options[0].id]},
        ],
    )

    model = table.get_model()

    row_0, row_1, row_2, row_3, row_4, row_5 = model.objects.all()

    row_0_field = getattr(row_0, f"field_{field.id}").all()
    assert len(row_0_field) == 2
    assert getattr(row_0_field[0], "id") == select_options[0].id
    assert getattr(row_0_field[1], "id") == select_options[1].id

    row_1_field = getattr(row_1, f"field_{field.id}").all()
    assert len(row_1_field) == 2
    assert getattr(row_1_field[0], "id") == select_options[2].id
    assert getattr(row_1_field[1], "id") == select_options[0].id

    row_2_field = getattr(row_2, f"field_{field.id}").all()
    assert len(row_2_field) == 2
    assert getattr(row_2_field[0], "id") == select_options[2].id
    assert getattr(row_2_field[1], "id") == select_options[0].id

    row_3_field = getattr(row_3, f"field_{field.id}").all()
    assert len(row_3_field) == 2
    assert getattr(row_3_field[0], "id") == select_options[3].id
    assert getattr(row_3_field[1], "id") == select_options[0].id

    row_4_field = getattr(row_4, f"field_{field.id}").all()
    assert len(row_4_field) == 1
    assert getattr(row_4_field[0], "id") == select_options[0].id

    row_5_field = getattr(row_5, f"field_{field.id}").all()
    assert len(row_5_field) == 1
    assert getattr(row_5_field[0], "id") == select_options[0].id

    error_report = row_handler.create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": [select_options[0].id, "missing"]},
            {f"field_{field.id}": [select_options[0].id, select_options[3].value]},
            {f"field_{field.id}": [select_options[2].value, 999999]},
            {f"field_{field.id}": [99999, "missing"]},
        ],
        generate_error_report=True,
    ).errors

    assert list(error_report.keys()) == [0, 2, 3]
    assert f"field_{field.id}" in error_report[0]
    assert f"field_{field.id}" in error_report[2]
    assert f"field_{field.id}" in error_report[3]


@pytest.mark.django_db
def test_multiple_select_field_type_sorting(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    view_handler = ViewHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
    )
    option_a = data_fixture.create_select_option(field=field, value="A", color="red")
    option_b = data_fixture.create_select_option(field=field, value="B", color="blue")
    option_c = data_fixture.create_select_option(field=field, value="C", color="green")

    values_1 = [option_c.id, option_a.id, option_b.id]
    values_2 = [option_b.id, option_a.id]
    values_3 = [option_a.id, option_c.id, option_b.id]
    values_4 = []
    row_1 = data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=values_1, user=user
    )
    row_2 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_2, user=user
    )
    row_3 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_3, user=user
    )
    row_4 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_4, user=user
    )

    sort = data_fixture.create_view_sort(view=grid_view, field=field, order="ASC")
    model = table.get_model()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_4.id, row_3.id, row_2.id, row_1.id]
    sort.order = "DESC"
    sort.save()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_1.id, row_2.id, row_3.id, row_4.id]

    option_a.value = "Z"
    option_a.save()
    sort.order = "ASC"
    sort.save()
    model = table.get_model()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_4.id, row_2.id, row_1.id, row_3.id]


@pytest.mark.django_db
def test_multiple_select_field_type_deleting_select_option(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    field_handler = FieldHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
    )
    field_id = f"field_{field.id}"
    option_a = data_fixture.create_select_option(field=field, value="A", color="red")
    option_b = data_fixture.create_select_option(field=field, value="B", color="blue")
    option_c = data_fixture.create_select_option(field=field, value="C", color="green")

    select_options = field.select_options.all()
    select_option_ids_before = [x.id for x in select_options]

    assert len(select_options) == 3

    values_1 = [option_c.id, option_a.id, option_b.id]
    values_2 = [option_b.id, option_a.id]
    values_3 = [option_a.id, option_c.id, option_b.id]
    values_4 = []
    row_1 = data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=values_1, user=user
    )
    row_2 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_2, user=user
    )
    row_3 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_3, user=user
    )
    row_4 = data_fixture.create_row_for_many_to_many_field(
        table, field, values_4, user=user
    )

    assert len(getattr(row_1, field_id).all()) == len(values_1)
    assert len(getattr(row_2, field_id).all()) == len(values_2)
    assert len(getattr(row_3, field_id).all()) == len(values_3)
    assert len(getattr(row_4, field_id).all()) == len(values_4)

    updated_select_options = [
        {"id": option.id, "value": option.value, "color": option.color}
        for option in select_options
        if not option.value == "A"
    ]
    field_handler.update_field_select_options(
        user=user, field=field, select_options=updated_select_options
    )
    select_options = field.select_options.all()
    select_option_ids_after = [x.id for x in select_options]
    assert len(select_options) == 2
    assert any(
        option_id in select_option_ids_after for option_id in select_option_ids_before
    )

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()

    row_1_field = getattr(row_1, field_id).all()
    row_2_field = getattr(row_2, field_id).all()
    row_3_field = getattr(row_3, field_id).all()
    row_4_field = getattr(row_4, field_id).all()

    assert len(row_1_field) == 2
    assert any([x.id in [option_b.id, option_c.id] for x in row_1_field])

    assert len(row_2_field) == 1
    assert any([x.id in [option_b.id] for x in row_1_field])

    assert len(row_3_field) == 2
    assert any([x.id in [option_b.id, option_c.id] for x in row_1_field])

    assert len(row_4_field) == 0


@pytest.mark.django_db
def test_multi_select_enhance_queryset(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    example_table = data_fixture.create_database_table(
        name="Example", database=database
    )
    field_handler = FieldHandler()
    row_handler = RowHandler()

    multiselect_row_field = field_handler.create_field(
        user=user,
        table=example_table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )
    select_options = multiselect_row_field.select_options.all()

    row_handler.create_row(
        user=user,
        table=example_table,
        values={
            f"field_{multiselect_row_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=example_table,
        values={
            f"field_{multiselect_row_field.id}": [
                select_options[0].id,
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=example_table,
        values={
            f"field_{multiselect_row_field.id}": [
                select_options[0].id,
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    model = example_table.get_model()
    rows = list(model.objects.all().enhance_by_fields())

    with django_assert_num_queries(0):
        for row in rows:
            list(getattr(row, f"field_{multiselect_row_field.id}").all())


@pytest.mark.django_db
def test_multiple_select_field_type_random_value(data_fixture):
    """
    Verify that the random_value function of the single select field type correctly
    returns one option of a given select_options list. If the select_options list is
    empty or the passed field type is not of single select field type by any chance
    it should return None.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field_handler = FieldHandler()
    cache = {}
    fake = Faker()

    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multiple select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
            {"value": "Option 3", "color": "white"},
            {"value": "Option 4", "color": "green"},
        ],
    )

    select_options = field.select_options.all()
    random_choice = MultipleSelectFieldType().random_value(field, fake, cache)
    assert type(random_choice) is list
    assert set([x.id for x in select_options]).issuperset(set(random_choice)) is True

    random_choice = MultipleSelectFieldType().random_value(field, fake, cache)
    assert type(random_choice) is list
    assert set([x.id for x in select_options]).issuperset(set(random_choice)) is True

    email_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="email",
        name="E-Mail",
    )
    random_choice_2 = MultipleSelectFieldType().random_value(email_field, fake, cache)
    assert random_choice_2 is None


@pytest.mark.django_db
def test_import_export_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
            {"value": "Option 3", "color": "white"},
            {"value": "Option 4", "color": "green"},
        ],
    )
    select_option = field.select_options.all().first()
    field_type = field_type_registry.get_by_model(field)
    field_serialized = field_type.export_serialized(field)
    id_mapping = {}
    field_imported = field_type.import_serialized(
        table,
        field_serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        DeferredForeignKeyUpdater(),
    )

    assert field_imported.select_options.all().count() == 4
    imported_select_option = field_imported.select_options.all().first()
    assert imported_select_option.id != select_option.id
    assert imported_select_option.value == select_option.value
    assert imported_select_option.color == select_option.color
    assert imported_select_option.order == select_option.order


@pytest.mark.django_db
def test_import_serialized_value_with_missing_select_options(data_fixture):
    table = data_fixture.create_database_table()
    database = table.database
    workspace = database.workspace

    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="field"
    )
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field, value="Option 2"
    )

    model = table.get_model(attribute_names=True)
    row = model.objects.create()
    row.field.set([option_1.id, option_2.id])

    # The relationship between the row and the delete option will still exist.
    option_2.delete()

    config = ImportExportConfig(include_permission_data=False)
    serialized = application_type_registry.get_by_model(database).export_serialized(
        database, config, BytesIO()
    )
    imported_database = application_type_registry.get_by_model(
        database
    ).import_serialized(
        workspace,
        serialized,
        config,
        {},
        DeferredForeignKeyUpdater(),
    )

    imported_model = imported_database.table_set.all()[0].get_model(
        attribute_names=True
    )
    imported_row = imported_model.objects.all()[0]

    assert len(imported_row.field.all()) == 1


@pytest.mark.django_db(transaction=True)
def test_get_set_export_serialized_value_multiple_select_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()
    core_handler = CoreHandler()

    multiselect_row_field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )
    select_options = multiselect_row_field.select_options.all()

    row_handler.create_row(
        user=user,
        table=table,
        values={},
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{multiselect_row_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{multiselect_row_field.id}": [
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )
    assert len(SelectOption.objects.all()) == 3

    config = ImportExportConfig(include_permission_data=False)

    exported_applications = core_handler.export_workspace_applications(
        workspace, BytesIO(), config
    )
    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )
    imported_database = imported_applications[0]
    imported_table = imported_database.table_set.all()[0]
    imported_field = imported_table.field_set.all().first().specific

    assert imported_table.id != table.id
    assert imported_field.id != multiselect_row_field.id
    assert len(SelectOption.objects.all()) == 6

    imported_model = imported_table.get_model()
    all = imported_model.objects.all()
    assert len(all) == 3
    imported_row_1 = all[0]
    imported_row_1_field = (
        getattr(imported_row_1, f"field_" f"{imported_field.id}")
        .order_by("order")
        .all()
    )
    imported_row_2 = all[1]
    imported_row_2_field = (
        getattr(imported_row_2, f"field_{imported_field.id}").order_by("order").all()
    )
    imported_row_3 = all[2]
    imported_row_3_field = (
        getattr(imported_row_3, f"field_{imported_field.id}").order_by("order").all()
    )

    assert len(imported_row_1_field) == 0

    assert len(imported_row_2_field) == 2
    assert imported_row_2_field[0].id != select_options[0].id
    assert imported_row_2_field[0].value == select_options[0].value
    assert imported_row_2_field[0].color == select_options[0].color
    assert imported_row_2_field[1].id != select_options[1].id
    assert imported_row_2_field[1].value == select_options[1].value
    assert imported_row_2_field[1].color == select_options[1].color

    assert len(imported_row_3_field) == 2
    assert imported_row_3_field[0].id != select_options[1].id
    assert imported_row_3_field[0].value == select_options[1].value
    assert imported_row_3_field[0].color == select_options[1].color
    assert imported_row_3_field[1].id != select_options[2].id
    assert imported_row_3_field[1].value == select_options[2].value
    assert imported_row_3_field[1].color == select_options[2].color


@pytest.mark.django_db
def test_conversion_single_select_to_multiple_select_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Single Select",
        type_name="single_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    select_options = field.select_options.all()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[0].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[1].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[2].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[2].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[2].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": select_options[2].id,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": None,
        },
    )

    assert SingleSelectField.objects.all().first().id == field.id

    field_handler.update_field(user=user, field=field, new_type_name="multiple_select")

    field_type = field_type_registry.get_by_model(field)
    select_options = field.select_options.all()
    model = table.get_model()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 3
    assert MultipleSelectField.objects.all().first().id == field.id
    assert SingleSelectField.objects.all().count() == 0

    rows = list(model.objects.all().enhance_by_fields())
    row_0, row_1, *_, row_7 = rows
    # Check first row
    row_multi_select_field_list_0 = getattr(row_0, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_0) == 1
    assert row_multi_select_field_list_0[0].id == select_options[0].id
    assert row_multi_select_field_list_0[0].value == select_options[0].value

    # Check second row
    row_multi_select_field_list_1 = getattr(row_1, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_1) == 1
    assert row_multi_select_field_list_1[0].id == select_options[1].id
    assert row_multi_select_field_list_1[0].value == select_options[1].value

    # Check empty row
    row_multi_select_field_list_7 = getattr(row_7, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_7) == 0


@pytest.mark.django_db
def test_conversion_multiple_select_to_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Multi Select",
        type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    select_options = field.select_options.all()
    # Row1
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[select_options[0].id, select_options[1].id],
        user=user,
    )

    # Row2
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[select_options[1].id, select_options[2].id],
        user=user,
    )

    # Row3
    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=[select_options[2].id], user=user
    )

    # Row4
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[select_options[1].id, select_options[2].id],
        user=user,
    )

    # Row5
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[select_options[2].id, select_options[1].id],
        user=user,
    )

    # Row6
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[select_options[0].id, select_options[1].id, select_options[2].id],
        user=user,
    )

    assert MultipleSelectField.objects.all().first().id == field.id

    field = field_handler.update_field(
        user=user, field=field, new_type_name="single_select"
    )

    field_type = field_type_registry.get_by_model(field)
    select_options = field.select_options.all()
    model = table.get_model()
    assert field_type.type == "single_select"
    assert len(select_options) == 3
    assert SingleSelectField.objects.all().first().id == field.id
    assert MultipleSelectField.objects.all().count() == 0

    # Check first row
    rows = list(model.objects.all().enhance_by_fields())
    row_0, row_1, row_2, row_3, row_4, row_5 = rows
    row_multiple_select_field_list_0 = getattr(row_0, f"field_{field.id}")
    assert row_multiple_select_field_list_0.id == select_options[0].id
    assert row_multiple_select_field_list_0.value == select_options[0].value

    # Check second row
    row_multiple_select_field_list_1 = getattr(row_1, f"field_{field.id}")
    assert row_multiple_select_field_list_1.id == select_options[1].id
    assert row_multiple_select_field_list_1.value == select_options[1].value

    # Check third row
    row_multiple_select_field_list_2 = getattr(row_2, f"field_{field.id}")
    assert row_multiple_select_field_list_2.id == select_options[2].id
    assert row_multiple_select_field_list_2.value == select_options[2].value

    # Check fourth row
    row_multiple_select_field_list_3 = getattr(row_3, f"field_{field.id}")
    assert row_multiple_select_field_list_3.id == select_options[1].id
    assert row_multiple_select_field_list_3.value == select_options[1].value

    # Check fifth row
    row_multiple_select_field_list_4 = getattr(row_4, f"field_{field.id}")
    assert row_multiple_select_field_list_4.id == select_options[2].id
    assert row_multiple_select_field_list_4.value == select_options[2].value

    # Check sixth row
    row_multiple_select_field_list_5 = getattr(row_5, f"field_{field.id}")
    assert row_multiple_select_field_list_5.id == select_options[0].id
    assert row_multiple_select_field_list_5.value == select_options[0].value


@pytest.mark.django_db
def test_converting_multiple_select_field_value(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field, value="Option 1"
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field, value="Option 2"
    )

    assert len(SelectOption.objects.all()) == 2
    row = row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{multiple_select_field.id}": [option_1.id]},
    )
    # We have to add option_2 in a separate request so we have the guarantee that the
    # m2m through table id for option_2 is greater than option_1 for the ordering
    # assertion to be correct later.
    row_handler.update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={f"field_{multiple_select_field.id}": [option_1.id, option_2.id]},
    )

    text_field = field_handler.update_field(
        user=user, field=multiple_select_field, new_type_name="text"
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{text_field.id}": "Option 3"},
    )

    # empty row
    row_handler.create_row(
        user=user,
        table=table,
    )

    # create row with additional whitespace
    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{text_field.id}": "Option 3, "},
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{text_field.id}": "Option 3,Option 2"},
    )

    assert len(SelectOption.objects.all()) == 0
    model = table.get_model()
    rows = model.objects.all()

    assert getattr(rows[0], f"field_{text_field.id}") == ", ".join(
        [option_1.value, option_2.value]
    )

    # Converting back to multiple select using the unique row values as input,
    # should automatically add the right options.
    unique_values = field_handler.get_unique_row_values(
        field=text_field, limit=10, split_comma_separated=True
    )
    multiple_select_field = field_handler.update_field(
        user=user,
        field=text_field,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )
    model = table.get_model()
    rows = model.objects.all()
    assert len(SelectOption.objects.all()) == 3
    row_0, row_1, row_2, row_3, row_4 = rows
    cell_1 = getattr(row_0, f"field_{multiple_select_field.id}")
    cell_2 = getattr(row_1, f"field_{multiple_select_field.id}")
    cell_3 = getattr(row_2, f"field_{multiple_select_field.id}")
    cell_4 = getattr(row_3, f"field_{multiple_select_field.id}")
    cell_5 = getattr(row_4, f"field_{multiple_select_field.id}")
    assert len(cell_1.all()) == 2
    assert len(cell_2.all()) == 1
    assert len(cell_3.all()) == 0
    assert len(cell_4.all()) == 1
    assert len(cell_5.all()) == 2


@pytest.mark.django_db
def test_conversion_number_to_multiple_select_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Number",
        type_name="number",
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 1,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 2,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 3,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 4,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 5,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": 6,
        },
    )

    assert NumberField.objects.all().first().id == field.id

    unique_values = field_handler.get_unique_row_values(
        field=field, limit=10, split_comma_separated=True
    )
    field_handler.update_field(
        user=user,
        field=field,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )

    field_type = field_type_registry.get_by_model(field)
    select_options = field.select_options.all()
    model = table.get_model()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 6
    assert MultipleSelectField.objects.all().first().id == field.id

    row_0, row_1, row_2, row_3, row_4, row_5 = list(
        model.objects.all().enhance_by_fields()
    )
    # Check first row
    row_multi_select_field_list_0 = getattr(row_0, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_0) == 1
    assert row_multi_select_field_list_0[0].value == "1"

    # Check second row
    row_multi_select_field_list_1 = getattr(row_1, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_1) == 1
    assert row_multi_select_field_list_1[0].value == "2"

    # Check third row
    row_multi_select_field_list_2 = getattr(row_2, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_2) == 1
    assert row_multi_select_field_list_2[0].value == "3"

    # Check fourth row
    row_multi_select_field_list_3 = getattr(row_3, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_3) == 1
    assert row_multi_select_field_list_3[0].value == "4"

    # Check fifth row
    row_multi_select_field_list_4 = getattr(row_4, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_4) == 1
    assert row_multi_select_field_list_4[0].value == "5"

    # Check third row
    row_multi_select_field_list_5 = getattr(row_5, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_5) == 1
    assert row_multi_select_field_list_5[0].value == "6"


@pytest.mark.django_db
def test_conversion_email_to_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Email",
        type_name="email",
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname1@mail.de",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname2@mail.de",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname3@mail.de",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname4@mail.de",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname5@mail.de",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "myname6@mail.de",
        },
    )

    assert EmailField.objects.all().first().id == field.id

    unique_values = field_handler.get_unique_row_values(
        field=field, limit=10, split_comma_separated=True
    )
    field_handler.update_field(
        user=user,
        field=field,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )

    field_type = field_type_registry.get_by_model(field)
    select_options = field.select_options.all()
    model = table.get_model()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 6
    assert MultipleSelectField.objects.all().first().id == field.id

    rows = list(model.objects.all().enhance_by_fields())
    # Check first row
    row_multi_select_field_list_0 = getattr(rows[0], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_0) == 1
    assert row_multi_select_field_list_0[0].value == "myname1@mail.de"

    # Check second row
    row_multi_select_field_list_1 = getattr(rows[1], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_1) == 1
    assert row_multi_select_field_list_1[0].value == "myname2@mail.de"

    # Check third row
    row_multi_select_field_list_2 = getattr(rows[2], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_2) == 1
    assert row_multi_select_field_list_2[0].value == "myname3@mail.de"

    # Check fourth row
    row_multi_select_field_list_3 = getattr(rows[3], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_3) == 1
    assert row_multi_select_field_list_3[0].value == "myname4@mail.de"

    # Check fifth row
    row_multi_select_field_list_4 = getattr(rows[4], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_4) == 1
    assert row_multi_select_field_list_4[0].value == "myname5@mail.de"

    # Check sixth row
    row_multi_select_field_list_5 = getattr(rows[5], f"field_{field.id}").all()
    assert len(row_multi_select_field_list_5) == 1
    assert row_multi_select_field_list_5[0].value == "myname6@mail.de"


@pytest.mark.django_db
def test_conversion_date_to_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    date_field_eu = field_handler.create_field(
        user=user, table=table, type_name="date", date_format="EU", name="date_field_eu"
    )
    date_field_us = field_handler.create_field(
        user=user, table=table, type_name="date", date_format="US", name="date_field_us"
    )
    date_field_iso = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="ISO",
        name="date_field_iso",
    )
    date_field_eu_12 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="EU",
        date_include_time=True,
        date_time_format="12",
        name="date_field_eu_12",
    )
    date_field_us_12 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="US",
        date_include_time=True,
        date_time_format="12",
        name="date_field_us_12",
    )
    date_field_iso_12 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="ISO",
        date_include_time=True,
        date_time_format="12",
        name="date_field_iso_12",
    )
    date_field_eu_24 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="EU",
        date_include_time=True,
        date_time_format="24",
        name="date_field_eu_24",
    )
    date_field_us_24 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="US",
        date_include_time=True,
        date_time_format="24",
        name="date_field_us_24",
    )
    date_field_iso_24 = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        date_format="ISO",
        date_include_time=True,
        date_time_format="24",
        name="date_field_iso_24",
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{date_field_eu.id}": "2021-08-31",
            f"field_{date_field_us.id}": "2021-08-31",
            f"field_{date_field_iso.id}": "2021-08-31",
            f"field_{date_field_eu_12.id}": "2021-08-31 11:00:00",
            f"field_{date_field_us_12.id}": "2021-08-31 11:00:00",
            f"field_{date_field_iso_12.id}": "2021-08-31 11:00:00",
            f"field_{date_field_eu_24.id}": "2021-08-31 11:00:00",
            f"field_{date_field_us_24.id}": "2021-08-31 11:00:00",
            f"field_{date_field_iso_24.id}": "2021-08-31 11:00:00",
        },
    )

    all_fields = [
        date_field_eu,
        date_field_us,
        date_field_iso,
        date_field_eu_12,
        date_field_us_12,
        date_field_iso_12,
        date_field_eu_24,
        date_field_us_24,
        date_field_iso_24,
    ]

    all_results = [
        "31/08/2021",
        "08/31/2021",
        "2021-08-31",
        "31/08/2021 11:00 AM",
        "08/31/2021 11:00 AM",
        "2021-08-31 11:00 AM",
        "31/08/2021 11:00",
        "08/31/2021 11:00",
        "2021-08-31 11:00",
    ]

    for index, field in enumerate(all_fields):
        field_handler.update_field(
            user=user,
            field=field,
            new_type_name="multiple_select",
            **{
                "type": "multiple_select",
                "select_options": [{"value": all_results[index], "color": "red"}],
            },
        )

        field_model = field_handler.get_field(field.id)
        field_type = field_type_registry.get_by_model(field_model.specific_class)
        # Update field value after type change
        # all_fields[index] = field_model.specific
        select_options = field.select_options.all()
        assert field_type.type == "multiple_select"
        assert len(select_options) == 1

    model = table.get_model(attribute_names=True)
    rows = list(model.objects.all().enhance_by_fields())

    for index, field in enumerate(all_fields):
        cell = getattr(rows[0], field.model_attribute_name).all()
        assert len(cell) == 1
        assert cell[0].value == all_results[index]

    # convert multiple_select field back into date
    # if there is another select_option added then
    # we expect to not have any value in that cell
    new_select_option = data_fixture.create_select_option(
        field=date_field_eu, value="01/09/2021", color="green"
    )
    select_options = list(date_field_eu.select_options.all())

    row = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{date_field_eu.id}": [select_options[0].id],
        },
    )

    row_handler.update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={
            f"field_{date_field_eu.id}": [getattr(x, "id") for x in select_options],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{date_field_eu.id}": [new_select_option.id],
        },
    )

    date_field_eu = field_handler.update_field(
        user=user,
        field=date_field_eu,
        new_type_name="date",
        date_format="EU",
    )

    model = table.get_model(attribute_names=True)
    rows = list(model.objects.all().enhance_by_fields())

    assert rows[0].datefieldeu == date(2021, 8, 31)
    assert rows[1].datefieldeu == date(2021, 8, 31)
    assert rows[2].datefieldeu == date(2021, 9, 1)


@pytest.mark.django_db
def test_convert_long_text_to_multiple_select(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user, table=table, type_name="long_text", name="Text"
    )
    field_value = "This is a description, with several, commas."
    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": field_value},
    )
    multiple_select_field = field_handler.update_field(
        user=user,
        field=field,
        new_type_name="multiple_select",
        **{
            "type": "multiple_select",
            "select_options": [
                {"value": value, "color": "red"} for value in field_value.split(", ")
            ],
        },
    )

    assert len(field.select_options.all()) == 3
    model = table.get_model()
    rows = model.objects.all()

    cell = getattr(rows[0], f"field_{multiple_select_field.id}").all()
    assert len(cell) == 3
    assert cell[0].value == "This is a description"
    assert cell[1].value == "with several"
    assert cell[2].value == "commas."


@pytest.mark.django_db
def test_multiple_select_with_single_select_present(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="single_select",
        name="Single",
        select_options=[
            {"value": "Option 1", "color": "red"},
            {"value": "Option 2", "color": "blue"},
        ],
    )

    field_handler.create_field(
        user=user, table=table, type_name="multiple_select", name="Multi"
    )

    single_options = multiple_select_field.select_options.all()
    first_select_option = single_options[0]

    assert type(first_select_option) is SelectOption

    row = row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{multiple_select_field.id}": single_options[0]},
    )

    field_cell = getattr(row, f"field_{multiple_select_field.id}")
    assert field_cell.id == first_select_option.id
    assert field_cell.value == first_select_option.value
    assert field_cell.color == first_select_option.color


@pytest.mark.django_db
def test_convert_multiple_select_to_text(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "orange"},
        ],
    )
    options = field.select_options.all()
    assert len(SelectOption.objects.all()) == 2

    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, user=user, values=[options[0].id, options[1].id]
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, user=user, values=[options[1].id, options[0].id]
    )

    field = field_handler.update_field(user=user, field=field, new_type_name="text")
    assert len(SelectOption.objects.all()) == 0

    model = table.get_model()
    row_1, row_2 = model.objects.all()

    cell_1 = getattr(row_1, f"field_{field.id}")
    cell_2 = getattr(row_2, f"field_{field.id}")
    assert cell_1 == "Option 1, Option 2"
    assert cell_2 == "Option 2, Option 1"


@pytest.mark.django_db
def test_convert_multiple_select_to_text_with_comma_and_quotes(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "orange"},
            {"value": "Option 3,", "color": "red"},
        ],
    )
    options = field.select_options.all()
    assert len(SelectOption.objects.all()) == 3

    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, user=user, values=[options[0].id, options[1].id]
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, user=user, values=[options[2].id, options[1].id]
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, user=user, values=[options[2].id]
    )

    field = field_handler.update_field(user=user, field=field, new_type_name="text")
    assert len(SelectOption.objects.all()) == 0

    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": 'Option 1, "Option 3,", Option 4'},
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": '"Option 3,"'},
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{field.id}": '"Option 3,",'},
    )

    model = table.get_model()
    row_1, row_2, row_3, row_4, row_5, row_6 = model.objects.all()

    cell_1 = getattr(row_1, f"field_{field.id}")
    cell_2 = getattr(row_2, f"field_{field.id}")
    cell_3 = getattr(row_3, f"field_{field.id}")
    cell_4 = getattr(row_4, f"field_{field.id}")
    cell_5 = getattr(row_5, f"field_{field.id}")
    cell_6 = getattr(row_6, f"field_{field.id}")

    assert cell_1 == "Option 1, Option 2"
    # we want to make sure that the converted select option containing a "comma"
    # is correctly quoted
    assert cell_2 == '"Option 3,", Option 2'
    assert cell_3 == '"Option 3,"'
    assert cell_4 == 'Option 1, "Option 3,", Option 4'
    assert cell_5 == '"Option 3,"'
    assert cell_6 == '"Option 3,",'

    # converting back to multiple select should create 'Option 3,' without quotes
    unique_values = field_handler.get_unique_row_values(
        field=field, limit=10, split_comma_separated=True
    )
    field = field_handler.update_field(
        user=user,
        field=field,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )
    assert len(SelectOption.objects.all()) == 4

    model = table.get_model()
    row_1, row_2, row_3, row_4, row_5, row_6 = model.objects.all()

    cell_1 = getattr(row_1, f"field_{field.id}").all()
    cell_2 = getattr(row_2, f"field_{field.id}").all()
    cell_3 = getattr(row_3, f"field_{field.id}").all()
    cell_4 = getattr(row_4, f"field_{field.id}").all()
    cell_5 = getattr(row_5, f"field_{field.id}").all()
    cell_6 = getattr(row_6, f"field_{field.id}").all()

    assert len(cell_1) == 2
    assert cell_1[0].value == "Option 1"
    assert cell_1[1].value == "Option 2"

    assert len(cell_2) == 2
    assert cell_2[0].value == "Option 3,"
    assert cell_2[1].value == "Option 2"

    assert len(cell_3) == 1
    assert cell_3[0].value == "Option 3,"

    assert len(cell_4) == 3
    assert cell_4[0].value == "Option 1"
    assert cell_4[1].value == "Option 3,"
    assert cell_4[2].value == "Option 4"

    assert len(cell_5) == 1
    assert cell_5[0].value == "Option 3,"

    assert len(cell_6) == 1
    assert cell_6[0].value == "Option 3,"


@pytest.mark.django_db
def test_conversion_to_multiple_select_field_with_select_options(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field = field_handler.create_field(
        user=user,
        table=table,
        name="Text",
        type_name="text",
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "Option 1",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "Option 2",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": "Option 3",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field.id}": None,
        },
    )

    field_handler.update_field(
        user=user,
        field=field,
        new_type_name="multiple_select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 3", "color": "green"},
        ],
    )

    field_type = field_type_registry.get_by_model(field)
    select_options = field.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 2
    model = table.get_model()

    row_0, row_1, row_2, row_3 = list(model.objects.all().enhance_by_fields())
    # Check first row
    row_multi_select_field_list_0 = getattr(row_0, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_0) == 1
    assert row_multi_select_field_list_0[0].value == "Option 1"

    # Check second row
    row_multi_select_field_list_1 = getattr(row_1, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_1) == 0

    # Check third row
    row_multi_select_field_list_2 = getattr(row_2, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_2) == 1
    assert row_multi_select_field_list_2[0].value == "Option 3"

    # Check fourth row
    row_multi_select_field_list_3 = getattr(row_3, f"field_{field.id}").all()
    assert len(row_multi_select_field_list_3) == 0


@pytest.mark.django_db
def test_conversion_to_multiple_select_with_more_than_threshold_options_in_extraction(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Text",
        type_name="long_text",
    )

    field_2 = field_handler.create_field(
        user=user,
        table=table,
        name="Text 2",
        type_name="long_text",
    )

    conversion_config = MultipleSelectConversionConfig()
    long_text_string_items = []
    for i in range(conversion_config.new_select_options_threshold):
        option_string = f"Option {i}"
        long_text_string_items.append(option_string)

    long_text_string = ",".join(long_text_string_items)

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": long_text_string,
            f"field_{field_2.id}": f"{long_text_string}, Option X",
        },
    )

    unique_values = field_handler.get_unique_row_values(
        field=field_1, limit=200, split_comma_separated=True
    )
    field_handler.update_field(
        user=user,
        field=field_1,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )

    field_type = field_type_registry.get_by_model(field_1)
    select_options = field_1.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == conversion_config.new_select_options_threshold

    field_handler.update_field(
        user=user,
        field=field_2,
        new_type_name="multiple_select",
    )

    field_type = field_type_registry.get_by_model(field_2)
    select_options = field_2.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 0

    model = table.get_model()

    rows = list(model.objects.all().enhance_by_fields())
    # Check first row
    row_multi_select_field_list_0 = getattr(rows[0], f"field_{field_2.id}").all()
    assert len(row_multi_select_field_list_0) == 0


@pytest.mark.django_db
def test_conversion_to_multiple_select_with_more_than_threshold_options_provided(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Text",
        type_name="long_text",
    )

    field_2 = field_handler.create_field(
        user=user,
        table=table,
        name="Text 2",
        type_name="long_text",
    )

    conversion_config = MultipleSelectConversionConfig()
    provided_select_options = []
    for i in range(conversion_config.new_select_options_threshold):
        option = {"value": f"Option {i}", "color": "blue"}
        provided_select_options.append(option)

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": "Option 1",
            f"field_{field_2.id}": "Option X",
        },
    )

    field_handler.update_field(
        user=user,
        field=field_1,
        new_type_name="multiple_select",
        select_options=provided_select_options,
    )

    field_type = field_type_registry.get_by_model(field_1)
    select_options = field_1.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == conversion_config.new_select_options_threshold

    provided_select_options.append({"value": "Option X", "color": "green"})
    field_handler.update_field(
        user=user,
        field=field_2,
        new_type_name="multiple_select",
        select_options=provided_select_options,
    )

    field_type = field_type_registry.get_by_model(field_2)
    select_options = field_2.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == conversion_config.new_select_options_threshold + 1

    model = table.get_model()

    rows = list(model.objects.all().enhance_by_fields())
    # Check first row
    row_multi_select_field_1 = getattr(rows[0], f"field_{field_1.id}").all()
    row_multi_select_field_2 = getattr(rows[0], f"field_{field_2.id}").all()
    assert len(row_multi_select_field_1) == 1
    assert row_multi_select_field_1[0].value == "Option 1"
    assert len(row_multi_select_field_2) == 1
    assert row_multi_select_field_2[0].value == "Option X"


@pytest.mark.django_db
def test_conversion_to_multiple_select_with_option_value_too_large(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Text",
        type_name="long_text",
    )

    conversion_config = MultipleSelectConversionConfig()

    too_long_string_for_select_option = "X" * 300
    not_too_long_string = "This is not too long."
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": too_long_string_for_select_option,
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": not_too_long_string,
        },
    )

    unique_values = field_handler.get_unique_row_values(
        field=field_1, limit=10, split_comma_separated=True
    )
    field_handler.update_field(
        user=user,
        field=field_1,
        new_type_name="multiple_select",
        select_options=[
            {"value": value[:255], "color": "blue"} for value in unique_values
        ],
    )

    field_type = field_type_registry.get_by_model(field_1)
    select_options = field_1.select_options.all()
    assert field_type.type == "multiple_select"
    assert len(select_options) == 2

    model = table.get_model()
    row_1, row_2 = model.objects.all()
    cell_1 = getattr(row_1, f"field_{field_1.id}").all()
    cell_2 = getattr(row_2, f"field_{field_1.id}").all()

    assert len(cell_1) == 1
    assert len(cell_1[0].value) == conversion_config.allowed_select_options_length

    assert len(cell_2) == 1
    assert cell_2[0].value == not_too_long_string


@pytest.mark.django_db
def test_conversion_to_multiple_select_with_same_option_value_on_same_row(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field_handler = FieldHandler()
    row_handler = RowHandler()

    field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Text",
        type_name="long_text",
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": "test,test",
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{field_1.id}": "test, test",
        },
    )

    unique_values = field_handler.get_unique_row_values(
        field=field_1, limit=10, split_comma_separated=True
    )
    field_handler.update_field(
        user=user,
        field=field_1,
        new_type_name="multiple_select",
        select_options=[{"value": value, "color": "blue"} for value in unique_values],
    )

    field_type = field_type_registry.get_by_model(field_1)
    select_options = field_1.select_options.all()
    id_of_only_select_option = select_options[0].id
    assert field_type.type == "multiple_select"
    assert len(select_options) == 1

    model = table.get_model()
    rows = model.objects.all()
    row_1, row_2 = rows
    cell_1 = getattr(row_1, f"field_{field_1.id}").all()
    cell_2 = getattr(row_2, f"field_{field_1.id}").all()

    assert len(cell_1) == 1
    assert cell_1[0].id == id_of_only_select_option

    assert len(cell_2) == 1
    assert cell_2[0].id == id_of_only_select_option


@pytest.mark.django_db
def test_multiple_select_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue", order=0
    )
    option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red", order=1
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="C", color="green", order=2
    )
    data_fixture.create_view_sort(
        view=grid_view, field=multiple_select_field, order="ASC"
    )

    handler = RowHandler()
    [row_b, row_c, row_a] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{multiple_select_field.id}": [option_b.id],
            },
            {
                f"field_{multiple_select_field.id}": [option_c.id],
            },
            {
                f"field_{multiple_select_field.id}": [option_a.id],
            },
        ],
    ).created_rows

    base_queryset = ViewHandler().apply_sorting(
        grid_view, table.get_model().objects.all()
    )

    assert base_queryset[0].id == row_a.id
    assert base_queryset[1].id == row_b.id
    assert base_queryset[2].id == row_c.id

    table_model = table.get_model()
    previous_row = handler.get_adjacent_row(
        table_model, row_b.id, previous=True, view=grid_view
    )
    next_row = handler.get_adjacent_row(table_model, row_b.id, view=grid_view)

    assert previous_row.id == row_a.id
    assert next_row.id == row_c.id


@pytest.mark.django_db
def test_num_queries_n_number_of_multiple_select_field_get_rows_query(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue", order=0
    )
    option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red", order=1
    )

    handler = RowHandler()
    handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{multiple_select_field.id}": [option_a.id],
            },
            {
                f"field_{multiple_select_field.id}": [option_b.id],
            },
        ],
    )

    model = table.get_model()

    with CaptureQueriesContext(connection) as query_1:
        result = list(model.objects.all().enhance_by_fields())
        list(getattr(result[0], f"field_{multiple_select_field.id}").all())
        list(getattr(result[1], f"field_{multiple_select_field.id}").all())

    multiple_select_field_2 = data_fixture.create_multiple_select_field(
        table=table, name="option_field_2", order=2, primary=True
    )
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field_2, value="1", color="blue", order=0
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field_2, value="2", color="red", order=1
    )

    model = table.get_model()
    rows = list(model.objects.all())
    print(rows)
    getattr(rows[0], f"field_{multiple_select_field_2.id}").set([option_1.id])
    rows[0].save()
    getattr(rows[1], f"field_{multiple_select_field_2.id}").set([option_2.id])
    rows[1].save()

    with CaptureQueriesContext(connection) as query_2:
        result = list(model.objects.all().enhance_by_fields())
        list(getattr(result[0], f"field_{multiple_select_field.id}").all())
        list(getattr(result[0], f"field_{multiple_select_field_2.id}").all())
        list(getattr(result[1], f"field_{multiple_select_field.id}").all())
        list(getattr(result[1], f"field_{multiple_select_field_2.id}").all())

    assert len(query_1.captured_queries) == len(query_2.captured_queries)


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.row_history
def test_multiple_select_serialize_metadata_for_row_history(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
            {"value": "Option 3", "color": "white"},
            {"value": "Option 4", "color": "green"},
        ],
    )
    model = table.get_model()
    row_handler = RowHandler()
    select_options = field.select_options.all()
    original_row = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )
    select_option_1_id = select_options[0].id
    select_option_2_id = select_options[1].id
    select_option_3_id = select_options[2].id
    original_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        metadata = MultipleSelectFieldType().serialize_metadata_for_row_history(
            field, original_row, None
        )

    getattr(original_row, f"field_{field.id}").set([select_options[2].id], clear=True)
    updated_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        metadata = MultipleSelectFieldType().serialize_metadata_for_row_history(
            field, updated_row, metadata
        )

        assert metadata == {
            "id": AnyInt(),
            "select_options": {
                select_option_1_id: {
                    "color": "blue",
                    "id": select_option_1_id,
                    "value": "Option 1",
                },
                select_option_2_id: {
                    "color": "red",
                    "id": select_option_2_id,
                    "value": "Option 2",
                },
                select_option_3_id: {
                    "color": "white",
                    "id": select_option_3_id,
                    "value": "Option 3",
                },
            },
            "type": "multiple_select",
        }

    # empty values
    original_row = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={f"field_{field.id}": []},
    )
    original_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        assert MultipleSelectFieldType().serialize_metadata_for_row_history(
            field, original_row, None
        ) == {
            "id": AnyInt(),
            "select_options": {},
            "type": "multiple_select",
        }


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.row_history
def test_multiple_select_are_row_values_equal(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "red"},
            {"value": "Option 3", "color": "white"},
            {"value": "Option 4", "color": "green"},
        ],
    )
    option_a = data_fixture.create_select_option(field=field, value="A", color="blue")
    option_b = data_fixture.create_select_option(field=field, value="B", color="red")

    with django_assert_num_queries(0):
        assert (
            MultipleSelectFieldType().are_row_values_equal([option_a.id], [option_a.id])
            is True
        )

        assert (
            MultipleSelectFieldType().are_row_values_equal(
                [option_a.id, option_b.id], [option_b.id, option_a.id]
            )
            is True
        )

        assert MultipleSelectFieldType().are_row_values_equal([], []) is True

        assert (
            MultipleSelectFieldType().are_row_values_equal([], [option_a.id]) is False
        )

        assert (
            MultipleSelectFieldType().are_row_values_equal([option_a.id], [option_b.id])
            is False
        )


@pytest.mark.django_db
def test_get_group_by_metadata_in_rows_with_many_to_many_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )

    RowHandler().force_create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{text_field.id}": "Row 1",
                f"field_{multiple_select_field.id}": [],
            },
            {
                f"field_{text_field.id}": "Row 2",
                f"field_{multiple_select_field.id}": [],
            },
            {
                f"field_{text_field.id}": "Row 3",
                f"field_{multiple_select_field.id}": [select_option_1.id],
            },
            {
                f"field_{text_field.id}": "Row 4",
                f"field_{multiple_select_field.id}": [select_option_1.id],
            },
            {
                f"field_{text_field.id}": "Row 5",
                f"field_{multiple_select_field.id}": [select_option_2.id],
            },
            {
                f"field_{text_field.id}": "Row 6",
                f"field_{multiple_select_field.id}": [select_option_2.id],
            },
            {
                f"field_{text_field.id}": "Row 7",
                f"field_{multiple_select_field.id}": [
                    select_option_1.id,
                    select_option_2.id,
                ],
            },
            {
                f"field_{text_field.id}": "Row 8",
                f"field_{multiple_select_field.id}": [
                    select_option_1.id,
                    select_option_2.id,
                ],
            },
            {
                f"field_{text_field.id}": "Row 9",
                f"field_{multiple_select_field.id}": [
                    select_option_2.id,
                    select_option_1.id,
                ],
            },
        ],
    ).created_rows

    model = table.get_model()

    queryset = model.objects.all().enhance_by_fields()
    rows = list(queryset)

    handler = ViewHandler()
    counts = handler.get_group_by_metadata_in_rows(
        [multiple_select_field], rows, queryset
    )

    # Resolve the queryset, so that we can do a comparison.
    for c in counts.keys():
        counts[c] = list(counts[c])

    assert counts == {
        multiple_select_field: unordered(
            [
                {"count": 2, f"field_{multiple_select_field.id}": []},
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [select_option_1.id],
                },
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [
                        select_option_1.id,
                        select_option_2.id,
                    ],
                },
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [select_option_2.id],
                },
                {
                    "count": 1,
                    f"field_{multiple_select_field.id}": [
                        select_option_2.id,
                        select_option_1.id,
                    ],
                },
            ]
        )
    }


@pytest.mark.django_db
def test_list_rows_with_group_by_and_many_to_many_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )
    select_option_3 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=3,
        value="Option 2",
        color="blue",
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=multiple_select_field)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{multiple_select_field.id}": [
                select_option_1.id,
                select_option_2.id,
                select_option_3.id,
            ],
        },
    )

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()

    assert response_json["group_by_metadata"] == {
        f"field_{multiple_select_field.id}": unordered(
            [
                {
                    f"field_{multiple_select_field.id}": [
                        select_option_1.id,
                        select_option_2.id,
                        select_option_3.id,
                    ],
                    "count": 1,
                },
            ]
        ),
    }


@pytest.mark.django_db
def test_get_group_by_metadata_in_rows_multiple_and_single_select_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    ms_option_1 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=1,
        value="A",
        color="blue",
    )
    ms_option_2 = data_fixture.create_select_option(
        field=multiple_select_field,
        order=2,
        value="B",
        color="blue",
    )

    single_select_field = data_fixture.create_single_select_field(table=table)
    ss_option_1 = data_fixture.create_select_option(
        field=single_select_field,
        order=1,
        value="1",
        color="blue",
    )
    ss_option_2 = data_fixture.create_select_option(
        field=single_select_field,
        order=2,
        value="2",
        color="blue",
    )

    RowHandler().force_create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{text_field.id}": "Row 1",
                f"field_{multiple_select_field.id}": [],
                f"field_{single_select_field.id}": None,
            },
            {
                f"field_{text_field.id}": "Row 2",
                f"field_{multiple_select_field.id}": [],
                f"field_{single_select_field.id}": ss_option_1.id,
            },
            {
                f"field_{text_field.id}": "Row 3",
                f"field_{multiple_select_field.id}": [ms_option_1.id],
                f"field_{single_select_field.id}": ss_option_1.id,
            },
            {
                f"field_{text_field.id}": "Row 4",
                f"field_{multiple_select_field.id}": [ms_option_1.id],
                f"field_{single_select_field.id}": ss_option_2.id,
            },
            {
                f"field_{text_field.id}": "Row 5",
                f"field_{multiple_select_field.id}": [ms_option_2.id],
                f"field_{single_select_field.id}": ss_option_2.id,
            },
            {
                f"field_{text_field.id}": "Row 6",
                f"field_{multiple_select_field.id}": [ms_option_2.id],
            },
            {
                f"field_{text_field.id}": "Row 7",
                f"field_{multiple_select_field.id}": [
                    ms_option_1.id,
                    ms_option_2.id,
                ],
            },
            {
                f"field_{text_field.id}": "Row 8",
                f"field_{multiple_select_field.id}": [
                    ms_option_1.id,
                    ms_option_2.id,
                ],
            },
            {
                f"field_{text_field.id}": "Row 9",
                f"field_{multiple_select_field.id}": [
                    ms_option_2.id,
                    ms_option_1.id,
                ],
            },
        ],
    ).created_rows

    model = table.get_model()

    queryset = model.objects.all().enhance_by_fields()
    rows = list(queryset)

    handler = ViewHandler()
    counts = handler.get_group_by_metadata_in_rows(
        [multiple_select_field, single_select_field], rows, queryset
    )

    # Resolve the queryset, so that we can do a comparison.
    for c in counts.keys():
        counts[c] = list(counts[c])

    assert counts == {
        multiple_select_field: unordered(
            [
                {"count": 2, f"field_{multiple_select_field.id}": []},
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [ms_option_1.id],
                },
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [
                        ms_option_1.id,
                        ms_option_2.id,
                    ],
                },
                {
                    "count": 2,
                    f"field_{multiple_select_field.id}": [ms_option_2.id],
                },
                {
                    "count": 1,
                    f"field_{multiple_select_field.id}": [
                        ms_option_2.id,
                        ms_option_1.id,
                    ],
                },
            ]
        ),
        single_select_field: unordered(
            [
                {
                    f"field_{single_select_field.id}": ss_option_1.id,
                    f"field_{multiple_select_field.id}": [ms_option_1.id],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": ss_option_1.id,
                    f"field_{multiple_select_field.id}": [],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": ss_option_2.id,
                    f"field_{multiple_select_field.id}": [ms_option_1.id],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": ss_option_2.id,
                    f"field_{multiple_select_field.id}": [ms_option_2.id],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": None,
                    f"field_{multiple_select_field.id}": [
                        ms_option_1.id,
                        ms_option_2.id,
                    ],
                    "count": 2,
                },
                {
                    f"field_{single_select_field.id}": None,
                    f"field_{multiple_select_field.id}": [ms_option_2.id],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": None,
                    f"field_{multiple_select_field.id}": [
                        ms_option_2.id,
                        ms_option_1.id,
                    ],
                    "count": 1,
                },
                {
                    f"field_{single_select_field.id}": None,
                    f"field_{multiple_select_field.id}": [],
                    "count": 1,
                },
            ]
        ),
    }


@pytest.mark.django_db
def test_multiple_select_field_type_get_order_collate(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )

    model = table.get_model()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(
        dir_path + "/../../../../../../tests/all_chars.txt", mode="r", encoding="utf-8"
    ) as f:
        all_chars = f.read()
    with open(
        dir_path + "/../../../../../../tests/sorted_chars.txt",
        mode="r",
        encoding="utf-8",
    ) as f:
        sorted_chars = f.read()

    options, rows = [], []
    for char in all_chars:
        options.append(
            SelectOption(field=multiple_select_field, value=char, color="blue", order=0)
        )
        rows.append(model())

    options = SelectOption.objects.bulk_create(options)
    rows = model.objects.bulk_create(rows)

    relations = []
    field_name = f"field_{multiple_select_field.id}"

    for row, option in zip(rows, options):
        relation, _ = RowHandler()._prepare_m2m_field_related_objects(
            row, field_name, [option.id]
        )
        relations.extend(relation)

    getattr(model, field_name).through.objects.bulk_create(relations)

    queryset = (
        model.objects.all()
        .order_by_fields_string(field_name)
        .prefetch_related(field_name)
    )
    result = ""
    for char in queryset:
        result += getattr(char, field_name).all()[0].value

    assert result == sorted_chars


@dataclass
class ViewWithFieldsSetup:
    user: AbstractUser
    table: Table
    grid_view: GridView
    fields: Dict[str, Field]
    model: Type[GeneratedTableModel]
    rows: List[Type[GeneratedTableModel]]
    options: List[SelectOption]


def setup_view_for_multiple_select_field(data_fixture, option_values):
    """
    Setup a view with a multiple select field and some options. `field_name` must be one
    of the following: "multiple_select", "ref_multiple_select",
    "ref_ref_multiple_select".
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="multiple_select"
    )
    formula_field = data_fixture.create_formula_field(
        table=table, formula="field('multiple_select')", name="ref_multiple_select"
    )
    ref_formula_field = data_fixture.create_formula_field(
        table=table,
        formula="field('ref_multiple_select')",
        name="ref_ref_multiple_select",
    )

    options = [
        data_fixture.create_select_option(field=multiple_select_field, value=value)
        if value
        else None
        for value in option_values
    ]

    model = table.get_model()

    def prep_row(options):
        if options is None:
            return {}
        return {multiple_select_field.db_column: [opt.id for opt in options]}

    rows = (
        RowHandler()
        .force_create_rows(
            user,
            table,
            [prep_row([option] if option is not None else None) for option in options],
            model=model,
        )
        .created_rows
    )

    fields = {
        "multiple_select": multiple_select_field,
        "ref_multiple_select": formula_field,
        "ref_ref_multiple_select": ref_formula_field,
    }

    return ViewWithFieldsSetup(
        user=user,
        table=table,
        grid_view=grid_view,
        fields=fields,
        model=model,
        rows=rows,
        options=options,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_has_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture, ["AAA", "AAB", "ABB", "BBB", None]
    )
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    field = test_setup.fields[field_name]
    rows = test_setup.rows
    (option_1, option_2, option_3, option_4, _) = test_setup.options
    options = (option_1, option_2, option_3, option_4)

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=field,
        type="multiple_select_has",
        value=f"{option_1.id},{option_2.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    # only two last (ABB, BBB) are selected
    assert len(ids) == 2
    # first two rows only
    assert set([r.id for r in rows[:2]]) == set(ids)

    # no match values
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    # all rows are visible because the value is empty.
    assert len(ids) == 5

    # no match values
    view_filter.value = "12345678,12345679,12345680"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    # all rows are filtered out
    assert ids == []

    # no match values
    view_filter.value = "true,false"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    # all rows are filtered out
    assert len(ids) == 0

    view_filter.value = ",".join([str(o.id) for o in options])
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    # all the rows with an option are selected
    assert len(ids) == 4
    assert set(ids) == set([o.id for o in rows[:4]])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_is_empty_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture,
        ["A", "B", None],
    )

    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3 = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="empty"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_is_not_empty_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(data_fixture, ["A", "B", None])
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3 = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="not_empty"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_contains_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture, ["A", "AA", "B", None]
    )
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3, _ = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="contains", value="A"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = "AA"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "B"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_contains_not_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture, ["A", "AA", "B", None]
    )
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3, row_4 = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="contains_not", value="A"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.value = "AA"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert ids == unordered([row_1.id, row_3.id, row_4.id])

    view_filter.value = "B"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert ids == unordered([row_1.id, row_2.id, row_4.id])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_contains_word_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture, ["A", "aa", "B", None]
    )
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3, row_4 = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="contains_word", value="A"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = "AA"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "B"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name", ["multiple_select", "ref_multiple_select", "ref_ref_multiple_select"]
)
def test_multiple_select_doest_contains_word_filter_type(field_name, data_fixture):
    test_setup = setup_view_for_multiple_select_field(
        data_fixture, ["A", "AA", "B", None]
    )
    handler = ViewHandler()
    grid_view = test_setup.grid_view
    model = test_setup.model
    row_1, row_2, row_3, row_4 = test_setup.rows
    field = test_setup.fields[field_name]

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, type="doesnt_contain_word", value="A"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert ids == unordered([row_2.id, row_3.id, row_4.id])

    view_filter.value = "AA"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert ids == unordered([row_1.id, row_3.id, row_4.id])

    view_filter.value = "B"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert ids == unordered([row_1.id, row_2.id, row_4.id])
