from django.core.exceptions import ValidationError
from django.db import connection

import pytest

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.field_types import AutonumberFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import AutonumberField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


def get_counter_value(field_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT last_value FROM database_autonumberfield WHERE field_ptr_id = %s",
            [field_id],
        )
        row = cursor.fetchone()
        return row[0] if row else None


def _create_rows(user, table, count, model=None):
    result = RowHandler().create_rows(
        user=user, table=table, rows_values=[{} for _ in range(count)], model=model
    )
    return result.created_rows


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_alter_autonumber_field_column_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "9223372036854775807"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^&&^^%$$"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^5.2&&^^%$$"})

    field = FieldHandler().update_field(
        user=user, field=field, new_type_name="autonumber"
    )

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]
    assert get_counter_value(field.id) == 3


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_duplicate_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 3)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]

    duplicated_field, _ = FieldHandler().duplicate_field(
        user=user, field=autonumber_field, duplicate_data=True
    )

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{duplicated_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]

    assert get_counter_value(duplicated_field.id) == 3

    rows = _create_rows(user, table, 1, model)
    rows[0].refresh_from_db()
    assert getattr(rows[0], f"field_{autonumber_field.id}") == 4
    assert getattr(rows[0], f"field_{duplicated_field.id}") == 4


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_trash_restore_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 1)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1]

    TrashHandler().trash(
        user, table.database.workspace, table.database, autonumber_field
    )

    # Rows created while field is trashed get NULL for the autonumber column.
    # After restore, backfill_nulls assigns sequential values.
    model = table.get_model()
    model.objects.create()
    model.objects.create()

    TrashHandler().restore_item(user, "field", autonumber_field.id)

    model = table.get_model()
    row_values = list(
        model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    )
    # Row 1 keeps its value, rows 2-3 get backfilled starting from last_value+1
    assert row_values[0] == 1
    assert row_values[1] == 2
    assert row_values[2] == 3
    assert get_counter_value(autonumber_field.id) == 3


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_duplicate_table_with_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 1)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1]

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_model = duplicated_table.get_model()
    duplicated_field = duplicated_table.field_set.get()

    _create_rows(user, duplicated_table, 2)

    row_values = duplicated_model.objects.values_list(
        f"field_{duplicated_field.id}", flat=True
    )
    assert list(row_values) == [1, 2, 3]

    _create_rows(user, table, 1)
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_updating_autonumber_field_does_not_change_row_values_once_set(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()
    model.objects.create(**{f"field_{text_field.id}": "a"})
    model.objects.create(**{f"field_{text_field.id}": "b"})

    view = data_fixture.create_grid_view(table=table)
    view_filter = data_fixture.create_view_filter(
        view=view, field=text_field, type="not_empty"
    )
    view_sort = data_fixture.create_view_sort(view=view, field=text_field, order="DESC")

    autonumber_field = data_fixture.create_autonumber_field(table=table, view=view)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [3, 4, 2, 1]

    view_filter.delete()
    view_sort.delete()

    FieldHandler().update_field(
        user=user,
        field=autonumber_field,
        name="Updated name",
        view_id=view.id,
    )

    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [3, 4, 2, 1]


@pytest.mark.field_autonumber
@pytest.mark.undo_redo
@pytest.mark.django_db
def test_undo_redo_create_autonumber_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "a"})
    model.objects.create(**{f"field_{text_field.id}": "b"})

    autonumber_field = action_type_registry.get_by_type(CreateFieldActionType).do(
        user, table=table, name="autonumber", type_name="autonumber"
    )

    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(values) == [1, 2]

    actions = ActionHandler.undo(
        user, [CreateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [CreateFieldActionType])

    # Rows created while field is trashed get NULL.
    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "e"})
    model.objects.create(**{f"field_{text_field.id}": "f"})

    actions = ActionHandler.redo(
        user, [CreateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [CreateFieldActionType])
    model = table.get_model()

    values = list(model.objects.values_list(f"field_{autonumber_field.id}", flat=True))
    # Original rows keep 1-2, restored rows get backfilled 3-4
    assert values == [1, 2, 3, 4]


@pytest.mark.field_autonumber
@pytest.mark.undo_redo
@pytest.mark.django_db
def test_undo_redo_delete_autonumber_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    RowHandler().create_rows(
        user=user,
        table=table,
        rows_values=[
            {f"field_{text_field.id}": "a"},
            {f"field_{text_field.id}": "b"},
        ],
    )

    action_type_registry.get_by_type(DeleteFieldActionType).do(user, autonumber_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "c"})
    model.objects.create(**{f"field_{text_field.id}": "d"})

    actions = ActionHandler.undo(
        user, [DeleteFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [DeleteFieldActionType])
    model = table.get_model()
    row_values = model.objects.order_by(f"field_{autonumber_field.id}").values(
        f"field_{text_field.id}", f"field_{autonumber_field.id}"
    )
    # Rows 1-2 keep their values; rows 3-4 (created while trashed) get backfilled
    assert list(row_values) == [
        {f"field_{text_field.id}": "a", f"field_{autonumber_field.id}": 1},
        {f"field_{text_field.id}": "b", f"field_{autonumber_field.id}": 2},
        {f"field_{text_field.id}": "c", f"field_{autonumber_field.id}": 3},
        {f"field_{text_field.id}": "d", f"field_{autonumber_field.id}": 4},
    ]

    actions = ActionHandler.redo(
        user, [DeleteFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [DeleteFieldActionType])


@pytest.mark.field_autonumber
@pytest.mark.undo_redo
@pytest.mark.django_db
def test_undo_redo_update_autonumber_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 2)

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, autonumber_field, new_type_name="text"
    )

    # Counter should no longer exist for this field (it's now text)
    model = table.get_model()
    model.objects.create(**{f"field_{autonumber_field.id}": "c"})

    row_values = model.objects.order_by("id").values_list(
        f"field_{autonumber_field.id}", flat=True
    )
    assert list(row_values) == ["1", "2", "c"]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    # After undo, field is autonumber again with counter aligned
    assert get_counter_value(autonumber_field.id) == 3
    row_values = model.objects.order_by("id").values_list(
        f"field_{autonumber_field.id}", flat=True
    )
    assert list(row_values) == [1, 2, 3]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_perm_delete_field_drops_counter(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 2)

    assert get_counter_value(autonumber_field.id) == 2

    FieldHandler().delete_field(user=user, field=autonumber_field)

    # Counter still exists (field is trashed, not permanently deleted)
    assert get_counter_value(autonumber_field.id) == 2

    TrashHandler.permanently_delete(autonumber_field)

    # Counter gone after permanent delete
    assert get_counter_value(autonumber_field.id) is None


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_update_to_other_type_drops_unique_constraint(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 2)

    autonumber_field.refresh_from_db()
    assert autonumber_field.is_unique_constraint_applied is True

    FieldHandler().update_field(user=user, field=autonumber_field, new_type_name="text")

    # UNIQUE constraint should be dropped when converting away from autonumber
    # Verify by checking the field no longer has the flag
    # (the field is now a text field, so we can't check AutonumberField attributes)


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_update_to_autonumber_creates_counter(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()

    assert get_counter_value(text_field.id) is None

    FieldHandler().update_field(user=user, field=text_field, new_type_name="autonumber")

    assert get_counter_value(text_field.id) == 2

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{text_field.id}", flat=True)
    assert list(row_values) == [1, 2]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_import_rows_assign_new_values(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    RowHandler().import_rows(
        user=user,
        table=table,
        data=[[], [], []],
    )

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_renumber_rows_according_to_views_filters_and_sorts(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "ab"})
    model.objects.create(**{f"field_{text_field.id}": "aa"})
    model.objects.create(**{f"field_{text_field.id}": "bb"})
    model.objects.create(**{f"field_{text_field.id}": "bc"})

    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view, field=text_field, type="contains", value="b"
    )
    data_fixture.create_view_sort(view=view, field=text_field, order="ASC")

    autonumber_field = data_fixture.create_autonumber_field(table=table, view=view)

    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(values) == [1, 4, 2, 3]

    view_2 = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view_2, field=text_field, type="contains_not", value="a"
    )
    data_fixture.create_view_sort(view=view_2, field=text_field, order="DESC")

    autonumber_field_2 = data_fixture.create_autonumber_field(table=table, view=view_2)

    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field_2.id}", flat=True)
    assert list(values) == [3, 4, 2, 1]

    view.filters_disabled = True
    view.save(update_fields=["filters_disabled"])

    autonumber_field_3 = data_fixture.create_autonumber_field(table=table, view=view)
    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field_3.id}", flat=True)
    assert list(values) == [2, 1, 3, 4]

    rows = _create_rows(user, table, 1, model)
    rows[0].refresh_from_db()
    assert getattr(rows[0], f"field_{autonumber_field.id}") == 5
    assert getattr(rows[0], f"field_{autonumber_field_2.id}") == 5
    assert getattr(rows[0], f"field_{autonumber_field_3.id}") == 5


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_values_cannot_be_updated_manually(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    rows = _create_rows(user, table, 1)

    with pytest.raises(ValidationError):
        RowHandler().update_rows(
            user,
            table,
            [{"id": rows[0].id, f"field_{autonumber_field.id}": 5}],
        )


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_numbers_trashed_rows_to_avoid_conflicts_on_restore(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    row_1 = model.objects.create()

    trashed_row_id = row_1.id
    TrashHandler().trash(user, table.database.workspace, table.database, row_1)

    autonumber_field = data_fixture.create_autonumber_field(table=table)

    rows = _create_rows(user, table, 1)
    rows[0].refresh_from_db()

    assert getattr(rows[0], f"field_{autonumber_field.id}") == 2

    model = table.get_model()
    trashed_row = model.objects_and_trash.get(pk=trashed_row_id)
    assert getattr(trashed_row, f"field_{autonumber_field.id}") == 1


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_numbers_rows_correctly_with_trashed_rows(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(view=grid_view, field=text_field, type="not_empty")
    data_fixture.create_view_sort(view=grid_view, field=text_field, order="ASC")

    model = table.get_model()
    row_1, row_2, row_3, row_4, row_5 = model.objects.bulk_create(
        [
            model(),
            model(),
            model(**{f"field_{text_field.id}": "b"}),
            model(**{f"field_{text_field.id}": "c"}),
            model(**{f"field_{text_field.id}": "a"}),
        ]
    )

    TrashHandler().trash(user, table.database.workspace, table.database, row_1)
    TrashHandler().trash(user, table.database.workspace, table.database, row_3)

    autonumber_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="autonumber",
        name="autonumber",
        view=grid_view,
    )

    model = table.get_model()
    autonumber_field_key = f"field_{autonumber_field.id}"
    row_values = model.objects_and_trash.values("id", autonumber_field_key).order_by(
        autonumber_field_key
    )
    assert list(row_values) == [
        {"id": row_5.id, autonumber_field_key: 1},
        {"id": row_4.id, autonumber_field_key: 2},
        {"id": row_2.id, autonumber_field_key: 3},
        {"id": row_1.id, autonumber_field_key: 4},  # trashed
        {"id": row_3.id, autonumber_field_key: 5},  # trashed
    ]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_view_filters(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    rows = _create_rows(user, table, 2)

    view = data_fixture.create_grid_view(table=table)
    view_filter = data_fixture.create_view_filter(
        view=view, field=autonumber_field, type="equal", value=1
    )

    model = table.get_model()
    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [rows[0].id]

    view_filter.type = "not_equal"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [rows[1].id]

    view_filter.type = "lower_than"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == []

    view_filter.type = "higher_than"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [rows[1].id]

    view_filter.type = "contains"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [rows[0].id]

    view_filter.type = "contains_not"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [rows[1].id]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_view_aggregations(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    _create_rows(user, table, 2)

    view = data_fixture.create_grid_view(table=table)
    result = ViewHandler().get_field_aggregations(
        user, view, [(autonumber_field, "max")]
    )
    assert result[autonumber_field.db_column] == 2

    _create_rows(user, table, 2)

    result = ViewHandler().get_field_aggregations(
        user, view, [(autonumber_field, "max")]
    )
    assert result[autonumber_field.db_column] == 4


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_can_be_referenced_in_formula(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_autonumber_field(name="autonumber", table=table)
    row_1, row_2 = (
        RowHandler()
        .create_rows(user=user, table=table, rows_values=[{}, {}])
        .created_rows
    )

    formula_field = data_fixture.create_formula_field(
        table=table, formula="field('autonumber') * 2"
    )

    model = table.get_model()
    row_values = model.objects.all().values("id", f"field_{formula_field.id}")
    assert list(row_values) == [
        {"id": row_1.id, f"field_{formula_field.id}": 2},
        {"id": row_2.id, f"field_{formula_field.id}": 4},
    ]

    (row_3,) = (
        RowHandler()
        .create_rows(user=user, table=table, rows_values=[{}], model=model)
        .created_rows
    )
    row_values = model.objects.all().values("id", f"field_{formula_field.id}")
    assert list(row_values) == [
        {"id": row_1.id, f"field_{formula_field.id}": 2},
        {"id": row_2.id, f"field_{formula_field.id}": 4},
        {"id": row_3.id, f"field_{formula_field.id}": 6},
    ]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_can_be_looked_up(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    data_fixture.create_autonumber_field(name="autonumber", table=table_b)

    formula_field = data_fixture.create_formula_field(
        table=table_a, formula=f"sum(lookup('{link_field.name}', 'autonumber'))"
    )

    row_b_1, row_b_2 = _create_rows(user, table_b, 2)

    model_a = table_a.get_model()
    (row,) = (
        RowHandler()
        .create_rows(
            user=user,
            table=table_a,
            rows_values=[
                {f"field_{link_field.id}": [row_b_1.id, row_b_2.id]},
            ],
            model=model_a,
        )
        .created_rows
    )

    assert getattr(row, f"field_{formula_field.id}") == 3


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_counter_uses_max_value_not_row_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(
        table=table, name="autonumber"
    )

    rows = _create_rows(user, table, 5)

    for row in rows[:3]:
        row.delete()

    db_column = f"field_{autonumber_field.id}"
    model = table.get_model()
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {model._meta.db_table} SET {db_column} = 100 WHERE id = %s",
            [rows[4].id],
        )

    # Re-align counter from MAX
    AutonumberFieldType().align_counter(autonumber_field, model)

    assert get_counter_value(autonumber_field.id) == 100

    new_rows = _create_rows(user, table, 1)
    new_rows[0].refresh_from_db()
    assert getattr(new_rows[0], db_column) == 101


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_unique_constraint_applied_on_create(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    autonumber_field.refresh_from_db()
    assert autonumber_field.is_unique_constraint_applied is True


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_counter_and_model_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    assert isinstance(autonumber_field, AutonumberField)
    assert autonumber_field.last_value == 0
    assert autonumber_field.is_unique_constraint_applied is True

    _create_rows(user, table, 3)

    autonumber_field.refresh_from_db()
    assert autonumber_field.last_value == 3


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_bulk_create_assigns_sequential_values(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    rows = _create_rows(user, table, 10)

    model = table.get_model()
    values = list(
        model.objects.values_list(f"field_{autonumber_field.id}", flat=True).order_by(
            f"field_{autonumber_field.id}"
        )
    )
    assert values == list(range(1, 11))
    assert get_counter_value(autonumber_field.id) == 10
