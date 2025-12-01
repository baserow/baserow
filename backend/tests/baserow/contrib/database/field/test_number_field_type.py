from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

import pytest
from rest_framework import serializers

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import DeferredForeignKeyUpdater
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
@pytest.mark.parametrize(
    "expected,field_kwargs",
    [
        (
            [
                9223372036854775807,
                100,
                100,
                101,
                0,
                0,
                0,
                0,
                None,
                None,
                None,
                None,
                None,
            ],
            {"number_decimal_places": 0, "number_negative": False},
        ),
        (
            [
                9223372036854775807,
                100,
                100,
                101,
                -9223372036854775808,
                -100,
                -100,
                -101,
                None,
                None,
                None,
                None,
                None,
            ],
            {"number_decimal_places": 0, "number_negative": True},
        ),
        (
            [
                Decimal("9223372036854775807.0"),
                Decimal("100.0"),
                Decimal("100.2"),
                Decimal("100.6"),
                Decimal("0.0"),
                Decimal("0.0"),
                Decimal("0.0"),
                Decimal("0.0"),
                None,
                None,
                None,
                None,
                None,
            ],
            {
                "number_negative": False,
                "number_decimal_places": 1,
            },
        ),
        (
            [
                Decimal("9223372036854775807.000"),
                Decimal("100.000"),
                Decimal("100.220"),
                Decimal("100.600"),
                Decimal("-9223372036854775808.0"),
                Decimal("-100.0"),
                Decimal("-100.220"),
                Decimal("-100.600"),
                None,
                None,
                None,
                None,
                None,
            ],
            {
                "number_negative": True,
                "number_decimal_places": 3,
            },
        ),
        (
            [
                Decimal("9223372036854775807.0000000000"),
                Decimal("100.0000000000"),
                Decimal("100.2200000000"),
                Decimal("100.5999900000"),
                Decimal("-9223372036854775808.00000000"),
                Decimal("-100.00000000"),
                Decimal("-100.2200000000"),
                Decimal("-100.5999000000"),
                None,
                None,
                None,
                None,
                None,
            ],
            {
                "number_negative": True,
                "number_decimal_places": 10,
            },
        ),
        (
            [
                9223372036854775807,
                100,
                100,
                101,
                0,
                0,
                0,
                0,
                None,
                None,
                None,
                None,
                None,
            ],
            {
                "number_decimal_places": 0,
                "number_negative": False,
                "number_prefix": "$",
                "number_suffix": "%",
            },
        ),
    ],
)
def test_alter_number_field_column_type(expected, field_kwargs, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1)

    handler = FieldHandler()
    field = handler.update_field(user=user, field=field, name="Text field")

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "9223372036854775807"})
    model.objects.create(**{f"field_{field.id}": "100"})
    model.objects.create(**{f"field_{field.id}": "100.22"})
    model.objects.create(**{f"field_{field.id}": "100.59999"})
    model.objects.create(**{f"field_{field.id}": "-9223372036854775808"})
    model.objects.create(**{f"field_{field.id}": "-100"})
    model.objects.create(**{f"field_{field.id}": "-100.22"})
    model.objects.create(**{f"field_{field.id}": "-100.5999"})
    model.objects.create(**{f"field_{field.id}": "100.59.99"})
    model.objects.create(**{f"field_{field.id}": "-100.59.99"})
    model.objects.create(**{f"field_{field.id}": "100TEST100.10"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^&&^^%$$"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^5.2&&^^%$$"})

    # Change the field type to a number and test if the values have been changed.
    field = handler.update_field(
        user=user, field=field, new_type_name="number", **field_kwargs
    )

    model = table.get_model()
    rows = model.objects.all()
    for index, row in enumerate(rows):
        assert getattr(row, f"field_{field.id}") == expected[index]


