from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    Field,
    FormulaField,
    LinkRowField,
    LookupField,
    TextField,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.trash.models import TrashedRows
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import TrashEntry
from baserow.core.trash.exceptions import (
    CannotRestoreChildBeforeParent,
    ParentIdMustBeProvidedException,
    RelatedTableTrashedException,
)
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_delete_row_by_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row = handler.create_row(user=user, table=table)
    handler.create_row(user=user, table=table)

    TrashHandler.permanently_delete(row, table.id)
    assert model.objects.all().count() == 1


@pytest.mark.django_db
@patch("baserow.core.trash.signals.permanently_deleted.send")
def test_perm_deleting_many_rows_at_once_only_looks_up_the_model_once(
    mock, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row_1 = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row_1)
    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 1
    assert TrashEntry.objects.count() == 1

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    invalidate_table_in_model_cache(table.id)
    with django_assert_num_queries(14):
        TrashHandler.permanently_delete_marked_trash()

    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)
    TrashHandler.trash(user, table.database.workspace, table.database, row_2)
    TrashHandler.trash(user, table.database.workspace, table.database, row_3)

    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 2
    assert TrashEntry.objects.count() == 2

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    invalidate_table_in_model_cache(table.id)
    # We only want 8 more queries when deleting 2 rows instead of 1 compared to
    # above:
    # 1. An extra query to open the second trash entries savepoint
    # 2. An extra query to lookup the second trash entry
    # 3. A query to lookup the extra row we are deleting
    # 4. A query to delete said row
    # 5. A query to delete it's trash entry.
    # 6. A query to delete any related row comments.
    # 7. An extra query to close the second trash entries savepoint
    # If we weren't caching the table models an extra number of queries would be first
    # performed to lookup the table information which breaks this assertion.
    with django_assert_num_queries(21):
        TrashHandler.permanently_delete_marked_trash()


@pytest.mark.django_db
def test_can_delete_fields_and_rows_in_the_same_perm_delete_batch(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    handler = RowHandler()
    model = table.get_model()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row_1)
    TrashHandler.trash(user, table.database.workspace, table.database, field)
    TrashHandler.trash(user, table.database.workspace, table.database, row_2)
    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 2
    assert TrashEntry.objects.count() == 3

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 0
    assert TrashEntry.objects.count() == 0

    field_2 = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    row_3 = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, field_2)
    TrashHandler.trash(user, table.database.workspace, table.database, row_3)

    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 1
    assert TrashEntry.objects.count() == 2

    TrashEntry.objects.update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()

    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 0
    assert TrashEntry.objects.count() == 0


@pytest.mark.django_db
def test_can_trash_row_with_blank_primary_single_select(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    data_fixture.create_select_option(field=option_field, value="A", color="blue")
    data_fixture.create_select_option(field=option_field, value="B", color="red")

    handler = RowHandler()
    model = table.get_model()
    row = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row)
    assert TrashEntry.objects.count() == 1
    assert model.objects.count() == 0
    assert model.trash.count() == 1


@pytest.mark.django_db
def test_can_trash_row_with_blank_primary_file_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_file_field(
        table=table, name="file_field", order=1, primary=True
    )

    handler = RowHandler()
    model = table.get_model()
    row = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row)
    assert TrashEntry.objects.count() == 1
    assert model.objects.count() == 0
    assert model.trash.count() == 1


@pytest.mark.django_db
def test_delete_row_by_id_perm(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    row = handler.create_row(user=user, table=table)
    handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row)
    model = table.get_model()
    assert model.objects.all().count() == 1
    assert model.trash.all().count() == 1

    TrashHandler.permanently_delete(row, table.id)
    assert model.objects.all().count() == 1
    assert model.trash.all().count() == 0


@pytest.mark.django_db
def test_cant_delete_row_by_id_perm_without_tableid(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    row = handler.create_row(user=user, table=table)
    handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row)
    with pytest.raises(ParentIdMustBeProvidedException):
        TrashHandler.permanently_delete(row)


@pytest.mark.django_db
def test_perm_delete_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)

    assert Table.objects.all().count() == 1
    assert f"database_table_{table.id}" in connection.introspection.table_names()

    TrashHandler.permanently_delete(table)

    assert Table.objects.all().count() == 0
    assert f"database_table_{table.id}" not in connection.introspection.table_names()


