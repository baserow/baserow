from decimal import Decimal
from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.rows.actions import (
    CreateRowActionType,
    CreateRowsActionType,
    DeleteRowActionType,
    DeleteRowsActionType,
    ImportRowsActionType,
    MoveRowActionType,
    UpdateRowActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_creating_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    row = action_type_registry.get_by_type(CreateRowActionType).do(
        user,
        table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )

    assert model.objects.all().count() == 1
    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == 59999.99
    assert not getattr(row, "field_9999", None)

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [CreateRowActionType])

    assert model.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_creating_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    row = action_type_registry.get_by_type(CreateRowActionType).do(
        user,
        table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )

    assert model.objects.all().count() == 1
    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == 59999.99
    assert not getattr(row, "field_9999", None)

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [CreateRowActionType])

    assert model.objects.all().count() == 1

    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == 59999.99
    assert not getattr(row, "field_9999", None)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_creating_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    action_type_registry.get_by_type(CreateRowsActionType).do(
        user,
        table,
        rows_values=[
            {
                f"field_{name_field.id}": "Tesla",
                f"field_{speed_field.id}": 240,
                f"field_{price_field.id}": 59999.99,
            },
            {
                f"field_{name_field.id}": "Giulietta",
                f"field_{speed_field.id}": 210,
                f"field_{price_field.id}": 34999.99,
            },
            {
                f"field_{name_field.id}": "Panda",
                f"field_{speed_field.id}": 160,
                f"field_{price_field.id}": 8999.99,
            },
        ],
    )

    assert model.objects.all().count() == 3

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [CreateRowsActionType])

    assert model.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_creating_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    action_type_registry.get_by_type(CreateRowsActionType).do(
        user,
        table,
        rows_values=[
            {
                f"field_{name_field.id}": "Tesla",
                f"field_{speed_field.id}": 240,
                f"field_{price_field.id}": 59999.99,
            },
            {
                f"field_{name_field.id}": "Giulietta",
                f"field_{speed_field.id}": 210,
                f"field_{price_field.id}": 34999.99,
            },
            {
                f"field_{name_field.id}": "Panda",
                f"field_{speed_field.id}": 160,
                f"field_{price_field.id}": 8999.99,
            },
        ],
    )

    assert model.objects.all().count() == 3

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [CreateRowsActionType])

    assert model.objects.all().count() == 3


@pytest.mark.undo_redo
@pytest.mark.django_db
def test_can_undo_importing_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(name="Car", user=user)
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
    model = table.get_model()

    action_type_registry.get_by_type(ImportRowsActionType).do(
        user,
        table,
        data={
            "data": [
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
            ]
        },
    )

    assert model.objects.all().count() == 3

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [ImportRowsActionType])

    assert model.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
