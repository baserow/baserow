import os
import random
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.db import connection, transaction
from django.db.models import Sum
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from pyinstrument import Profiler
from pytest_unordered import unordered

from baserow.contrib.database.fields.exceptions import (
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    BooleanField,
    LinkRowField,
    LongTextField,
    TextField,
)
from baserow.contrib.database.management.commands.fill_table_rows import fill_table_rows
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.constants import LAST_MODIFIED_BY_COLUMN_NAME
from baserow.contrib.database.table.exceptions import (
    InitialTableDataLimitExceeded,
    InvalidInitialTableData,
    TableDoesNotExist,
    TableNotInDatabase,
)
from baserow.contrib.database.table.handler import TableHandler, TableUsageHandler
from baserow.contrib.database.table.models import Table, TableUsage, TableUsageUpdate
from baserow.contrib.database.views.models import GridView, GridViewFieldOptions, View
from baserow.core.cache import local_cache
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.models import Template, TrashEntry, Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.core.usage.handler import UsageHandler
from baserow.core.usage.registries import USAGE_UNIT_MB
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
def test_get_database_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_database_table()
    handler = TableHandler()

    with pytest.raises(TableDoesNotExist):
        handler.get_table(table_id=99999)

    # If the error is raised we know for sure that the base query has resolved.
    with pytest.raises(AttributeError):
        handler.get_table(
            table_id=table.id, base_queryset=Table.objects.prefetch_related("UNKNOWN")
        )

    table_copy = handler.get_table(table_id=table.id)
    assert table_copy.id == table.id

    TrashHandler.trash(user, table.database.workspace, table.database, table.database)

    with pytest.raises(TableDoesNotExist):
        handler.get_table(table_id=table.id)

    TrashHandler.restore_item(user, "application", table.database.id)

    TrashHandler.trash(user, table.database.workspace, None, table.database.workspace)
    with pytest.raises(TableDoesNotExist):
        handler.get_table(table_id=table.id)


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_database_minimum_table(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = TableHandler()
    handler.create_table(user=user, database=database, name="Test table")

    assert Table.objects.all().count() == 1
    assert TextField.objects.all().count() == 1

    table = Table.objects.all().first()
    assert table.name == "Test table"
    assert table.order == 1
    assert table.database == database

    primary_field = TextField.objects.all().first()
    assert primary_field.table == table
    assert primary_field.primary
    assert primary_field.name == "Name"

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["user"] == user

    with pytest.raises(UserNotInWorkspace):
        handler.create_table(user=user_2, database=database, name="")

    assert f"database_table_{table.id}" in connection.introspection.table_names()

    model = table.get_model(attribute_names=True)
    row = model.objects.create(name="Test")
    assert row.name == "Test"

    with pytest.raises(TypeError):
        model.objects.create(does_not_exist=True)

    assert model.objects.count() == 1
    row = model.objects.get(id=row.id)
    assert row.name == "Test"


@pytest.mark.django_db
def test_create_example_table(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    table_handler = TableHandler()
    table, _ = table_handler.create_table(
        user, database, name="Table 1", fill_example=True
    )

    assert Table.objects.all().count() == 1
    assert GridView.objects.all().count() == 1
    assert TextField.objects.all().count() == 1
    assert LongTextField.objects.all().count() == 1
    assert BooleanField.objects.all().count() == 1
    assert GridViewFieldOptions.objects.all().count() == 2

    model = table.get_model(attribute_names=True)

    assert model.objects.count() == 2
    assert model.objects.all()[0].last_modified_by == user
    assert model.objects.all()[1].last_modified_by == user


@pytest.mark.django_db(transaction=True)
def test_fill_table_with_initial_data(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    table_handler = TableHandler()

    with pytest.raises(InvalidInitialTableData):
        table_handler.create_table(user, database, name="Table 1", data=[])

    with pytest.raises(InvalidInitialTableData):
        table_handler.create_table(user, database, name="Table 1", data=[[]])

    with override_settings(INITIAL_TABLE_DATA_LIMIT=2), pytest.raises(
        InitialTableDataLimitExceeded
    ):
        table_handler.create_table(user, database, name="Table 1", data=[[], [], []])
    with override_settings(MAX_FIELD_LIMIT=2), pytest.raises(MaxFieldLimitExceeded):
        table_handler.create_table(
            user,
            database,
            name="Table 1",
            data=[["field1", "field2", "field3"], ["rows"] * 3],
        )

    data = [
        ["A", "B", "C", "D"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
        ["2-1", "2-2", "2-3"],
        ["3-1", "3-2"],
    ]
    table, _ = table_handler.create_table(
        user, database, name="Table 1", data=data, first_row_header=True
    )

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "A"
    assert text_fields[1].name == "B"
    assert text_fields[2].name == "C"
    assert text_fields[3].name == "D"
    assert text_fields[4].name == "Field 5"

    assert GridView.objects.all().count() == 1

    model = table.get_model()
    results = model.objects.all()

    assert results.count() == 3

    assert results[0].order == Decimal("1.00000000000000000000")
    assert results[1].order == Decimal("2.00000000000000000000")
    assert results[2].order == Decimal("3.00000000000000000000")

    assert getattr(results[0], f"field_{text_fields[0].id}") == "1-1"
    assert getattr(results[0], f"field_{text_fields[1].id}") == "1-2"
    assert getattr(results[0], f"field_{text_fields[2].id}") == "1-3"
    assert getattr(results[0], f"field_{text_fields[3].id}") == "1-4"
    assert getattr(results[0], f"field_{text_fields[4].id}") == "1-5"

    assert getattr(results[1], f"field_{text_fields[0].id}") == "2-1"
    assert getattr(results[1], f"field_{text_fields[1].id}") == "2-2"
    assert getattr(results[1], f"field_{text_fields[2].id}") == "2-3"
    assert getattr(results[1], f"field_{text_fields[3].id}") is None
    assert getattr(results[1], f"field_{text_fields[4].id}") is None

    assert getattr(results[2], f"field_{text_fields[0].id}") == "3-1"
    assert getattr(results[2], f"field_{text_fields[1].id}") == "3-2"
    assert getattr(results[2], f"field_{text_fields[2].id}") is None
    assert getattr(results[2], f"field_{text_fields[3].id}") is None
    assert getattr(results[2], f"field_{text_fields[4].id}") is None

    data = [
        ["1-1"],
        ["2-1", "2-2", "2-3"],
        ["3-1", "3-2"],
    ]
    table, _ = table_handler.create_table(
        user, database, name="Table 2", data=data, first_row_header=False
    )

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "Field 1"
    assert text_fields[1].name == "Field 2"
    assert text_fields[2].name == "Field 3"

    assert GridView.objects.all().count() == 2

    model = table.get_model()
    results = model.objects.all()

    assert getattr(results[0], f"field_{text_fields[0].id}") == "1-1"
    assert getattr(results[0], f"field_{text_fields[1].id}") is None
    assert getattr(results[0], f"field_{text_fields[2].id}") is None

    assert getattr(results[1], f"field_{text_fields[0].id}") == "2-1"
    assert getattr(results[1], f"field_{text_fields[1].id}") == "2-2"
    assert getattr(results[1], f"field_{text_fields[2].id}") == "2-3"

    assert getattr(results[2], f"field_{text_fields[0].id}") == "3-1"
    assert getattr(results[2], f"field_{text_fields[1].id}") == "3-2"

    data = [
        ["A", "B", "C", "D", "E"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
    ]
    with override_settings(MAX_FIELD_LIMIT=5):
        table, _ = table_handler.create_table(
            user, database, name="Table 3", data=data, first_row_header=True
        )

    assert GridView.objects.all().count() == 3
    assert table.field_set.count() == 5

    too_long_field_name = "x" * 256
    field_name_with_ok_length = "x" * 255

    data = [
        [too_long_field_name, "B", "C", "D", "E"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
    ]
    with pytest.raises(MaxFieldNameLengthExceeded):
        table_handler.create_table(
            user, database, name="Table 3", data=data, first_row_header=True
        )

    data = [
        [field_name_with_ok_length, "B", "C", "D", "E"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
    ]
    table, _ = table_handler.create_table(
        user, database, name="Table 3", data=data, first_row_header=True
    )

    assert table.field_set.count() == 5


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_updated.send")
def test_update_database_table(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    handler = TableHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_table(user=user_2, table=table, name="Test 1")

    handler.update_table(user=user, table=table, name="Test 1")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == table.id
    assert send_mock.call_args[1]["user"].id == user.id

    table.refresh_from_db()

    assert table.name == "Test 1"


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.tables_reordered.send")
def test_order_tables(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_1 = data_fixture.create_database_table(database=database, order=1)
    table_2 = data_fixture.create_database_table(database=database, order=2)
    table_3 = data_fixture.create_database_table(database=database, order=3)

    handler = TableHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.order_tables(user=user_2, database=database, order=[])

    with pytest.raises(TableNotInDatabase):
        handler.order_tables(user=user, database=database, order=[0])

    handler.order_tables(
        user=user, database=database, order=[table_3.id, table_2.id, table_1.id]
    )
    table_1.refresh_from_db()
    table_2.refresh_from_db()
    table_3.refresh_from_db()
    assert table_1.order == 3
    assert table_2.order == 2
    assert table_3.order == 1

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["database"].id == database.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["order"] == [table_3.id, table_2.id, table_1.id]

    handler.order_tables(
        user=user, database=database, order=[table_1.id, table_3.id, table_2.id]
    )
    table_1.refresh_from_db()
    table_2.refresh_from_db()
    table_3.refresh_from_db()
    assert table_1.order == 1
    assert table_2.order == 3
    assert table_3.order == 2

    handler.order_tables(user=user, database=database, order=[table_1.id])
    table_1.refresh_from_db()
    table_2.refresh_from_db()
    table_3.refresh_from_db()
    assert table_1.order == 1
    assert table_2.order == 3
    assert table_3.order == 2


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_deleted.send")
def test_delete_database_table(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    handler = TableHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_table(user=user_2, table=table)

    assert Table.objects.all().count() == 1
    assert Table.trash.all().count() == 0

    table_id = table.id
    handler.delete_table(user=user, table=table)

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table_id"] == table_id
    assert send_mock.call_args[1]["user"].id == user.id

    assert Table.objects.all().count() == 0
    assert Table.trash.all().count() == 1
    assert f"database_table_{table.id}" in connection.introspection.table_names()


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_updated.send")
@patch("baserow.contrib.database.table.signals.table_deleted.send")
def test_deleting_table_trashes_all_fields_and_any_related_links(
    table_deleted_send_mock, field_updated_send_mock, data_fixture
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user)
    target_field = data_fixture.create_text_field(user, table=table_b, name="target")

    dependant_field = FieldHandler().create_field(
        user,
        table_a,
        "lookup",
        through_field_id=link_field.id,
        target_field_id=target_field.id,
        name="lookup",
    )
    other_dependant_field = FieldHandler().create_field(
        user, table_a, "formula", name="formula", formula=f'field("{link_field.name}")'
    )
    assert dependant_field.formula_type == "array"
    assert other_dependant_field.formula_type == "array"

    handler = TableHandler()
    handler.delete_table(user, table_b)

    dependant_field.refresh_from_db()
    other_dependant_field.refresh_from_db()
    assert dependant_field.formula_type == "invalid"
    assert other_dependant_field.formula_type == "invalid"

    table_deleted_send_mock.assert_called_once()
    assert table_deleted_send_mock.call_args[1]["table_id"] == table_b.id
    assert table_deleted_send_mock.call_args[1]["user"].id == user.id

    field_updated_send_mock.assert_called_once()
    updated_field_id = field_updated_send_mock.call_args[1]["field"].id
    related_updated_fields = field_updated_send_mock.call_args[1]["related_fields"]
    assert (
        updated_field_id == other_dependant_field.id
        or updated_field_id == dependant_field.id
    )
    assert field_updated_send_mock.call_args[1]["user"] is None
    assert related_updated_fields == [dependant_field] or related_updated_fields == [
        other_dependant_field
    ]


@pytest.mark.django_db
def test_deleting_a_table_breaks_dependant_fields_and_sends_updates_for_them(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user)

    other_table_b_field = data_fixture.create_long_text_field(
        user, table=table_b, name="other"
    )

    handler = TableHandler()
    handler.delete_table(user, table_b)

    other_table_b_field.refresh_from_db()
    link_field.refresh_from_db()
    assert other_table_b_field.trashed
    assert link_field.trashed
    assert link_field.link_row_related_field.trashed


@pytest.mark.django_db
def test_restoring_a_table_restores_fields_and_related_fields(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user)

    other_table_b_field = data_fixture.create_long_text_field(
        user, table=table_b, name="other"
    )

    handler = TableHandler()
    handler.delete_table(user, table_b)

    TrashHandler.restore_item(user, "table", table_b.id)

    other_table_b_field.refresh_from_db()
    link_field.refresh_from_db()
    assert not other_table_b_field.trashed
    assert not link_field.trashed
    assert not link_field.trashed
    assert not link_field.link_row_related_field.trashed


@pytest.mark.django_db
def test_restoring_table_with_a_previously_trashed_field_leaves_the_field_trashed(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user)

    other_table_b_field = data_fixture.create_long_text_field(
        user, table=table_b, name="other"
    )

    FieldHandler().delete_field(user, other_table_b_field)
    TableHandler().delete_table(user, table_b)

    TrashHandler.restore_item(user, "table", table_b.id)

    other_table_b_field.refresh_from_db()
    link_field.refresh_from_db()
    assert other_table_b_field.trashed
    assert TrashEntry.objects.get(
        trash_item_type="field", trash_item_id=other_table_b_field.id
    )
    assert not link_field.trashed
    assert not link_field.trashed
    assert not link_field.link_row_related_field.trashed


@pytest.mark.django_db
def test_count_rows(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()

    count_expected = random.randint(0, 100)

    for i in range(count_expected):
        model.objects.create(**{f"field_{field.id}": i})

    TableUsageHandler.update_tables_usage()

    table.refresh_from_db()
    assert table.usage.row_count == count_expected


@pytest.mark.django_db
def test_count_rows_ignores_templates(data_fixture, tmpdir):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    # Make sure that some template tables are created
    assert Table.objects.count() == 0
    CoreHandler().sync_templates(storage=storage)
    assert Table.objects.count() > 0

    TableUsageHandler.update_tables_usage()
    assert TableUsage.objects.all().count() == 0

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db(transaction=True)
def test_count_rows_table_gets_deleted(data_fixture):
    table = data_fixture.create_database_table()
    table_deleted = data_fixture.create_database_table(create_table=False)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()

    count_expected = random.randint(0, 100)

    for i in range(count_expected):
        model.objects.create(**{f"field_{field.id}": i})

    TableUsageHandler.update_tables_usage()

    table.refresh_from_db()
    table_deleted.refresh_from_db()
    assert table.usage.row_count == count_expected
    assert table_deleted.usage.row_count is None


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_counting_many_rows_in_many_tables(data_fixture):
    table_amount = 1000
    rows_amount = 2000
    profiler = Profiler()

    # 1000 tables
    for _ in range(table_amount):
        table = data_fixture.create_database_table()
        fill_table_rows(rows_amount, table)

    profiler.start()
    TableUsageHandler.update_tables_usage()
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))
    profiler.reset()
    TableUsage.objects.all().delete()

    # 2000 tables
    for _ in range(table_amount):
        table = data_fixture.create_database_table()
        fill_table_rows(rows_amount, table)

    profiler.start()
    TableUsageHandler.update_tables_usage()
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))
    profiler.reset()
    TableUsage.objects.all().delete()

    # 3000 tables
    for _ in range(table_amount):
        table = data_fixture.create_database_table()
        fill_table_rows(rows_amount, table)

    profiler.start()
    TableUsageHandler.update_tables_usage()
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_interesting_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name = "original-table-name"
    table, _, _, _, context = setup_interesting_test_table(
        data_fixture, user, database, original_table_name
    )

    table_handler = TableHandler()
    duplicated_table = table_handler.duplicate_table(user, table)
    assert (
        table_handler.get_table(duplicated_table.id).name == f"{original_table_name} 2"
    )

    # check link_row fields referencing other tables has been cloned correctly,
    # while self-referencing fields now points to the new duplicated table
    for field_object in duplicated_table.get_model()._field_objects.values():
        field_instance = field_object["field"]
        if not isinstance(field_instance, LinkRowField):
            continue

        if field_instance.name == "self_link_row":
            assert field_instance.link_row_table_id == duplicated_table.id
        else:
            linkrow_fields = field_instance.link_row_table.linkrowfield_set.filter(
                name=field_instance.name
            )
            original_link, duplicated_link = linkrow_fields
            assert original_link.name == duplicated_link.name
            assert original_link.link_row_table_id == duplicated_link.link_row_table_id
            assert bool(original_link.link_row_related_field_id) == bool(
                duplicated_link.link_row_related_field_id
            )
            assert (
                original_link.link_row_table_has_related_field
                == duplicated_link.link_row_table_has_related_field
            )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_table_with_limit_view_link_row_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    related_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    related_view = data_fixture.create_grid_view(table=related_table)

    field_handler = FieldHandler()
    table_1_link_row_field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Link Row 1",
        type_name="link_row",
        link_row_table=related_table,
        link_row_limit_selection_view=related_view,
    )

    table_handler = TableHandler()
    duplicated_table = table_handler.duplicate_table(user, table)

    duplicated_link_row = LinkRowField.objects.get(table=duplicated_table)

    assert duplicated_link_row.id != table_1_link_row_field_1.id
    assert duplicated_link_row.link_row_table_id == related_table.id
    assert duplicated_link_row.link_row_limit_selection_view_id == related_view.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_table_with_limit_view_link_row_field_same_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    table_1_link_row_field_1 = field_handler.create_field(
        user=user,
        table=table,
        name="Link Row 1",
        type_name="link_row",
        link_row_table=table,
        link_row_limit_selection_view=view,
    )

    table_handler = TableHandler()
    duplicated_table = table_handler.duplicate_table(user, table)
    duplicated_link_row = LinkRowField.objects.get(table=duplicated_table)
    duplicated_view = View.objects.get(table=duplicated_table)

    assert duplicated_link_row.id != table_1_link_row_field_1.id
    assert duplicated_link_row.link_row_table_id == duplicated_table.id
    assert duplicated_link_row.link_row_limit_selection_view_id == duplicated_view.id


@pytest.mark.django_db()
def test_duplicate_table_after_link_row_field_moved_to_another_table(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    _, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    table_c = data_fixture.create_database_table(user=user, database=database)

    grid_view = data_fixture.create_grid_view(table=table_b)

    assert grid_view.get_field_options().count() == 2

    FieldHandler().update_field(
        user,
        link_field,
        name=link_field.name,
        new_type_name="link_row",
        link_row_table_id=table_c.id,
        link_row_table=table_c,
        has_related_field=True,
    )

    # the field option should be removed from the grid view
    assert grid_view.get_field_options().count() == 1

    try:
        TableHandler().duplicate_table(user, table_b)
    except Exception as exc:
        pytest.fail("Duplicating table failed: %s" % exc)


@pytest.mark.django_db()
def test_create_last_modified_by_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(
        user,
        last_modified_by_column_added=False,
    )
    model = table.get_model()

    with pytest.raises(FieldDoesNotExist):
        model._meta.get_field(LAST_MODIFIED_BY_COLUMN_NAME)

    TableHandler().create_created_by_and_last_modified_by_fields(table)

    table.refresh_from_db()
    assert table.last_modified_by_column_added

    with local_cache.context():
        model = table.get_model()
        model._meta.get_field(LAST_MODIFIED_BY_COLUMN_NAME)


@pytest.mark.django_db
def test_list_workspace_tables_containing_trashed_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)
    data_fixture.create_database_table(user, database=database, trashed=True)
    workspace_tables = TableHandler().list_workspace_tables(user, workspace=workspace)
    assert list(workspace_tables) == [table]


@pytest.mark.django_db
def test_list_workspace_tables_in_trashed_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, trashed=True
    )
    data_fixture.create_database_table(user, database=database)
    workspace_tables = TableHandler().list_workspace_tables(user, workspace=workspace)
    assert workspace_tables.count() == 0


@pytest.mark.django_db
def test_list_workspace_tables_in_trashed_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, trashed=True)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(user, database=database)
    workspace_tables = TableHandler().list_workspace_tables(user, workspace=workspace)
    assert workspace_tables.count() == 0


@pytest.mark.django_db
def test_table_usage_handler_mark_table_for_usage_update_row_count_default_zero(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)

    TableUsageHandler.mark_table_for_usage_update(table_id=table.id)

    assert TableUsageUpdate.objects.count() == 1
    table_usage = TableUsageUpdate.objects.get(table_id=table.id)
    assert table_usage.row_count == 0


@pytest.mark.django_db(transaction=True)
def test_table_usage_handler_mark_table_for_usage_update_table_doesnt_exist():
    assert (
        TableUsageHandler.mark_table_for_usage_update(table_id=999, row_count=1) is None
    )


@pytest.mark.django_db
def test_table_usage_handler_mark_table_for_usage_update(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)
    table_2 = data_fixture.create_database_table(user, database=database)

    with freeze_time("2020-02-01 01:20"):
        TableUsageHandler.update_tables_usage()

    assert list(
        TableUsage.objects.values("table_id", "row_count", "storage_usage")
    ) == unordered(
        [
            {"table_id": table.id, "row_count": 0, "storage_usage": 0},
            {"table_id": table_2.id, "row_count": 0, "storage_usage": 0},
        ]
    )

    with freeze_time("2020-02-01 01:23"):
        TableUsageHandler.mark_table_for_usage_update(table.id, 10)

    def _get_sum(table_id):
        return (
            TableUsageUpdate.objects.filter(table_id=table_id).aggregate(
                total=Sum("row_count")
            )["total"]
            or 0
        )

    assert TableUsageUpdate.objects.all().count() == 1
    assert _get_sum(table.id) == 10

    # A second update on the same table should update the previous value
    with freeze_time("2020-02-01 01:24"):
        TableUsageHandler.mark_table_for_usage_update(table.id, -3)

    assert TableUsageUpdate.objects.all().count() == 2
    assert _get_sum(table.id) == 7

    # If row_count is 0, then row_count is not changed
    with freeze_time("2020-02-01 01:25"):
        TableUsageHandler.mark_table_for_usage_update(table.id, 0)

    assert TableUsageUpdate.objects.all().count() == 3
    assert _get_sum(table.id) == 7

    # An update to a second table, should create a second entry
    with freeze_time("2020-02-01 01:26"):
        TableUsageHandler.mark_table_for_usage_update(table_2.id, 10)

    assert TableUsageUpdate.objects.all().count() == 4
    assert _get_sum(table_2.id) == 10

    # Let's create 1 row in table and 2 rows in table_2 to verify the row_count is
    # updated correctly
    table.get_model().objects.create()

    table_2.get_model().objects.create()
    table_2.get_model().objects.create()

    # Re-count rows in tables
    with freeze_time("2020-02-01 01:30"):
        TableUsageHandler.update_tables_usage()

    assert TableUsageUpdate.objects.count() == 0
    # no matter what the row_count was in the updates, `update_tables_usage` will
    # re-count rows for all tables
    assert list(
        TableUsage.objects.values("table_id", "row_count", "storage_usage")
    ) == unordered(
        [
            {"table_id": table.id, "row_count": 1, "storage_usage": 0},
            {"table_id": table_2.id, "row_count": 2, "storage_usage": 0},
        ]
    )


@pytest.mark.django_db
def test_table_usage_handler_should_clear_updates_correctly(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)
    table_2 = data_fixture.create_database_table(user, database=database)

    with freeze_time("2020-02-01 01:20"):
        TableUsageHandler.update_tables_usage()

    with freeze_time("2020-02-01 01:21"):
        TableUsageHandler.mark_table_for_usage_update(table.id, 10)
        TableUsageHandler.mark_table_for_usage_update(table_2.id, 20)

    assert TableUsageUpdate.objects.count() == 2

    TableUsageHandler._update_existing_tables_usage(TableUsageUpdate.objects.all())

    assert TableUsageUpdate.objects.count() == 0


@pytest.mark.django_db
def test_table_usage_handler_creates_usage_entries_if_missing(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)
    table_2 = data_fixture.create_database_table(user, database=database)

    assert TableUsage.objects.count() == 0

    TableUsageHandler.update_tables_usage()

    assert TableUsage.objects.count() == 2
    assert list(Table.objects.order_by("id").values_list("id", flat=True)) == [
        table.id,
        table_2.id,
    ]


@pytest.mark.django_db
def test_table_usage_handler_create_updates_for_all_tables_in_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user, database=database)
    table_2 = data_fixture.create_database_table(user, database=database)
    data_fixture.create_database_table(user, database=database, trashed=True)

    TableUsageHandler.create_tables_usage_for_new_database(database.id)

    assert TableUsage.objects.count() == 0
    assert TableUsageUpdate.objects.count() == 2
    assert list(
        TableUsageUpdate.objects.order_by("table_id").values_list("table_id", flat=True)
    ) == [table.id, table_2.id]

    # create the correct entries in the TableUsage table
    TableUsageHandler.update_tables_usage()

    assert TableUsage.objects.count() == 2
    assert list(
        TableUsage.objects.order_by("table_id").values_list("table_id", flat=True)
    ) == [table.id, table_2.id]
    assert TableUsageUpdate.objects.count() == 0


@pytest.mark.django_db
def test_get_database_table_storage_usage(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_file_field(table=table)

    file_1 = data_fixture.create_user_file(size=2 * USAGE_UNIT_MB)
    file_2 = data_fixture.create_user_file(size=3 * USAGE_UNIT_MB)
    file_3 = data_fixture.create_user_file(size=5 * USAGE_UNIT_MB)

    RowHandler().create_rows(
        user,
        table,
        [
            {
                field.db_column: [
                    {"name": file_1.name, "visible_name": "new name"},
                ]
            }
        ],
    )

    assert TableUsageHandler.calculate_table_storage_usage(table.id) == 2

    RowHandler().create_rows(
        user,
        table,
        [
            {
                field.db_column: [
                    {"name": file_1.name, "visible_name": "new name"},
                ]
            }
        ],
    )

    assert TableUsageHandler.calculate_table_storage_usage(table.id) == 2

    RowHandler().create_rows(
        user,
        table,
        [
            {
                field.db_column: [
                    {"name": file_2.name, "visible_name": "new name 2"},
                    {"name": file_3.name, "visible_name": "new name 3"},
                ]
            }
        ],
    )

    assert TableUsageHandler.calculate_table_storage_usage(table.id) == 10


@pytest.mark.django_db
def test_usage_is_calculated_correctly_when_rows_are_deleted(data_fixture):
    database = data_fixture.create_database_application()
    table = data_fixture.create_database_table(database=database)

    TableUsage.objects.create(table_id=table.id, row_count=7)
    TableUsageUpdate.objects.create(table_id=table.id, row_count=3)
    TableUsageUpdate.objects.create(table_id=table.id, row_count=-5)

    subq = UsageHandler.get_workspace_row_count_annotation()
    workspace = (
        Workspace.objects.filter(id=table.database.workspace_id)
        .annotate(row_count=subq)
        .get()
    )

    assert workspace.row_count == 5

    table2 = data_fixture.create_database_table(database=database)
    TableUsage.objects.create(table_id=table2.id, row_count=17)
    TableUsageUpdate.objects.create(table_id=table2.id, row_count=1)
    TableUsageUpdate.objects.create(table_id=table2.id, row_count=-2)
    TableUsageUpdate.objects.create(table_id=table2.id, row_count=-6)

    workspace = (
        Workspace.objects.filter(id=table.database.workspace_id)
        .annotate(row_count=subq)
        .get()
    )

    assert workspace.row_count == 5 + 10

    table3 = data_fixture.create_database_table()
    TableUsage.objects.create(table_id=table3.id, row_count=5)
    TableUsageUpdate.objects.create(table_id=table3.id, row_count=-1)
    TableUsageUpdate.objects.create(table_id=table3.id, row_count=-1)

    assert list(
        Workspace.objects.order_by("id")
        .annotate(row_count=subq)
        .values("id", "row_count")
    ) == [
        {"row_count": 15, "id": database.workspace_id},
        {"row_count": 3, "id": table3.database.workspace_id},
    ]


@pytest.mark.django_db(transaction=True)
def test_usage_is_calculated_correctly_when_a_template_is_installed(
    data_fixture, tmpdir
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = CoreHandler()

    with transaction.atomic():
        handler.sync_templates(storage=storage, pattern="new-hire-onboarding")

    template = Template.objects.get()
    with transaction.atomic():
        CoreHandler().install_template(user, workspace, template, storage=storage)

    row_counts = [
        21,  # Tasks
        91,  # Checklist
        24,  # Employees
        18,  # Titles
        8,  # Departments
        4,  # Office locations
    ]
    assert (
        list(
            TableUsageUpdate.objects.order_by("table_id").values_list(
                "row_count", flat=True
            )
        )
        == row_counts
    )

    subq = UsageHandler.get_workspace_row_count_annotation()
    workspace = Workspace.objects.filter(id=workspace.id).annotate(row_count=subq).get()

    assert workspace.row_count == sum(row_counts)


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.table.tasks.update_table_usage.delay"
)
def test_usage_is_calculated_correctly_when_creating_a_new_table(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    with transaction.atomic():
        table, _ = TableHandler().create_table(
            user, database, name="test", fill_example=True
        )

    workspace = (
        Workspace.objects.filter(id=database.workspace.id)
        .annotate(row_count=UsageHandler.get_workspace_row_count_annotation())
        .get()
    )

    assert workspace.row_count == 2
