from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.field_types import AutonumberFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


def does_field_sequence_exist(field_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.sequences where sequence_name = 'field_{field_id}_seq');"
        )
        return cursor.fetchone()[0]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_alter_autonumber_field_column_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, order=1)

    model = table.get_model()
    handler = FieldHandler()

    model.objects.create(**{f"field_{field.id}": "9223372036854775807"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^&&^^%$$"})
    model.objects.create(**{f"field_{field.id}": "!@#$%%^^5.2&&^^%$$"})

    field = handler.update_field(user=user, field=field, new_type_name="autonumber")

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_duplicate_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()

    model.objects.create()
    model.objects.create()
    model.objects.create()

    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]

    duplicated_field, _ = FieldHandler().duplicate_field(
        user=user, field=autonumber_field
    )

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{duplicated_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]

    # Both the fields should have its own sequence
    row = model.objects.create()
    row.refresh_from_db()
    assert getattr(row, f"field_{autonumber_field.id}") == 4
    assert getattr(row, f"field_{duplicated_field.id}") == 4


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_trash_restore_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create()

    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1]

    TrashHandler().trash(
        user, table.database.workspace, table.database, autonumber_field
    )

    # If we create new rows, the db default should provide the next number
    # and the values will be available once the field will be restored.
    model = table.get_model()
    model.objects.create()
    model.objects.create()

    TrashHandler().restore_item(user, "field", autonumber_field.id)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_duplicate_table_with_autonumber_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create()

    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1]

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_model = duplicated_table.get_model()
    duplicated_field = duplicated_table.field_set.get()

    duplicated_model.objects.create()
    duplicated_model.objects.create()

    row_values = duplicated_model.objects.values_list(
        f"field_{duplicated_field.id}", flat=True
    )
    assert list(row_values) == [1, 2, 3]

    model.objects.create()
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

    # Add a filter and a sort to the view and number rows based on that
    view = data_fixture.create_grid_view(table=table)
    view_filter = data_fixture.create_view_filter(
        view=view, field=text_field, type="not_empty"
    )
    view_sort = data_fixture.create_view_sort(view=view, field=text_field, order="DESC")

    autonumber_field = data_fixture.create_autonumber_field(table=table, view=view)

    model = table.get_model()
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [3, 4, 2, 1]

    # Removing filters and sorts should not change the values
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
    model.objects.create(**{f"field_{text_field.id}": "c"})
    model.objects.create(**{f"field_{text_field.id}": "d"})

    values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(values) == [1, 2, 3, 4]

    actions = ActionHandler.undo(
        user, [CreateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [CreateFieldActionType])

    model = table.get_model()
    # Even though the field is trashed, the sequence is not dropped so
    # the field will continue to save the number according to the sequence
    model.objects.create(**{f"field_{text_field.id}": "e"})
    model.objects.create(**{f"field_{text_field.id}": "f"})

    actions = ActionHandler.redo(
        user, [CreateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [CreateFieldActionType])
    model = table.get_model()

    values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(values) == [1, 2, 3, 4, 5, 6]


@pytest.mark.field_autonumber
@pytest.mark.undo_redo
@pytest.mark.django_db
def test_undo_redo_delete_autonumber_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "a"})
    model.objects.create(**{f"field_{text_field.id}": "b"})

    action_type_registry.get_by_type(DeleteFieldActionType).do(user, autonumber_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "c"})
    model.objects.create(**{f"field_{text_field.id}": "d"})

    actions = ActionHandler.undo(
        user, [DeleteFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [DeleteFieldActionType])
    model = table.get_model()
    row_values = model.objects.values(
        f"field_{text_field.id}", f"field_{autonumber_field.id}"
    )
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

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "a"})
    model.objects.create(**{f"field_{text_field.id}": "b"})

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, autonumber_field, new_type_name="text"
    )

    assert does_field_sequence_exist(autonumber_field.id) is False

    model = table.get_model()
    model.objects.create(**{f"field_{autonumber_field.id}": "c"})

    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    # numbers are converted to strings
    assert list(row_values) == ["1", "2", "c"]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(table.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert does_field_sequence_exist(autonumber_field.id) is True
    row_values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(row_values) == [1, 2, 3]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_perm_delete_field_drop_field_sequence(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()

    assert does_field_sequence_exist(autonumber_field.id) is True

    FieldHandler().delete_field(user=user, field=autonumber_field)

    assert does_field_sequence_exist(autonumber_field.id) is True

    TrashHandler.permanently_delete(autonumber_field)

    assert does_field_sequence_exist(autonumber_field.id) is False


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_update_to_other_type_drop_field_sequence(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()

    assert does_field_sequence_exist(autonumber_field.id) is True

    FieldHandler().update_field(user=user, field=autonumber_field, new_type_name="text")

    assert does_field_sequence_exist(autonumber_field.id) is False


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_update_to_autonumber_create_field_sequence(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()

    assert does_field_sequence_exist(text_field.id) is False

    FieldHandler().update_field(user=user, field=text_field, new_type_name="autonumber")

    assert does_field_sequence_exist(text_field.id) is True

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

    # Add a filter and a sort to the view and number rows based on that
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view, field=text_field, type="contains", value="b"
    )
    data_fixture.create_view_sort(view=view, field=text_field, order="ASC")

    autonumber_field = data_fixture.create_autonumber_field(table=table, view=view)

    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field.id}", flat=True)
    assert list(values) == [1, 4, 2, 3]

    # A second autonumber field in a different view should number rows according
    # to that view
    view_2 = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view_2, field=text_field, type="contains_not", value="a"
    )
    data_fixture.create_view_sort(view=view_2, field=text_field, order="DESC")

    autonumber_field_2 = data_fixture.create_autonumber_field(table=table, view=view_2)

    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field_2.id}", flat=True)
    assert list(values) == [3, 4, 2, 1]

    # If the filters are disabled, then the rows should be numbered only according
    # to sorts
    view.filters_disabled = True
    view.save(update_fields=["filters_disabled"])

    autonumber_field_3 = data_fixture.create_autonumber_field(table=table, view=view)
    model = table.get_model()
    values = model.objects.values_list(f"field_{autonumber_field_3.id}", flat=True)
    assert list(values) == [2, 1, 3, 4]

    # adding a row should increment the number for both fields
    row = model.objects.create(**{f"field_{text_field.id}": "e"})
    row.refresh_from_db()
    assert getattr(row, f"field_{autonumber_field.id}") == 5
    assert getattr(row, f"field_{autonumber_field_2.id}") == 5
    assert getattr(row, f"field_{autonumber_field_3.id}") == 5