@pytest.mark.django_db
def test_perm_delete_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    assert Field.objects.all().count() == 1
    assert TextField.objects.all().count() == 1
    TrashHandler.permanently_delete(text_field)
    assert Field.objects.all().count() == 0
    assert Field.trash.all().count() == 0
    assert TextField.objects.all().count() == 0

    table_model = table.get_model()
    field_name = f"field_{text_field.id}"
    assert field_name not in [field.name for field in table_model._meta.get_fields()]
    assert f"trashed_{field_name}" not in [
        field.name for field in table_model._meta.get_fields()
    ]


@pytest.mark.django_db
def test_perm_delete_link_row_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    cars_table = data_fixture.create_database_table(name="Cars", database=database)
    data_fixture.create_database_table(name="Unrelated")

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=cars_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )
    TrashHandler.permanently_delete(link_field_1)
    assert LinkRowField.objects.all().count() == 0
    for t in connection.introspection.table_names():
        if "_relation_" in t:
            assert False


@pytest.mark.django_db
def test_trashing_a_table_with_link_fields_pointing_at_it_also_trashes_those_fields(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    cars_table = data_fixture.create_database_table(name="Cars", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=cars_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )
    TrashHandler.trash(user, database.workspace, database, customers_table)

    link_field_1.refresh_from_db()
    assert link_field_1.trashed


@pytest.mark.django_db
def test_trashed_row_entry_includes_the_rows_primary_key_value_as_an_extra_description(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    trash_entry = TrashHandler.trash(user, database.workspace, database, row)

    assert trash_entry.names == ["John"]
    assert trash_entry.name == str(row.id)
    assert trash_entry.parent_name == "Customers"


@pytest.mark.django_db
def test_trashed_rows_entry_includes_includes_the_correct_names(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row1 = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Row A"},
    )
    row2 = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": ""},
    )

    trashed_rows = TrashedRows.objects.create(
        table=customers_table, row_ids=[row1.id, row2.id]
    )
    trash_entry = TrashHandler.trash(user, database.workspace, database, trashed_rows)

    assert trash_entry.names == ["Row A", f"unnamed row {row2.id}"]
    assert trash_entry.name == " "
    assert trash_entry.parent_name == "Customers"


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_trash_and_restore_rows_in_batch(send_mock, data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )

    with patch("baserow.contrib.database.rows.signals.rows_created.send"):
        row1 = row_handler.create_row(
            user=user,
            table=customers_table,
            values={f"field_{customers_primary_field.id}": "Row A"},
        )
        row2 = row_handler.create_row(
            user=user,
            table=customers_table,
            values={f"field_{customers_primary_field.id}": ""},
        )

    trashed_rows = TrashedRows.objects.create(
        table=customers_table, row_ids=[row1.id, row2.id]
    )
    TrashHandler.trash(user, database.workspace, database, trashed_rows)

    customers_model = customers_table.get_model()

    assert customers_model.objects.all().count() == 0
    TrashHandler.restore_item(
        user, "rows", trashed_rows.id, parent_trash_item_id=customers_table.id
    )
    assert customers_model.objects.all().count() == 2

    send_mock.assert_called_once()
    assert [r.id for r in send_mock.call_args[1]["rows"]] == [row1.id, row2.id]
    assert send_mock.call_args[1]["user"] is None
    assert send_mock.call_args[1]["table"].id == customers_table.id
    assert send_mock.call_args[1]["model"]._generated_table_model
    assert send_mock.call_args[1]["before"] is None


@pytest.mark.django_db
def test_permanently_delete_rows_in_batch(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row1 = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Row A"},
    )
    row2 = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": ""},
    )

    trashed_rows = TrashedRows.objects.create(
        table=customers_table, row_ids=[row1.id, row2.id]
    )
    TrashHandler.trash(user, database.workspace, database, trashed_rows)
    TrashHandler.permanently_delete(trashed_rows, parent_id=customers_table.id)

    customers_model = customers_table.get_model()
    assert customers_model.objects_and_trash.all().count() == 0
    assert TrashedRows.objects.all().count() == 0


