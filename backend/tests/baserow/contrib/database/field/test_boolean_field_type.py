import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_alter_boolean_field_column_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1)

    handler = FieldHandler()
    field = handler.update_field(user=user, field=field, name="Text field")

    model = table.get_model()
    mapping = {
        "1": True,
        "t": True,
        "y": True,
        "yes": True,
        "on": True,
        "YES": True,
        "checked": True,
        "Checked": True,
        "": False,
        "f": False,
        "n": False,
        "false": False,
        "off": False,
        "Random text": False,
    }

    for value in mapping.keys():
        model.objects.create(**{f"field_{field.id}": value})

    # Change the field type to a boolean and test if the values have been changed.
    field = handler.update_field(user=user, field=field, new_type_name="boolean")

    model = table.get_model()
    rows = model.objects.all()

    for index, value in enumerate(mapping.values()):
        assert getattr(rows[index], f"field_{field.id}") == value


@pytest.mark.django_db
def test_get_set_export_serialized_value_boolean_field(data_fixture):
    table = data_fixture.create_database_table()
    boolean_field = data_fixture.create_boolean_field(table=table)
    boolean_field_name = f"field_{boolean_field.id}"
    boolean_field_type = field_type_registry.get_by_model(boolean_field)

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create(**{f"field_{boolean_field.id}": True})
    row_3 = model.objects.create(**{f"field_{boolean_field.id}": False})

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()

    old_row_1_value = getattr(row_1, boolean_field_name)
    old_row_2_value = getattr(row_2, boolean_field_name)
    old_row_3_value = getattr(row_3, boolean_field_name)

    boolean_field_type.set_import_serialized_value(
        row_1,
        boolean_field_name,
        boolean_field_type.get_export_serialized_value(
            row_1, boolean_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )
    boolean_field_type.set_import_serialized_value(
        row_2,
        boolean_field_name,
        boolean_field_type.get_export_serialized_value(
            row_2, boolean_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )
    boolean_field_type.set_import_serialized_value(
        row_3,
        boolean_field_name,
        boolean_field_type.get_export_serialized_value(
            row_3, boolean_field_name, {}, None, None
        ),
        {},
        {},
        None,
        None,
    )

    row_1.save()
    row_2.save()
    row_3.save()

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()

    assert old_row_1_value == getattr(row_1, boolean_field_name)
    assert old_row_2_value == getattr(row_2, boolean_field_name)
    assert old_row_3_value == getattr(row_3, boolean_field_name)


@pytest.mark.django_db
def test_boolean_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    boolean_field = data_fixture.create_boolean_field(table=table)

    data_fixture.create_view_sort(view=grid_view, field=boolean_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{boolean_field.id}": False,
            },
            {
                f"field_{boolean_field.id}": True,
            },
            {
                f"field_{boolean_field.id}": True,
            },
        ],
        model=table_model,
    ).created_rows

    previous_row = handler.get_adjacent_row(
        table_model, row_c.id, previous=True, view=grid_view
    )
    next_row = handler.get_adjacent_row(table_model, row_c.id, view=grid_view)

    assert previous_row.id == row_b.id
    assert next_row.id == row_a.id


@pytest.mark.django_db
def test_boolean_field_default_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")

    row_handler = RowHandler()

    model = table.get_model()
    row_1 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_2 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{boolean_field.id}": True},
    )
    assert getattr(row_1, f"field_{boolean_field.id}") is False
    assert getattr(row_2, f"field_{boolean_field.id}") is True

    field_handler = FieldHandler()
    boolean_field = field_handler.update_field(
        user=user, field=boolean_field, boolean_default=True
    )

    row_3 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_4 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{boolean_field.id}": False},
    )
    assert getattr(row_3, f"field_{boolean_field.id}") is True
    assert getattr(row_4, f"field_{boolean_field.id}") is False

    boolean_field = field_handler.update_field(
        user=user, field=boolean_field, boolean_default=False
    )

    row_5 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    assert getattr(row_5, f"field_{boolean_field.id}") is False

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()

    assert getattr(row_1, f"field_{boolean_field.id}") is False
    assert getattr(row_2, f"field_{boolean_field.id}") is True
    assert getattr(row_3, f"field_{boolean_field.id}") is True
    assert getattr(row_4, f"field_{boolean_field.id}") is False
    assert getattr(row_5, f"field_{boolean_field.id}") is False