def _create_table_with_related_fields(data_fixture):
    """
    Creates a table with three rows and fields whose sorts and filters rely on
    joins or annotations. In row order, the link row and multiple select values
    are "c", "a" and "b", and the single select values are "cherry", "apple" and
    "berry". The multiple select of the second row is empty instead of "a".
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    linked_table = data_fixture.create_database_table(database=database)
    linked_primary = data_fixture.create_text_field(table=linked_table, primary=True)
    handler = FieldHandler()
    fields = {
        "link_row": handler.create_field(
            user, table, "link_row", name="Link", link_row_table=linked_table
        )
    }
    fields["lookup"] = handler.create_field(
        user,
        table,
        "lookup",
        name="Lookup",
        through_field_id=fields["link_row"].id,
        target_field_id=linked_primary.id,
    )
    fields["single_select"] = data_fixture.create_single_select_field(table=table)
    fields["multiple_select"] = data_fixture.create_multiple_select_field(table=table)
    single_options = [
        data_fixture.create_select_option(field=fields["single_select"], value=value)
        for value in ["cherry", "apple", "berry"]
    ]
    multiple_options = {
        value: data_fixture.create_select_option(
            field=fields["multiple_select"], value=value
        )
        for value in ["a", "b", "c"]
    }

    linked_model = linked_table.get_model()
    linked_rows = {
        value: linked_model.objects.create(**{f"field_{linked_primary.id}": value})
        for value in ["a", "b", "c"]
    }
    RowHandler().create_rows(
        user,
        table,
        [
            {
                fields["link_row"].db_column: [linked_rows[link].id],
                fields["single_select"].db_column: single_option.id,
                fields["multiple_select"].db_column: multiple,
            }
            for link, single_option, multiple in zip(
                ["c", "a", "b"],
                single_options,
                [[multiple_options["c"].id], [], [multiple_options["b"].id]],
            )
        ],
    )
    return user, table, fields


def _autonumber_values(table, autonumber_field):
    return list(
        table.get_model()
        .objects.order_by("id")
        .values_list(autonumber_field.db_column, flat=True)
    )


@pytest.mark.field_autonumber
@pytest.mark.django_db
@pytest.mark.parametrize(
    "ordering,field_name,expected",
    [
        ("sort", "link_row", [3, 1, 2]),
        ("sort", "lookup", [3, 1, 2]),
        ("sort", "multiple_select", [3, 1, 2]),
        ("group_by", "link_row", [3, 1, 2]),
    ],
)
def test_renumber_rows_according_to_view_ordered_by_related_field(
    data_fixture, ordering, field_name, expected
):
    user, table, fields = _create_table_with_related_fields(data_fixture)
    view = data_fixture.create_grid_view(table=table)
    if ordering == "sort":
        data_fixture.create_view_sort(view=view, field=fields[field_name], order="ASC")
    else:
        data_fixture.create_view_group_by(
            view=view, field=fields[field_name], order="ASC"
        )

    autonumber_field = FieldHandler().create_field(
        user, table, "autonumber", name="Number", view_id=view.id
    )

    assert _autonumber_values(table, autonumber_field) == expected


@pytest.mark.field_autonumber
@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name,filter_type,value,expected",
    [
        ("single_select", "contains", "rr", [1, 3, 2]),
        ("multiple_select", "contains", "b", [2, 3, 1]),
        ("multiple_select", "empty", "", [2, 1, 3]),
    ],
)
def test_renumber_rows_according_to_view_filtered_by_related_field(
    data_fixture, field_name, filter_type, value, expected
):
    user, table, fields = _create_table_with_related_fields(data_fixture)
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view, field=fields[field_name], type=filter_type, value=value
    )

    autonumber_field = FieldHandler().create_field(
        user, table, "autonumber", name="Number", view_id=view.id
    )

    assert _autonumber_values(table, autonumber_field) == expected


@pytest.mark.field_autonumber
@pytest.mark.django_db
@pytest.mark.parametrize(
    "has_filter,filters_disabled,expects_subquery",
    [(False, False, False), (True, True, False), (True, False, True)],
)
def test_renumber_rows_only_checks_view_filters_when_they_apply(
    data_fixture, has_filter, filters_disabled, expects_subquery
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table, filters_disabled=filters_disabled)
    if has_filter:
        data_fixture.create_view_filter(
            view=view, field=text_field, type="contains", value="a"
        )

    with CaptureQueriesContext(connection) as captured:
        FieldHandler().create_field(
            user, table, "autonumber", name="Number", view_id=view.id
        )

    numbering_sql = next(
        query["sql"] for query in captured if "WITH ordered AS" in query["sql"]
    )
    assert ("EXISTS" in numbering_sql) is expects_subquery


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_convert_to_autonumber_numbers_rows_according_to_view_sorted_by_lookup(
    data_fixture,
):
    user, table, fields = _create_table_with_related_fields(data_fixture)
    text_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_sort(view=view, field=fields["lookup"], order="ASC")

    autonumber_field = FieldHandler().update_field(
        user, text_field, "autonumber", view_id=view.id
    )

    assert _autonumber_values(table, autonumber_field) == [3, 1, 2]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_renumber_rows_gives_trashed_rows_the_highest_numbers(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    model = table.get_model()
    rows = [
        model.objects.create(**{text_field.db_column: value})
        for value in ["rb", "ra", "x", "rc"]
    ]
    model.objects.filter(id=rows[1].id).update(trashed=True)

    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=view, field=text_field, type="contains", value="r"
    )
    data_fixture.create_view_sort(view=view, field=text_field, order="ASC")

    autonumber_field = FieldHandler().create_field(
        user, table, "autonumber", name="Number", view_id=view.id
    )

    values = (
        table.get_model()
        .objects_and_trash.order_by("id")
        .values_list(autonumber_field.db_column, flat=True)
    )
    assert list(values) == [1, 4, 3, 2]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_rejects_view_of_another_table(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    other_table = data_fixture.create_database_table(database=database)
    other_view = data_fixture.create_grid_view(table=other_table)
    text_field = data_fixture.create_text_field(table=table)

    with pytest.raises(ViewDoesNotExist):
        FieldHandler().create_field(
            user, table, "autonumber", name="Number", view_id=other_view.id
        )

    with pytest.raises(ViewDoesNotExist):
        FieldHandler().update_field(
            user, text_field, "autonumber", view_id=other_view.id
        )


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_values_cannot_be_updated_manually(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    row = model.objects.create()

    with pytest.raises(ValidationError):
        RowHandler().update_rows(
            user,
            table,
            [{"id": row.id, f"field_{autonumber_field.id}": 5}],
            model,
            rows_to_update=[row],
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

    # Adding an autonumber field now, also the trashed row should be numbered
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    row_2 = model.objects.create()
    row_2.refresh_from_db()

    assert getattr(row_2, f"field_{autonumber_field.id}") == 2

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

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    # Add a filter and a sort to the view and number rows based on that
    view = data_fixture.create_grid_view(table=table)
    view_filter = data_fixture.create_view_filter(
        view=view, field=autonumber_field, type="equal", value=1
    )

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [row_1.id]

    view_filter.type = "not_equal"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [row_2.id]

    view_filter.type = "lower_than"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == []

    view_filter.type = "higher_than"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [row_2.id]

    view_filter.type = "contains"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [row_1.id]

    view_filter.type = "contains_not"
    view_filter.save(update_fields=["type"])

    qs = ViewHandler().get_queryset(user, view, model=model)
    assert list(qs.values_list("id", flat=True)) == [row_2.id]


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_autonumber_field_view_aggregations(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(table=table)

    model = table.get_model()
    model.objects.create()
    model.objects.create()

    view = data_fixture.create_grid_view(table=table)
    result = ViewHandler().get_field_aggregations(
        user, view, [(autonumber_field, "max")]
    )
    assert result[autonumber_field.db_column] == 2

    model.objects.create()
    model.objects.create()

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

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

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
def test_autonumber_sequence_uses_max_value_not_row_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    autonumber_field = data_fixture.create_autonumber_field(
        table=table, name="autonumber"
    )

    model = table.get_model()

    rows = [model.objects.create() for _ in range(5)]

    for row in rows[:3]:
        row.delete()

    db_column = f"field_{autonumber_field.id}"
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {model._meta.db_table} SET {db_column} = 100 WHERE id = %s",
            [rows[4].id],
        )

    field_type = AutonumberFieldType()
    field_type.create_field_sequence(autonumber_field, model, connection)

    new_row = model.objects.create()
    new_row.refresh_from_db()
    assert getattr(new_row, db_column) == 101