@pytest.mark.django_db
def test_trashed_row_entry_extra_description_is_unnamed_when_no_value_pk(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={},
    )
    trash_entry = TrashHandler.trash(user, database.workspace, database, row)

    assert trash_entry.names == [f"unnamed row {row.id}"]
    assert trash_entry.name == str(row.id)
    assert trash_entry.parent_name == "Customers"


@pytest.mark.django_db
def test_restoring_a_trashed_link_field_restores_the_opposing_field_also(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )
    FieldHandler().delete_field(user, link_field_1)

    assert LinkRowField.trash.count() == 2

    TrashHandler.restore_item(user, "field", link_field_1.id)

    assert LinkRowField.objects.count() == 2


@pytest.mark.django_db
def test_trashing_a_row_hides_it_from_a_link_row_field_pointing_at_it(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    cars_table = data_fixture.create_database_table(name="Cars", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    john_row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    jane_row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=cars_table,
        type_name="link_row",
        name="customer",
        link_row_table=customers_table,
    )
    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=cars_table, type_name="text", name="Name", primary=True
    )
    linked_row_pointing_at_john = row_handler.create_row(
        user=user,
        table=cars_table,
        values={
            f"field_{cars_primary_field.id}": "BMW",
            f"field_{link_field_1.id}": [john_row.id],
        },
    )
    linked_row_pointing_at_jane = row_handler.create_row(
        user=user,
        table=cars_table,
        values={
            f"field_{cars_primary_field.id}": "Audi",
            f"field_{link_field_1.id}": [jane_row.id],
        },
    )

    cars_model = cars_table.get_model(attribute_names=True)
    assert list(cars_model.objects.values_list("customer", flat=True)) == [
        john_row.id,
        jane_row.id,
    ]
    row = RowHandler().get_row(user, cars_table, linked_row_pointing_at_john.id)
    assert list(
        getattr(row, f"field_{link_field_1.id}").values_list("id", flat=True)
    ) == [john_row.id]

    TrashHandler.trash(user, database.workspace, database, john_row)

    row = RowHandler().get_row(user, cars_table, linked_row_pointing_at_john.id)
    assert list(getattr(row, f"field_{link_field_1.id}").all()) == []
    row = RowHandler().get_row(user, cars_table, linked_row_pointing_at_jane.id)
    assert list(
        getattr(row, f"field_{link_field_1.id}").values_list("id", flat=True)
    ) == [jane_row.id]


@pytest.mark.django_db
def test_a_trashed_linked_row_pointing_at_a_trashed_row_is_restored_correctly(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    cars_table = data_fixture.create_database_table(name="Cars", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    john_row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    jane_row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=cars_table,
        type_name="link_row",
        name="customer",
        link_row_table=customers_table,
    )
    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=cars_table, type_name="text", name="Name", primary=True
    )
    linked_row_pointing_at_john = row_handler.create_row(
        user=user,
        table=cars_table,
        values={
            f"field_{cars_primary_field.id}": "BMW",
            f"field_{link_field_1.id}": [john_row.id],
        },
    )
    row_handler.create_row(
        user=user,
        table=cars_table,
        values={
            f"field_{cars_primary_field.id}": "Audi",
            f"field_{link_field_1.id}": [jane_row.id],
        },
    )

    TrashHandler.trash(
        user,
        database.workspace,
        database,
        linked_row_pointing_at_john,
    )
    TrashHandler.trash(user, database.workspace, database, john_row)
    TrashHandler.restore_item(
        user, "row", linked_row_pointing_at_john.id, parent_trash_item_id=cars_table.id
    )

    row = RowHandler().get_row(user, cars_table, linked_row_pointing_at_john.id)
    assert list(getattr(row, f"field_{link_field_1.id}").all()) == []

    TrashHandler.restore_item(
        user, "row", john_row.id, parent_trash_item_id=customers_table.id
    )

    row = RowHandler().get_row(user, cars_table, linked_row_pointing_at_john.id)
    assert list(
        getattr(row, f"field_{link_field_1.id}").values_list("id", flat=True)
    ) == [john_row.id]