@pytest.mark.django_db
def test_alter_number_field_column_type_negative(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, number_negative=True
    )
    decimal_field = data_fixture.create_number_field(
        table=table,
        order=2,
        number_negative=True,
        number_decimal_places=2,
    )

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{number_field.id}": -10,
            f"field_{decimal_field.id}": Decimal("-10.10"),
        }
    )

    handler = FieldHandler()
    number_field = handler.update_field(
        user=user, field=number_field, number_negative=False
    )
    decimal_field = handler.update_field(
        user=user, field=decimal_field, number_negative=False
    )

    model = table.get_model()
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{number_field.id}") == 0
    assert getattr(rows[0], f"field_{decimal_field.id}") == 0.00


@pytest.mark.django_db
def test_import_export_number_field(data_fixture):
    number_field = data_fixture.create_number_field(
        name="Number field",
        number_negative=True,
        number_decimal_places=2,
    )
    number_field_type = field_type_registry.get_by_model(number_field)
    number_serialized = number_field_type.export_serialized(number_field)
    number_field_imported = number_field_type.import_serialized(
        number_field.table,
        number_serialized,
        ImportExportConfig(include_permission_data=True),
        {},
        DeferredForeignKeyUpdater(),
    )
    assert number_field.number_negative == number_field_imported.number_negative
    assert number_field.number_decimal_places == (
        number_field_imported.number_decimal_places
    )


@pytest.mark.django_db
def test_content_type_still_set_when_save_overridden(data_fixture):
    table = data_fixture.create_database_table()
    field = NumberField(
        number_negative=False,
        number_decimal_places=1,
        order=1,
        table=table,
    )
    assert field.content_type_id is None
    field.save()
    expected_content_type = ContentType.objects.get_for_model(NumberField)
    assert field.content_type == expected_content_type
    assert field.content_type_id == expected_content_type.id


@pytest.mark.django_db
def test_number_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    number_field = data_fixture.create_number_field(table=table)

    data_fixture.create_view_sort(view=grid_view, field=number_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{number_field.id}": 1,
            },
            {
                f"field_{number_field.id}": 2,
            },
            {
                f"field_{number_field.id}": 3,
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
def test_number_field_default_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    number_field = data_fixture.create_number_field(table=table, name="Number")

    row_handler = RowHandler()

    model = table.get_model()
    row_1 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_2 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{number_field.id}": 42},
    )
    assert getattr(row_1, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{number_field.id}") == 42

    field_handler = FieldHandler()
    number_field = field_handler.update_field(
        user=user, field=number_field, number_default=100
    )

    row_3 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_4 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{number_field.id}": 50},
    )
    assert getattr(row_3, f"field_{number_field.id}") == 100
    assert getattr(row_4, f"field_{number_field.id}") == 50

    number_field = field_handler.update_field(
        user=user, field=number_field, number_default=0
    )

    row_5 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    assert getattr(row_5, f"field_{number_field.id}") == 0

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()

    assert getattr(row_1, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{number_field.id}") == 42
    assert getattr(row_3, f"field_{number_field.id}") == 100
    assert getattr(row_4, f"field_{number_field.id}") == 50
    assert getattr(row_5, f"field_{number_field.id}") == 0


@pytest.mark.django_db
def test_number_field_serializer_default_with_required(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    field_with_default = data_fixture.create_number_field(
        table=table, number_decimal_places=0, number_default=0
    )
    field_without_default = data_fixture.create_number_field(
        table=table, number_decimal_places=0, number_default=None
    )

    field_type = field_type_registry.get_by_model(field_with_default)

    serializer_field_with_default = field_type.get_serializer_field(
        field_with_default, required=True
    )
    serializer_field_without_default = field_type.get_serializer_field(
        field_without_default, required=True
    )

    assert serializer_field_with_default.required is True
    assert serializer_field_with_default.allow_null is False
    assert serializer_field_with_default.default == serializers.empty

    assert serializer_field_without_default.required is True
    assert serializer_field_without_default.allow_null is False
    assert serializer_field_without_default.default is serializers.empty