@patch("baserow.contrib.database.table.signals.table_updated.send")
@patch("baserow.contrib.database.rows.signals.rows_created.send")
def test_can_undo_redo_importing_rows(row_send_mock, table_send_mock, data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(name="Car", user=user)
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
    model = table.get_model()

    action_type_registry.get_by_type(ImportRowsActionType).do(
        user,
        table,
        data={
            "data": [
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
            ]
        },
    )

    table_send_mock.assert_called_once()
    table_send_mock.reset_mock()
    row_send_mock.assert_called_once()
    args = row_send_mock.call_args
    assert args[1]["send_realtime_update"] is False
    assert args[1]["send_webhook_events"] is False
    row_send_mock.reset_mock()

    assert model.objects.all().count() == 3

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [ImportRowsActionType])

    assert model.objects.all().count() == 3

    table_send_mock.assert_not_called()
    row_send_mock.assert_called_once()
    assert len(row_send_mock.call_args[1]["rows"]) == 3

    # Test that the signal change when we undo more rows
    action_type_registry.get_by_type(ImportRowsActionType).do(
        user,
        table,
        data={
            "data": [
                [
                    "Tesla",
                    240,
                    59999.99,
                ],
            ]
            * 51
        },
    )

    row_send_mock.reset_mock()
    table_send_mock.reset_mock()

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    table_send_mock.assert_called_once()
    row_send_mock.assert_not_called()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_deleting_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    row = RowHandler().create_row(
        user,
        table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )

    assert model.objects.all().count() == 1

    action_type_registry.get_by_type(DeleteRowActionType).do(user, table, row.id)

    assert model.objects.all().count() == 0

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [DeleteRowActionType])

    assert model.objects.all().count() == 1
    assert getattr(row, f"field_{name_field.id}") == "Tesla"
    assert getattr(row, f"field_{speed_field.id}") == 240
    assert getattr(row, f"field_{price_field.id}") == 59999.99
    assert not getattr(row, "field_9999", None)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_deleting_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    row = RowHandler().create_row(
        user,
        table,
        values={
            name_field.id: "Tesla",
            speed_field.id: 240,
            f"field_{price_field.id}": 59999.99,
            9999: "Must not be added",
        },
    )

    assert model.objects.all().count() == 1

    action_type_registry.get_by_type(DeleteRowActionType).do(user, table, row.id)

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [DeleteRowActionType])

    assert model.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_deleting_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{name_field.id}": "Tesla",
                    f"field_{speed_field.id}": 240,
                    f"field_{price_field.id}": 59999.99,
                },
                {
                    f"field_{name_field.id}": "Giulietta",
                    f"field_{speed_field.id}": 210,
                    f"field_{price_field.id}": 34999.99,
                },
                {
                    f"field_{name_field.id}": "Panda",
                    f"field_{speed_field.id}": 160,
                    f"field_{price_field.id}": 8999.99,
                },
            ],
        )
        .created_rows
    )

    assert model.objects.all().count() == 3

    action_type_registry.get_by_type(DeleteRowsActionType).do(
        user, table, [row.id for row in rows]
    )

    assert model.objects.all().count() == 0

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [DeleteRowsActionType])

    assert model.objects.all().count() == 3


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_deleting_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
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
    model = table.get_model()

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{name_field.id}": "Tesla",
                    f"field_{speed_field.id}": 240,
                    f"field_{price_field.id}": 59999.99,
                },
                {
                    f"field_{name_field.id}": "Giulietta",
                    f"field_{speed_field.id}": 210,
                    f"field_{price_field.id}": 34999.99,
                },
                {
                    f"field_{name_field.id}": "Panda",
                    f"field_{speed_field.id}": 160,
                    f"field_{price_field.id}": 8999.99,
                },
            ],
        )
        .created_rows
    )

    assert model.objects.all().count() == 3

    action_type_registry.get_by_type(DeleteRowsActionType).do(
        user, table, [row.id for row in rows]
    )

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [DeleteRowsActionType])

    assert model.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_moving_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(name="Car", user=user)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)

    def refresh_rows_from_db():
        row_1.refresh_from_db()
        row_2.refresh_from_db()
        row_3.refresh_from_db()

    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    # move row_1 to the end
    action_type_registry.get_by_type(MoveRowActionType).do(user, table, row_1.id)

    refresh_rows_from_db()
    assert row_1.order == Decimal("4.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [MoveRowActionType])

    refresh_rows_from_db()
    assert row_1.order < row_2.order < row_3.order


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_moving_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(name="Car", user=user)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)

    def refresh_rows_from_db():
        row_1.refresh_from_db()
        row_2.refresh_from_db()
        row_3.refresh_from_db()

    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    # move row_1 to the end
    action_type_registry.get_by_type(MoveRowActionType).do(user, table, row_1.id)

    refresh_rows_from_db()
    assert row_1.order == Decimal("4.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [MoveRowActionType])

    refresh_rows_from_db()
    assert row_2.order < row_3.order < row_1.order


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_moving_row_does_nothing_if_row_is_at_same_original_position(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(name="Car", user=user)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)

    def refresh_rows_from_db():
        row_1.refresh_from_db()
        row_2.refresh_from_db()
        row_3.refresh_from_db()

    assert row_1.order == Decimal("1.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    # move row_1 to the end
    action_type_registry.get_by_type(MoveRowActionType).do(
        user, table, row_1.id, before_row=row_2
    )

    refresh_rows_from_db()
    assert row_1.order < row_2.order < row_3.order
    order = [row_1.order, row_2.order, row_3.order]

    undone_actions = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert not undone_actions

    refresh_rows_from_db()
    assert order == [row_1.order, row_2.order, row_3.order]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_updating_row(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table_car = data_fixture.create_database_table(
        name="Car", user=user, database=database
    )
    table_manufacturer = data_fixture.create_database_table(
        name="Manufacturer", user=user, database=database
    )

    # Manufacturer fields
    manufacturer_name_field = data_fixture.create_text_field(
        table=table_car, name="Name", text_default="Test"
    )

    # Car fields
    car_name_field = data_fixture.create_text_field(
        table=table_car, name="Name", text_default="Test"
    )
    speed_field = data_fixture.create_number_field(
        table=table_car, name="Max speed", number_negative=True
    )
    price_field = data_fixture.create_number_field(
        table=table_car,
        name="Price",
        number_decimal_places=2,
        number_negative=False,
    )
    available_field = data_fixture.create_boolean_field(
        table=table_car,
        name="Available",
    )
    fuel_type_option_field = data_fixture.create_single_select_field(
        table=table_car, name="option_field", order=1
    )
    option_gasoline = data_fixture.create_select_option(
        field=fuel_type_option_field, value="gasoline", color="blue"
    )
    option_electric = data_fixture.create_select_option(
        field=fuel_type_option_field, value="electric", color="red"
    )

    year_of_manufacturer = data_fixture.create_date_field(
        table=table_car, name="Year of manufacturer", date_format="ISO"
    )

    manufacturer_link_row_field = FieldHandler().create_field(
        user=user,
        table=table_car,
        type_name="link_row",
        name="manufacturer",
        link_row_table=table_manufacturer,
    )

    alternative_car_link_row_field = FieldHandler().create_field(
        user=user,
        table=table_car,
        type_name="link_row",
        name="alternative_car",
        link_row_table=table_car,
    )

    multiple_select_field = data_fixture.create_multiple_select_field(table=table_car)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 3",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [select_option_1, select_option_2, select_option_3]
    )

    formula_field = data_fixture.create_formula_field(
        table=table_car, formula="'test'", formula_type="text"
    )

    # create a couple of manufacturers

    row_handler = RowHandler()

    tesla_manufacturer = row_handler.create_row(
        user,
        table_manufacturer,
        values={manufacturer_name_field.id: "Tesla"},
    )

    alfa_manufacturer = row_handler.create_row(
        user,
        table_manufacturer,
        values={manufacturer_name_field.id: "Alfa"},
    )

    # create a car with a manufacturer

    original_car_values = {
        car_name_field.id: "Model 3",
        speed_field.id: 240,
        f"field_{price_field.id}": 59999.99,
        f"field_{available_field.id}": True,
        f"field_{fuel_type_option_field.id}": option_electric.id,
        manufacturer_link_row_field.id: [tesla_manufacturer.id],
        year_of_manufacturer.id: "2018-01-01",
        multiple_select_field.id: [select_option_1.id, select_option_2.id],
        9999: "Must not be added",
    }

    car = row_handler.create_row(
        user,
        table_car,
        values=original_car_values,
    )

    model = table_car.get_model()

    car.refresh_from_db()
    assert model.objects.all().count() == 1
    assert getattr(car, f"field_{car_name_field.id}") == "Model 3"
    assert getattr(car, f"field_{speed_field.id}") == 240
    assert getattr(car, f"field_{price_field.id}") == Decimal("59999.99")
    assert getattr(car, f"field_{available_field.id}") is True
    assert (
        getattr(car, f"field_{fuel_type_option_field.id}").value
        == option_electric.value
    )
    car_manufacturer = getattr(
        car, f"field_{manufacturer_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_manufacturer) == [tesla_manufacturer.id]
    assert str(getattr(car, f"field_{year_of_manufacturer.id}")) == "2018-01-01"
    assert not getattr(car, "field_9999", None)
    options = getattr(car, f"field_{multiple_select_field.id}").values_list(
        "id", flat=True
    )
    assert list(options) == unordered([select_option_1.id, select_option_2.id])
    assert getattr(car, f"field_{formula_field.id}") == "test"

    new_values = {
        car_name_field.id: "Alfa Romeo Giulietta",
        speed_field.id: 220,
        f"field_{price_field.id}": 34999.99,
        f"field_{available_field.id}": False,
        f"field_{fuel_type_option_field.id}": option_gasoline.id,
        manufacturer_link_row_field.id: [alfa_manufacturer.id],
        alternative_car_link_row_field.id: [car.id],
        year_of_manufacturer.id: "2015-09-01",
        multiple_select_field.id: [select_option_3.id],
    }

    action_type_registry.get_by_type(UpdateRowActionType).do(
        user, table_car, car.id, values=new_values
    )

    car.refresh_from_db()
    assert model.objects.all().count() == 1
    assert getattr(car, f"field_{car_name_field.id}") == "Alfa Romeo Giulietta"
    assert getattr(car, f"field_{speed_field.id}") == 220
    assert getattr(car, f"field_{price_field.id}") == Decimal("34999.99")
    assert getattr(car, f"field_{available_field.id}") is False
    assert (
        getattr(car, f"field_{fuel_type_option_field.id}").value
        == option_gasoline.value
    )
    car_manufacturer = getattr(
        car, f"field_{manufacturer_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_manufacturer) == [alfa_manufacturer.id]
    car_alternatives = getattr(
        car, f"field_{alternative_car_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_alternatives) == [car.id]
    assert str(getattr(car, f"field_{year_of_manufacturer.id}")) == "2015-09-01"
    options = getattr(car, f"field_{multiple_select_field.id}").values_list(
        "id", flat=True
    )
    assert list(options) == [select_option_3.id]
    assert getattr(car, f"field_{formula_field.id}") == "test"

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table_car.id)], session_id
    )

    car.refresh_from_db()

    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowActionType])

    assert model.objects.all().count() == 1
    assert getattr(car, f"field_{car_name_field.id}") == "Model 3"
    assert getattr(car, f"field_{speed_field.id}") == 240
    assert getattr(car, f"field_{price_field.id}") == Decimal("59999.99")
    assert getattr(car, f"field_{available_field.id}") is True
    assert (
        getattr(car, f"field_{fuel_type_option_field.id}").value
        == option_electric.value
    )
    car_manufacturer = getattr(
        car, f"field_{manufacturer_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_manufacturer) == [tesla_manufacturer.id]
    car_alternatives = getattr(
        car, f"field_{alternative_car_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_alternatives) == []
    assert str(getattr(car, f"field_{year_of_manufacturer.id}")) == "2018-01-01"
    assert not getattr(car, "field_9999", None)
    options = getattr(car, f"field_{multiple_select_field.id}").values_list(
        "id", flat=True
    )
    assert list(options) == unordered([select_option_1.id, select_option_2.id])
    assert getattr(car, f"field_{formula_field.id}") == "test"

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table_car.id)], session_id
    )

    car.refresh_from_db()

    assert_undo_redo_actions_are_valid(action_redone, [UpdateRowActionType])

    assert model.objects.all().count() == 1
    assert getattr(car, f"field_{car_name_field.id}") == "Alfa Romeo Giulietta"
    assert getattr(car, f"field_{speed_field.id}") == 220
    assert getattr(car, f"field_{price_field.id}") == Decimal("34999.99")
    assert getattr(car, f"field_{available_field.id}") is False
    assert (
        getattr(car, f"field_{fuel_type_option_field.id}").value
        == option_gasoline.value
    )
    car_manufacturer = getattr(
        car, f"field_{manufacturer_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_manufacturer) == [alfa_manufacturer.id]
    car_alternatives = getattr(
        car, f"field_{alternative_car_link_row_field.id}"
    ).values_list("id", flat=True)
    assert list(car_alternatives) == [car.id]
    assert str(getattr(car, f"field_{year_of_manufacturer.id}")) == "2015-09-01"
    options = getattr(car, f"field_{multiple_select_field.id}").values_list(
        "id", flat=True
    )
    assert list(options) == [select_option_3.id]
    assert getattr(car, f"field_{formula_field.id}") == "test"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_redo_updating_row_dont_change_formula_field_values(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    formula_field = data_fixture.create_formula_field(
        table=table, name="Formula", formula="1+1"
    )

    row_handler = RowHandler()

    row = row_handler.create_row(user, table, {name_field.id: "Original value"})

    model = table.get_model()

    assert model.objects.count() == 1
    assert getattr(row, f"field_{formula_field.id}") == Decimal("2")

    action_type_registry.get_by_type(UpdateRowActionType).do(
        user, table, row.id, values={name_field.id: "New value"}
    )

    row.refresh_from_db()
    assert getattr(row, f"field_{formula_field.id}") == Decimal("2")

    FieldHandler().update_field(
        user=user,
        table=table,
        field=formula_field,
        formula="2+2",
    )

    row.refresh_from_db()
    assert getattr(row, f"field_{formula_field.id}") == Decimal("4")

    # undo restores the original name value but not the formula field value.
    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    row.refresh_from_db()

    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowActionType])

    assert getattr(row, f"field_{formula_field.id}") == Decimal("4")

    # same for redo
    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    row.refresh_from_db()
    assert_undo_redo_actions_are_valid(action_redone, [UpdateRowActionType])

    assert getattr(row, f"field_{formula_field.id}") == Decimal("4")


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_update_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    row_handler = RowHandler()

    row_one = row_handler.create_row(user, table, {name_field.id: "Original value"})
    row_two = row_handler.create_row(user, table, {name_field.id: "Original value"})

    model = table.get_model()

    assert model.objects.count() == 2

    action_type_registry.get_by_type(UpdateRowsActionType).do(
        user,
        table,
        [
            {"id": row_one.id, f"field_{name_field.id}": "New value"},
            {"id": row_two.id, f"field_{name_field.id}": "New value"},
        ],
    )

    row_one.refresh_from_db()
    row_two.refresh_from_db()

    assert getattr(row_one, f"field_{name_field.id}") == "New value"
    assert getattr(row_two, f"field_{name_field.id}") == "New value"

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowsActionType])

    row_one.refresh_from_db()
    row_two.refresh_from_db()

    assert getattr(row_one, f"field_{name_field.id}") == "Original value"
    assert getattr(row_two, f"field_{name_field.id}") == "Original value"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_rows(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    row_handler = RowHandler()

    row_one = row_handler.create_row(user, table, {name_field.id: "Original value"})
    row_two = row_handler.create_row(user, table, {name_field.id: "Original value"})

    action_type_registry.get_by_type(UpdateRowsActionType).do(
        user,
        table,
        [
            {"id": row_one.id, f"field_{name_field.id}": "New value"},
            {"id": row_two.id, f"field_{name_field.id}": "New value"},
        ],
    )

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [UpdateRowsActionType])

    row_one.refresh_from_db()
    row_two.refresh_from_db()

    assert getattr(row_one, f"field_{name_field.id}") == "New value"
    assert getattr(row_two, f"field_{name_field.id}") == "New value"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_rows_interesting_field_types(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table1 = data_fixture.create_database_table(
        name="Table", user=user, database=database
    )
    table2 = data_fixture.create_database_table(
        name="Table 2", user=user, database=database
    )

    # Fields
    name_field = data_fixture.create_text_field(
        table=table1, name="Name", text_default="Test", primary=True
    )
    file_field = data_fixture.create_file_field(
        table=table1,
        name="File",
    )
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table1,
        type_name="link_row",
        name="Link",
        link_row_table=table2,
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table1)
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="#000000",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=2,
        value="Option 2",
        color="#000000",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    formula_field = data_fixture.create_formula_field(
        table=table1,
        name="formula",
        formula=f"field('{name_field.name}')",
        formula_type="text",
    )

    # Fixtures
    file = data_fixture.create_user_file(
        original_name="file1.txt",
        is_image=False,
    )

    row_handler = RowHandler()

    # Fill the seocond table with data
    row_table_2 = row_handler.create_row(
        user, table2, {name_field.id: "Row one table 2 name field"}
    )
    row_2_table_2 = row_handler.create_row(
        user, table2, {name_field.id: "Row two table 2 name field"}
    )

    row_table_1 = row_handler.create_row(
        user,
        table1,
        {
            name_field.id: "Original value",
            file_field.id: [{"name": file.name, "visible_name": "Original name"}],
            link_row_field.id: [row_table_2.id],
            multiple_select_field.id: [multi_select_option_1.id],
        },
    )

    action_type_registry.get_by_type(UpdateRowsActionType).do(
        user,
        table1,
        [
            {
                "id": row_table_1.id,
                f"field_{name_field.id}": "New value",
                f"field_{file_field.id}": [
                    {"name": file.name, "visible_name": "New name"},
                ],
                f"field_{link_row_field.id}": [row_2_table_2.id],
                f"field_{multiple_select_field.id}": [multi_select_option_2.id],
            },
        ],
    )

    row_table_1.refresh_from_db()

    assert getattr(row_table_1, f"field_{name_field.id}") == "New value"
    assert (
        getattr(row_table_1, f"field_{file_field.id}")[0]["visible_name"] == "New name"
    )
    assert list(
        getattr(row_table_1, f"field_{link_row_field.id}").values_list("id", flat=True)
    ) == [row_2_table_2.id]
    assert list(
        getattr(row_table_1, f"field_{multiple_select_field.id}").values_list(
            "id", flat=True
        )
    ) == [multi_select_option_2.id]
    assert getattr(row_table_1, f"field_{formula_field.id}") == "New value"

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table1.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowsActionType])

    row_table_1.refresh_from_db()

    assert getattr(row_table_1, f"field_{name_field.id}") == "Original value"
    assert (
        getattr(row_table_1, f"field_{file_field.id}")[0]["visible_name"]
        == "Original name"
    )
    assert list(
        getattr(row_table_1, f"field_{link_row_field.id}").values_list("id", flat=True)
    ) == [row_table_2.id]
    assert list(
        getattr(row_table_1, f"field_{multiple_select_field.id}").values_list(
            "id", flat=True
        )
    ) == [multi_select_option_1.id]
    assert getattr(row_table_1, f"field_{formula_field.id}") == "Original value"

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table1.id)], session_id
    )

    assert_undo_redo_actions_are_valid(action_redone, [UpdateRowsActionType])

    row_table_1.refresh_from_db()

    assert getattr(row_table_1, f"field_{name_field.id}") == "New value"
    assert (
        getattr(row_table_1, f"field_{file_field.id}")[0]["visible_name"] == "New name"
    )
    assert list(
        getattr(row_table_1, f"field_{link_row_field.id}").values_list("id", flat=True)
    ) == [row_2_table_2.id]
    assert list(
        getattr(row_table_1, f"field_{multiple_select_field.id}").values_list(
            "id", flat=True
        )
    ) == [multi_select_option_2.id]
    assert getattr(row_table_1, f"field_{formula_field.id}") == "New value"