@pytest.mark.django_db
def test_trashing_a_field_with_a_filter_trashes_the_filter(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    other_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Other"
    )
    grid_view = data_fixture.create_grid_view(user=user, table=customers_table)
    data_fixture.create_view_filter(
        view=grid_view, user=user, field=other_field, value="Steve"
    )

    row_handler.create_row(
        user=user,
        table=customers_table,
        values={
            f"field_{customers_primary_field.id}": "John",
            f"field_{other_field.id}": "Test",
        },
    )

    TrashHandler.trash(
        user,
        database.workspace,
        database,
        other_field,
    )

    model = customers_table.get_model()
    filtered_qs = ViewHandler().apply_filters(grid_view, model.objects.all())
    assert filtered_qs.count() == 1
    TrashHandler.restore_item(
        user,
        "field",
        other_field.id,
    )

    model = customers_table.get_model()
    filtered_qs = ViewHandler().apply_filters(grid_view, model.objects.all())
    assert filtered_qs.count() == 0


@pytest.mark.django_db
def test_trashing_a_field_with_a_sort_trashes_the_sort(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    other_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Other"
    )
    grid_view = data_fixture.create_grid_view(user=user, table=customers_table)
    data_fixture.create_view_sort(
        view=grid_view, user=user, field=other_field, order="ASC"
    )

    row_handler.create_row(
        user=user,
        table=customers_table,
        values={
            f"field_{customers_primary_field.id}": "1",
            f"field_{other_field.id}": "2",
        },
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={
            f"field_{customers_primary_field.id}": "2",
            f"field_{other_field.id}": "1",
        },
    )

    TrashHandler.trash(
        user,
        database.workspace,
        database,
        other_field,
    )

    model = customers_table.get_model()
    filtered_qs = ViewHandler().apply_sorting(grid_view, model.objects.all())
    assert list(
        filtered_qs.values_list(f"field_{customers_primary_field.id}", flat=True)
    ) == ["1", "2"]

    TrashHandler.restore_item(
        user,
        "field",
        other_field.id,
    )

    model = customers_table.get_model()
    filtered_qs = ViewHandler().apply_sorting(grid_view, model.objects.all())
    assert list(
        filtered_qs.values_list(f"field_{customers_primary_field.id}", flat=True)
    ) == ["2", "1"]


@pytest.mark.django_db(transaction=True)
def test_can_perm_delete_tables(
    data_fixture,
):
    patcher = patch("baserow.core.models.TrashEntry.delete")
    trash_entry_delete = patcher.start()

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    TrashHandler.trash(user, table.database.workspace, table.database, table)
    assert TrashEntry.objects.count() == 1
    assert f"database_table_{table.id}" in connection.introspection.table_names()

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    trash_entry_delete.side_effect = RuntimeError("Force the outer transaction to fail")
    with pytest.raises(RuntimeError):
        TrashHandler.permanently_delete_marked_trash()

    assert Table.trash.filter(id=table.id).exists()
    assert TrashEntry.objects.count() == 1
    # The transaction rolled back and restored the Table, TrashEntry and underlying
    # table
    assert f"database_table_{table.id}" in connection.introspection.table_names()

    # Now make it so the deletion will work the second time, as long as it handles
    # the actual table no longer being there.
    patcher.stop()

    TrashHandler.permanently_delete_marked_trash()

    assert not Table.trash.filter(id=table.id).exists()
    assert TrashEntry.objects.count() == 0
    assert f"database_table_{table.id}" not in connection.introspection.table_names()


@pytest.mark.django_db
def test_a_restored_field_will_have_its_name_changed_to_ensure_it_is_unique(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(database=database, name="Table")
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_field = field_handler.create_field(
        user=user,
        table=customers_table,
        type_name="text",
        name="Name",
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )
    field_handler.delete_field(user, link_field_1)
    field_handler.delete_field(user, customers_field)

    assert LinkRowField.trash.count() == 2

    clashing_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name"
    )
    another_clashing_field = field_handler.create_field(
        user=user,
        table=customers_table,
        type_name="text",
        name="Name (Restored)",
    )
    link_field_2 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )

    TrashHandler.restore_item(user, "field", link_field_1.id)
    link_field_1.refresh_from_db()

    assert LinkRowField.objects.count() == 4
    assert link_field_2.name == "Customer"
    assert link_field_1.name == "Customer (Restored)"
    assert link_field_2.link_row_related_field.name == "Table"
    assert link_field_1.link_row_related_field.name == "Table (Restored)"

    TrashHandler.restore_item(user, "field", customers_field.id)
    customers_field.refresh_from_db()

    assert TextField.objects.count() == 3
    assert clashing_field.name == "Name"
    assert another_clashing_field.name == "Name (Restored)"
    assert customers_field.name == "Name (Restored) 2"

    # Check that a normal trash and restore when there aren't any naming conflicts will
    # return the old names.
    TrashHandler.trash(user, database.workspace, database, link_field_1)
    TrashHandler.restore_item(user, "field", link_field_1.id)
    link_field_1.refresh_from_db()
    assert link_field_2.name == "Customer"
    assert link_field_1.name == "Customer (Restored)"


