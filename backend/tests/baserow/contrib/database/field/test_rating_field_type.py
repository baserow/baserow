from decimal import Decimal

from django.core.exceptions import ValidationError

import pytest
from faker import Faker

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import RatingField
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_field_creation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1, name="name")

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="rating",
        name="rating",
        max_value=4,
        color="red",
        style="flag",
    )

    assert len(RatingField.objects.all()) == 1
    from_db = RatingField.objects.get(name="rating")
    assert from_db.color == "red"
    assert from_db.max_value == 4
    assert from_db.style == "flag"

    fake = Faker()
    value = fake.random_int(1, 4)
    model = table.get_model(attribute_names=True)
    row = model.objects.create(rating=value, name="Test")

    assert row.rating == value
    assert row.name == "Test"

    handler.delete_field(user=user, field=field)
    assert len(RatingField.objects.all()) == 0

    for invalid_value in [
        {"max_value": 11},
        {"max_value": 0},
        {"max_value": -2},
        {"style": "invalid"},
        {"style": ""},
        {"color": None},
        {"color": ""},
    ]:
        with pytest.raises(ValueError):
            handler.create_field(
                user=user,
                table=table,
                type_name="rating",
                name="rating invalid",
                **invalid_value,
            )


@pytest.mark.django_db
def test_row_creation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(table=table, order=1, name="name")
    field_handler = FieldHandler()
    row_handler = RowHandler()

    rating_field = field_handler.create_field(
        user=user, table=table, type_name="rating", name="rating"
    )
    assert len(RatingField.objects.all()) == 1

    model = table.get_model(attribute_names=True)

    row1 = row_handler.create_row(
        user=user, table=table, values={"rating": 3}, model=model
    )
    row_handler.create_row(user=user, table=table, values={"rating": 0}, model=model)
    row_handler.create_row(user=user, table=table, values={"rating": None}, model=model)
    row_handler.create_row(user=user, table=table, values={}, model=model)

    assert [(f.id, f.rating) for f in model.objects.all()] == [
        (1, 3),
        (2, 0),
        (3, 0),
        (4, 0),
    ]

    row_handler.update_row_by_id(
        user=user,
        row_id=row1.id,
        table=table,
        values={rating_field.id: 1},
    )

    assert [(f.id, f.rating) for f in model.objects.all()] == [
        (1, 1),
        (2, 0),
        (3, 0),
        (4, 0),
    ]

    for invalid_value in [-1, 6]:
        with pytest.raises(ValidationError):
            row_handler.create_row(
                user=user, table=table, values={"rating": invalid_value}, model=model
            )
            row_handler.update_row_by_id(
                user=user,
                row_id=row1.id,
                table=table,
                values={"rating": invalid_value},
            )


@pytest.mark.django_db
def test_rating_field_modification(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table(user=user, database=table.database)
    text_field = data_fixture.create_text_field(table=table, order=1, name="text")
    field_handler = FieldHandler()
    row_handler = RowHandler()

    rating_field = field_handler.create_field(
        user=user, table=table, type_name="rating", name="Rating"
    )

    integer_field = data_fixture.create_number_field(
        table=table,
        name="integer",
        number_decimal_places=0,
        number_negative=True,
    )

    decimal_field = data_fixture.create_number_field(
        table=table,
        name="decimal",
        number_decimal_places=1,
        number_negative=True,
    )

    boolean_field = data_fixture.create_boolean_field(table=table, name="boolean")

    model = table.get_model(attribute_names=True)

    row_handler.create_row(
        user=user,
        table=table,
        values={
            "text": "5",
            "rating": 5,
            "integer": 5,
            "decimal": 4.5,
            "boolean": True,
        },
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "text": "3",
            "rating": 4,
            "integer": 3,
            "decimal": 2.5,
            "boolean": False,
        },
        model=model,
    )
    row3 = row_handler.create_row(
        user=user,
        table=table,
        values={"text": "1", "rating": 3, "integer": 1, "decimal": 1.3},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"text": "1.5", "rating": 2, "integer": -1, "decimal": -1.2},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"text": "invalid", "rating": 1, "integer": -5, "decimal": -7},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={"text": "0", "rating": 0, "integer": 0, "decimal": 0},
        model=model,
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            "text": None,
            "rating": None,
            "integer": None,
            "number": None,
        },
        model=model,
    )

    # Convert text field to rating
    field_handler.update_field(
        user=user, field=text_field, new_type_name="rating", max_value=3
    )
    # Change max_value
    field_handler.update_field(user=user, field=rating_field, max_value=3)
    # Change field type from number -> rating
    field_handler.update_field(
        user=user,
        field=integer_field,
        new_type_name="rating",
        max_value=3,
    )
    field_handler.update_field(
        user=user,
        field=decimal_field,
        new_type_name="rating",
        max_value=3,
    )
    field_handler.update_field(
        user=user,
        field=boolean_field,
        new_type_name="rating",
        max_value=3,
    )

    # Check value clamping on max_value modification
    assert [
        (f.id, f.text, f.rating, f.integer, f.decimal, f.boolean)
        for f in model.objects.all()
    ] == [
        (1, 3, 3, 3, 3, 1),
        (2, 3, 3, 3, 3, 0),
        (3, 1, 3, 1, 1, 0),
        (4, 2, 2, 0, 0, 0),
        (5, 0, 1, 0, 0, 0),
        (6, 0, 0, 0, 0, 0),
        (7, 0, 0, 0, 0, 0),
    ]

    # Change boolean field to test conversion back with value != [0,1]
    row_handler.update_row_by_id(
        user=user,
        row_id=row3.id,
        table=table,
        values={boolean_field.id: 3},
    )

    # Convert back field to original type
    field_handler.update_field(user=user, field=text_field, new_type_name="text")
    field_handler.update_field(
        user=user,
        field=integer_field,
        new_type_name="number",
        number_decimal_places=0,
        number_negative=True,
    )
    field_handler.update_field(
        user=user,
        field=decimal_field,
        new_type_name="number",
        number_negative=True,
        number_decimal_places=2,
    )
    field_handler.update_field(
        user=user,
        field=boolean_field,
        new_type_name="boolean",
    )

    assert [
        (f.id, f.text, f.integer, f.decimal, f.boolean) for f in model.objects.all()
    ] == [
        (1, "3", Decimal("3"), Decimal("3.00"), True),
        (2, "3", Decimal("3"), Decimal("3.00"), False),
        (3, "1", Decimal("1"), Decimal("1.00"), True),
        (4, "2", Decimal("0"), Decimal("0.00"), False),
        (5, "0", Decimal("0"), Decimal("0.00"), False),
        (6, "0", Decimal("0"), Decimal("0.00"), False),
        (7, "0", Decimal("0"), Decimal("0.00"), False),
    ]


@pytest.mark.django_db
def test_rating_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    rating_field = data_fixture.create_rating_field(table=table)

    data_fixture.create_view_sort(view=grid_view, field=rating_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{rating_field.id}": 1,
            },
            {
                f"field_{rating_field.id}": 2,
            },
            {
                f"field_{rating_field.id}": 3,
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
