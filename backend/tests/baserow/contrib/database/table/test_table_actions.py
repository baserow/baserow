import pytest

from baserow.contrib.database.table.actions import (
    CreateTableActionType,
    DeleteTableActionType,
    DuplicateTableActionType,
    OrderTableActionType,
    UpdateTableActionType,
)
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    setup_interesting_test_table,
)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_create_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    table, _ = action_type_registry.get_by_type(CreateTableActionType).do(
        user, database, name="Test 1"
    )

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_undone, [CreateTableActionType])
    assert Table.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_create_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    table, _ = action_type_registry.get_by_type(CreateTableActionType).do(
        user, database, name="Test 1"
    )

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert Table.objects.filter(pk=table.id).count() == 0

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [CreateTableActionType])
    assert Table.objects.filter(pk=table.id).count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_delete_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)

    action_type_registry.get_by_type(DeleteTableActionType).do(user, table)
    assert Table.objects.count() == 0

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_undone, [DeleteTableActionType])
    assert Table.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_delete_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)

    action_type_registry.get_by_type(DeleteTableActionType).do(user, table)

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert Table.objects.filter(pk=table.id).count() == 1

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [DeleteTableActionType])
    assert Table.objects.filter(pk=table.id).count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_order_tables(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table_1 = data_fixture.create_database_table(database=database, user=user, order=1)
    table_2 = data_fixture.create_database_table(database=database, user=user, order=2)
    table_3 = data_fixture.create_database_table(database=database, user=user, order=3)

    def get_tables_order():
        return [t.id for t in database.table_set.order_by("order")]

    original_order = get_tables_order()
    new_order = [table_2.id, table_3.id, table_1.id]

    assert original_order != new_order

    action_type_registry.get_by_type(OrderTableActionType).do(
        user, database, order=new_order
    )
    assert get_tables_order() == new_order

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_undone, [OrderTableActionType])
    assert get_tables_order() == original_order


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_order_tables(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table_1 = data_fixture.create_database_table(database=database, user=user, order=1)
    table_2 = data_fixture.create_database_table(database=database, user=user, order=2)
    table_3 = data_fixture.create_database_table(database=database, user=user, order=3)

    def get_tables_order():
        return [t.id for t in database.table_set.all()]

    original_order = get_tables_order()
    new_order = [table_2.id, table_3.id, table_1.id]

    assert original_order != new_order

    action_type_registry.get_by_type(OrderTableActionType).do(
        user, database, order=new_order
    )
    assert get_tables_order() == new_order

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert get_tables_order() == original_order

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [OrderTableActionType])
    assert get_tables_order() == new_order


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_update_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name, new_table_name = "original-table-name", "new-table-name"
    table = data_fixture.create_database_table(
        database=database, user=user, name=original_table_name
    )

    table = action_type_registry.get_by_type(UpdateTableActionType).do(
        user, table, name=new_table_name
    )
    assert table.name == new_table_name

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_undone, [UpdateTableActionType])
    table.refresh_from_db()
    assert table.name == original_table_name


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name, new_table_name = "original-table-name", "new-table-name"
    table = data_fixture.create_database_table(
        database=database, user=user, name=original_table_name
    )

    table = action_type_registry.get_by_type(UpdateTableActionType).do(
        user, table, name=new_table_name
    )
    assert table.name == new_table_name

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    table.refresh_from_db()
    assert table.name == original_table_name

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateTableActionType])
    table.refresh_from_db()
    assert table.name == new_table_name


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_duplicate_simple_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name = "original-table-name"
    table = data_fixture.create_database_table(
        database=database, user=user, name=original_table_name
    )

    duplicated_table = action_type_registry.get_by_type(DuplicateTableActionType).do(
        user, table
    )
    assert Table.objects.count() == 2
    assert duplicated_table.name == f"{original_table_name} 2"

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert_undo_redo_actions_are_valid(actions_undone, [DuplicateTableActionType])
    assert Table.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_simple_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name = "original-table-name"
    table = data_fixture.create_database_table(
        database=database, user=user, name=original_table_name
    )

    duplicated_table = action_type_registry.get_by_type(DuplicateTableActionType).do(
        user, table
    )
    assert Table.objects.count() == 2
    assert duplicated_table.name == f"{original_table_name} 2"

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert Table.objects.count() == 1

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [DuplicateTableActionType])
    assert Table.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_duplicate_interesting_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name = "original-table-name"
    table, _, _, _, context = setup_interesting_test_table(
        data_fixture, user, database, original_table_name
    )

    duplicated_table = action_type_registry.get_by_type(DuplicateTableActionType).do(
        user, table
    )
    table_handler = TableHandler()
    assert (
        table_handler.get_table(duplicated_table.id).name == f"{original_table_name} 2"
    )

    actions_undone = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert_undo_redo_actions_are_valid(actions_undone, [DuplicateTableActionType])
    with pytest.raises(TableDoesNotExist):
        table_handler.get_table(duplicated_table.id)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_interesting_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)

    original_table_name = "original-table-name"
    table, _, _, _, context = setup_interesting_test_table(
        data_fixture, user, database, original_table_name
    )

    duplicated_table = action_type_registry.get_by_type(DuplicateTableActionType).do(
        user, table
    )
    table_handler = TableHandler()
    assert (
        table_handler.get_table(duplicated_table.id).name == f"{original_table_name} 2"
    )

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(application_id=database.id)], session_id
    )

    assert_undo_redo_actions_are_valid(actions_redone, [DuplicateTableActionType])
    assert (
        table_handler.get_table(duplicated_table.id).name == f"{original_table_name} 2"
    )