@pytest.mark.django_db(transaction=True)
def test_import_rows_respects_primary_priority_sorting(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(
        user=user, name="Sample database"
    )
    table = data_fixture.create_database_table(database=database, name="Sample table")

    single_select = data_fixture.create_single_select_field(
        table=table, name="Single select", order=4, primary=False
    )
    data_fixture.create_select_option(
        field=single_select, value="A", color="dark-green", order=0
    )
    data_fixture.create_select_option(
        field=single_select, value="B", color="light-blue", order=1
    )

    name_field = data_fixture.create_text_field(
        table=table, name="Name", order=5, primary=True
    )

    text_field = data_fixture.create_text_field(
        table=table, name="Text", order=8, primary=False
    )

    data_fixture.create_formula_field(
        table=table,
        name="Formula",
        order=58,
        formula="field('Text')",
        formula_type="text",
        internal_formula="field('Text')",
        nullable=True,
        recalculate=True,
    )

    data = [["N", "A", "text"]]

    created_rows, error_report = ImportRowsActionType.do(
        user,
        table,
        data={"data": data, "configuration": None},
        progress=None,
    )

    assert error_report == {}
    assert len(created_rows) == 1

    row = created_rows[0]
    model = table.get_model()
    stored = model.objects.get(id=row.id)

    assert getattr(stored, name_field.db_column) == "N"
    assert getattr(stored, text_field.db_column) == "text"
    assert getattr(stored, single_select.db_column).value == "A"