@pytest.mark.django_db
def test_perm_delete_related_link_row_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )

    field_handler.delete_field(user, link_field_1.link_row_related_field)
    assert TrashEntry.objects.count() == 1
    link_field_1.refresh_from_db()
    assert link_field_1.trashed
    assert link_field_1.link_row_related_field.trashed

    TrashEntry.objects.update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()

    assert TrashEntry.objects.count() == 0
    assert LinkRowField.objects.all().count() == 0
    for t in connection.introspection.table_names():
        if "_relation_" in t:
            assert False


@pytest.mark.django_db
def test_perm_delete_table_and_related_link_row_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )

    TrashHandler.trash(user, database.workspace, database, table)
    TrashHandler.trash(
        user, database.workspace, database, link_field_1.link_row_related_field
    )

    assert TrashEntry.objects.count() == 2

    TrashEntry.objects.update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()

    assert LinkRowField.objects.all().count() == 0
    for t in connection.introspection.table_names():
        if "_relation_" in t:
            assert False

    assert TrashEntry.objects.count() == 0
    assert LinkRowField.objects_and_trash.all().count() == 0
    assert Table.objects_and_trash.all().count() == 1


@pytest.mark.django_db
def test_can_delete_applications_and_rows_in_the_same_perm_delete_batch(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row_1)
    TrashHandler.trash(user, table.database.workspace, table.database, table.database)
    TrashHandler.trash(user, table.database.workspace, table.database, row_2)
    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 2
    assert TrashEntry.objects.count() == 3
    assert table.get_database_table_name() in connection.introspection.table_names()

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert table.get_database_table_name() not in connection.introspection.table_names()
    assert TrashEntry.objects.count() == 0


@pytest.mark.django_db
def test_can_delete_tables_and_rows_in_the_same_perm_delete_batch(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    data_fixture.create_text_field(table=table, name="Name", text_default="Test")

    handler = RowHandler()
    model = table.get_model()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)
    row_4 = handler.create_row(user=user, table=table)

    TrashHandler.trash(user, table.database.workspace, table.database, row_1)
    TrashHandler.trash(user, table.database.workspace, table.database, table)
    TrashHandler.trash(user, table.database.workspace, table.database, row_2)
    RowHandler().delete_rows(user, table, row_ids=[row_3.id, row_4.id])
    assert model.objects.all().count() == 0
    assert model.trash.all().count() == 4
    assert TrashEntry.objects.count() == 4
    assert table.get_database_table_name() in connection.introspection.table_names()

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert TrashEntry.objects.count() == 0
    assert table.get_database_table_name() not in connection.introspection.table_names()


@pytest.mark.django_db
def test_perm_delete_lookup_row_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database
    )
    cars_table = data_fixture.create_database_table(name="Cars", database=database)
    data_fixture.create_database_table(name="Unrelated")

    field_handler = FieldHandler()
    row_handler = RowHandler()

    # Create a primary field and some example data for the customers table.
    customers_primary_field = field_handler.create_field(
        user=user, table=customers_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=customers_table,
        values={f"field_{customers_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=cars_table, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=cars_table, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Customer",
        link_row_table=customers_table,
    )
    lookup_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="lookup",
        name="Lookup",
        through_field_id=link_field_1.id,
        target_field_id=customers_primary_field.id,
    )
    trashed_at = datetime.now(tz=timezone.utc)
    plus_one_hour_over = timedelta(
        hours=settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED + 1
    )
    with freeze_time(trashed_at):
        url = reverse(
            "api:database:fields:item",
            kwargs={"field_id": link_field_1.link_row_related_field.id},
        )
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        url = reverse("api:database:fields:item", kwargs={"field_id": lookup_field.id})
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
    datetime_when_trash_item_old_enough_to_be_deleted = trashed_at + plus_one_hour_over
    with freeze_time(datetime_when_trash_item_old_enough_to_be_deleted):
        TrashHandler.mark_old_trash_for_permanent_deletion()
    TrashHandler.permanently_delete_marked_trash()

    assert LinkRowField.objects_and_trash.all().count() == 0
    assert LookupField.objects_and_trash.all().count() == 0
    assert FormulaField.objects_and_trash.all().count() == 0


@pytest.mark.django_db
def test_trashing_two_linked_tables_and_restoring_one_ignores_link_field(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table_1 = data_fixture.create_database_table(name="Table 1", database=database)
    table_2 = data_fixture.create_database_table(name="Table 2", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    table_1_primary_field = field_handler.create_field(
        user=user, table=table_1, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=table_2, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table_2,
        type_name="link_row",
        name="Customer",
        link_row_table=table_1,
    )
    TrashHandler.trash(user, database.workspace, database, table_1)
    TrashHandler.trash(user, database.workspace, database, table_2)

    TrashHandler.restore_item(user, "table", table_1.id)

    link_field_1.refresh_from_db()
    assert link_field_1.trashed
    assert link_field_1.link_row_related_field.trashed


@pytest.mark.django_db
def test_trashing_two_linked_tables_and_link_field_cant_restore_link_field(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table_1 = data_fixture.create_database_table(name="Table 1", database=database)
    table_2 = data_fixture.create_database_table(name="Table 2", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    table_1_primary_field = field_handler.create_field(
        user=user, table=table_1, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=table_2, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table_1,
        type_name="link_row",
        name="Customer",
        link_row_table=table_2,
    )
    link_field_trash_entry = TrashHandler.trash(
        user, database.workspace, database, link_field_1
    )
    TrashHandler.trash(user, database.workspace, database, table_1)
    TrashHandler.trash(user, database.workspace, database, table_2)

    with pytest.raises(CannotRestoreChildBeforeParent):
        TrashHandler.restore_item(user, "field", link_field_1.id)

    assert TrashEntry.objects.filter(id=link_field_trash_entry.id).exists()

    TrashHandler.restore_item(user, "table", table_1.id)

    with pytest.raises(RelatedTableTrashedException):
        TrashHandler.restore_item(user, "field", link_field_1.id)

    assert TrashEntry.objects.filter(id=link_field_trash_entry.id).exists()

    TrashHandler.restore_item(user, "table", table_2.id)

    link_field_1.refresh_from_db()
    assert TrashEntry.objects.filter(id=link_field_trash_entry.id).exists()
    assert link_field_1.trashed
    assert link_field_1.link_row_related_field.trashed

    TrashHandler.restore_item(user, "field", link_field_1.id)

    link_field_1.refresh_from_db()
    assert not TrashEntry.objects.filter(id=link_field_trash_entry.id).exists()
    assert not link_field_1.trashed
    assert not link_field_1.link_row_related_field.trashed


@pytest.mark.django_db
def test_trashing_two_linked_tables_after_one_perm_deleted_can_restore(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table_1 = data_fixture.create_database_table(name="Table 1", database=database)
    table_2 = data_fixture.create_database_table(name="Table 2", database=database)

    field_handler = FieldHandler()
    row_handler = RowHandler()

    table_1_primary_field = field_handler.create_field(
        user=user, table=table_1, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "John"},
    )
    row_handler.create_row(
        user=user,
        table=table_1,
        values={f"field_{table_1_primary_field.id}": "Jane"},
    )

    # Create a primary field and some example data for the cars table.
    cars_primary_field = field_handler.create_field(
        user=user, table=table_2, type_name="text", name="Name", primary=True
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "BMW"}
    )
    row_handler.create_row(
        user=user, table=table_2, values={f"field_{cars_primary_field.id}": "Audi"}
    )

    link_field_1 = field_handler.create_field(
        user=user,
        table=table_1,
        type_name="link_row",
        name="Customer",
        link_row_table=table_2,
    )
    link_field_trash_entry = TrashHandler.trash(
        user, database.workspace, database, link_field_1
    )
    TrashHandler.trash(user, database.workspace, database, table_1)
    table_2_trash_entry = TrashHandler.trash(
        user, database.workspace, database, table_2
    )

    table_2_trash_entry.should_be_permanently_deleted = True
    table_2_trash_entry.save()
    TrashHandler.permanently_delete_marked_trash()

    TrashHandler.restore_item(user, "table", table_1.id)

    assert not Field.objects.filter(id=link_field_1.id).exists()
    assert not Field.objects.filter(id=link_field_1.link_row_related_field.id).exists()

    link_field_trash_entry.should_be_permanently_deleted = True
    link_field_trash_entry.save()

    TrashHandler.permanently_delete_marked_trash()

    assert not TrashEntry.objects.exists()


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_trash_restore_view(data_fixture):
    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(name="Table 1", database=database)
    view = data_fixture.create_grid_view(name="View 1", table=table)

    assert view.trashed is False

    TrashHandler.trash(user, database.workspace, database, view)
    view.refresh_from_db()

    assert view.trashed is True

    TrashHandler.restore_item(user, "view", view.id)
    view.refresh_from_db()

    assert view.trashed is False

    # test view ownership

    view2 = data_fixture.create_grid_view(name="View 1", table=table)
    view2.ownership_type = "personal"
    view2.save()

    TrashHandler.trash(user, database.workspace, database, view2)

    with pytest.raises(PermissionDenied):
        TrashHandler.restore_item(user, "view", view2.id)

    with pytest.raises(PermissionDenied):
        TrashHandler.restore_item(user2, "view", view2.id)


@pytest.mark.django_db
def test_can_perm_delete_application_with_linked_tables(data_fixture):
    def test(table_1_order, table_2_order):
        user = data_fixture.create_user()
        database = data_fixture.create_database_application(user=user)
        table_a = data_fixture.create_database_table(
            user=user, database=database, order=table_1_order
        )
        table_b = data_fixture.create_database_table(
            user=user, database=database, order=table_2_order
        )

        FieldHandler().create_field(
            user, table_a, "link_row", link_row_table=table_b, name="link_row"
        )

        TrashHandler.trash(user, database.workspace, database, database)

        TrashEntry.objects.update(should_be_permanently_deleted=True)

        TrashHandler.permanently_delete_marked_trash()

        assert (
            table_a.get_database_table_name()
            not in connection.introspection.table_names()
        )
        assert (
            table_b.get_database_table_name()
            not in connection.introspection.table_names()
        )
        assert TrashEntry.objects.count() == 0

    test(table_1_order=0, table_2_order=1)
    test(table_1_order=1, table_2_order=0)


@pytest.mark.django_db
def test_can_perm_delete_application_which_links_to_self(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a = data_fixture.create_database_table(user=user, database=database)

    FieldHandler().create_field(
        user, table_a, "link_row", link_row_table=table_a, name="link_row"
    )

    TrashHandler.trash(user, database.workspace, database, database)

    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert (
        table_a.get_database_table_name() not in connection.introspection.table_names()
    )
    assert TrashEntry.objects.count() == 0


@pytest.mark.django_db
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_trash_and_restore_rows_in_batch_will_restore_formula_fields(
    send_mock, data_fixture
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name")
    f_name = FieldHandler().create_field(
        user, table, "formula", name="f1", formula="field('Name')"
    )
    f_f_name = FieldHandler().create_field(
        user, table, "formula", name="f2", formula="field('f1')"
    )

    with patch("baserow.contrib.database.rows.signals.rows_created.send"):
        row = RowHandler().create_row(user, table, values={name.db_column: "John"})

    TrashHandler.trash(user, database.workspace, database, row)

    TrashHandler.restore_item(user, "row", row.id, parent_trash_item_id=table.id)

    send_mock.assert_called_once()
    restored_row = send_mock.call_args[1]["rows"][0]
    assert getattr(restored_row, f_name.db_column) == "John"
    assert getattr(restored_row, f_f_name.db_column) == "John"
