from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.database.rows.handler import RowHandler
from baserow_enterprise.assistant.tools.database.tools import (
    get_list_rows_tool,
    get_rows_tools_factory,
)

from .utils import fake_tool_helpers


def _create_simple_database_with_linked_tables_and_rows(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    workspace = table_a.database.workspace
    primary_field_table_a = table_a.get_primary_field().specific
    primary_field_table_b = table_b.get_primary_field().specific
    text_field = data_fixture.create_text_field(
        user=user, table=table_a, name="Text field"
    )
    long_text_field = data_fixture.create_long_text_field(
        user=user, table=table_a, name="Long text field"
    )
    number_field = data_fixture.create_number_field(
        user=user,
        table=table_a,
        name="Number field",
        number_decimal_places=3,
    )
    date_field = data_fixture.create_date_field(
        user=user, table=table_a, name="Date field"
    )
    datetime_field = data_fixture.create_date_field(
        user=user, table=table_a, name="Datetime field", date_include_time=True
    )
    single_select_field = data_fixture.create_single_select_field(
        user=user, table=table_a, name="Single select"
    )
    data_fixture.create_select_option(value="Option 1", field=single_select_field)
    data_fixture.create_select_option(value="Option 2", field=single_select_field)

    multiple_select_field = data_fixture.create_multiple_select_field(
        user=user, table=table_a, name="Multiple select"
    )
    data_fixture.create_select_option(value="Option A", field=multiple_select_field)
    data_fixture.create_select_option(value="Option B", field=multiple_select_field)
    data_fixture.create_select_option(value="Option C", field=multiple_select_field)
    single_link_to_b_field = data_fixture.create_link_row_field(
        user=user,
        table=table_a,
        link_row_table=table_b,
        name="Single link to B",
        link_row_multiple_relationships=False,
    )

    table_b_rows = (
        RowHandler()
        .force_create_rows(
            user,
            table_b,
            [
                {primary_field_table_b.db_column: "Row B1"},
                {primary_field_table_b.db_column: "Row B2"},
                {primary_field_table_b.db_column: "Row B3"},
            ],
        )
        .created_rows
    )

    table_a_rows = (
        RowHandler()
        .force_create_rows(
            user,
            table_a,
            [
                {
                    primary_field_table_a.db_column: "Row A1",
                    text_field.db_column: "Text A1",
                    long_text_field.db_column: "Long text A1",
                    number_field.db_column: 10.123,
                    date_field.db_column: "2023-01-01",
                    datetime_field.db_column: "2023-01-01 10:00:00",
                    single_select_field.db_column: "Option 1",
                    multiple_select_field.db_column: ["Option A", "Option B"],
                    single_link_to_b_field.db_column: [table_b_rows[0].id],
                    link_a_to_b.db_column: [table_b_rows[0].id, table_b_rows[1].id],
                },
                {
                    primary_field_table_a.db_column: "Row A2",
                    text_field.db_column: "Text A2",
                    long_text_field.db_column: "Long text A2",
                    number_field.db_column: 20.456,
                    date_field.db_column: "2023-02-01",
                    datetime_field.db_column: "2023-02-01 11:00:00",
                    single_select_field.db_column: "Option 2",
                    multiple_select_field.db_column: ["Option B", "Option C"],
                    single_link_to_b_field.db_column: [table_b_rows[1].id],
                    link_a_to_b.db_column: [table_b_rows[1].id, table_b_rows[2].id],
                },
                {},
            ],
        )
        .created_rows
    )

    return {
        "user": user,
        "workspace": workspace,
        "table_a": table_a,
        "table_b": table_b,
        "table_a_fields": {
            "link_a_to_b": link_a_to_b,
            "text_field": text_field,
            "long_text_field": long_text_field,
            "number_field": number_field,
            "date_field": date_field,
            "datetime_field": datetime_field,
            "single_select_field": single_select_field,
            "multiple_select_field": multiple_select_field,
            "single_link_to_b_field": single_link_to_b_field,
        },
        "table_a_rows": table_a_rows,
        "table_b_rows": table_b_rows,
    }


@pytest.mark.django_db
def test_list_rows(data_fixture):
    res = _create_simple_database_with_linked_tables_and_rows(data_fixture)

    user = res["user"]
    workspace = res["workspace"]
    table = res["table_a"]
    tool_helpers = fake_tool_helpers

    list_table_rows = get_list_rows_tool(user, workspace, tool_helpers)
    assert callable(list_table_rows)

    result = list_table_rows(table_id=table.id, offset=0, limit=50)
    rows = result["rows"]
    assert len(rows) == 3
    assert rows[0] == {
        "primary": "Row A1",
        "Long text field": "Long text A1",
        "Number field": 10.123,
        "Date field": {"year": 2023, "month": 1, "day": 1},
        "Datetime field": {"year": 2023, "month": 1, "day": 1, "hour": 10, "minute": 0},
        "Single link to B": "Row B1",
        "Multiple select": ["Option A", "Option B"],
        "Text field": "Text A1",
        "Single select": "Option 1",
        "link": ["Row B1", "Row B2"],
        "id": 1,
    }
    assert rows[1] == {
        "primary": "Row A2",
        "Long text field": "Long text A2",
        "Number field": 20.456,
        "Date field": {"year": 2023, "month": 2, "day": 1},
        "Datetime field": {"year": 2023, "month": 2, "day": 1, "hour": 11, "minute": 0},
        "Single link to B": "Row B2",
        "Multiple select": ["Option B", "Option C"],
        "Text field": "Text A2",
        "Single select": "Option 2",
        "link": ["Row B2", "Row B3"],
        "id": 2,
    }
    assert rows[2] == {
        "primary": "",
        "Long text field": "",
        "Number field": None,
        "Date field": None,
        "Datetime field": None,
        "Single link to B": None,
        "Multiple select": [],
        "Text field": "",
        "Single select": None,
        "link": [],
        "id": 3,
    }

    # List a single field
    result = list_table_rows(
        table_id=table.id, offset=0, limit=50, field_ids=[table.get_primary_field().id]
    )
    rows = result["rows"]
    assert len(rows) == 3
    assert rows[0] == {
        "primary": "Row A1",
        "id": 1,
    }
    assert rows[1] == {
        "primary": "Row A2",
        "id": 2,
    }
    assert rows[2] == {
        "primary": "",
        "id": 3,
    }


@pytest.mark.django_db(transaction=True)
def test_create_rows(data_fixture):
    res = _create_simple_database_with_linked_tables_and_rows(data_fixture)

    user = res["user"]
    workspace = res["workspace"]
    table = res["table_a"]
    tool_helpers = fake_tool_helpers

    meta_tool = get_rows_tools_factory(user, workspace, tool_helpers)
    assert callable(meta_tool)

    tools_upgrade = meta_tool([table.id], ["create"])
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    added_tools_names = [tool.name for tool in added_tools]
    assert len(added_tools) == 1
    assert f"create_rows_in_table_{table.id}" in added_tools_names

    table_model = table.get_model()
    assert table_model.objects.count() == 3

    row_1 = {
        "primary": "Row A3",
        "Text field": "Text A3",
        "Long text field": "Long text A3",
        "Number field": 30.789,
        "Date field": {"year": 2023, "month": 3, "day": 1},
        "Datetime field": {
            "year": 2023,
            "month": 3,
            "day": 1,
            "hour": 12,
            "minute": 0,
        },
        "Single select": "Option 1",
        "Multiple select": ["Option A", "Option C"],
        "Single link to B": "Row B3",
        "link": ["Row B1"],
    }
    row_2 = {
        "primary": "",
        "Text field": "",
        "Long text field": "",
        "Number field": None,
        "Date field": None,
        "Datetime field": None,
        "Single select": None,
        "Multiple select": [],
        "Single link to B": None,
        "link": [],
    }
    create_table_rows = added_tools[0]
    result = create_table_rows(rows=[row_1, row_2])
    created_row_ids = result["created_row_ids"]
    assert len(created_row_ids) == 2
    assert created_row_ids == [4, 5]


@pytest.mark.django_db(transaction=True)
def test_update_rows(data_fixture):
    res = _create_simple_database_with_linked_tables_and_rows(data_fixture)

    user = res["user"]
    workspace = res["workspace"]
    table = res["table_a"]
    tool_helpers = fake_tool_helpers

    meta_tool = get_rows_tools_factory(user, workspace, tool_helpers)
    assert callable(meta_tool)
    tools_upgrade = meta_tool([table.id], ["update"])
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    added_tools_names = [tool.name for tool in added_tools]
    assert len(added_tools) == 1
    assert f"update_rows_in_table_{table.id}" in added_tools_names

    table_model = table.get_model()
    assert table_model.objects.count() == 3

    # Update row 1 with new values
    row_1_updates = {
        "id": 1,
        "primary": "Updated Row A1",
        "Text field": "Updated Text A1",
        "Number field": 99.999,
        "Single select": "Option 2",
        "link": ["Row B3"],
        "Single link to B": "Row B2",
        "Datetime field": "__NO_CHANGE__",
        "Date field": "__NO_CHANGE__",
        "Multiple select": "__NO_CHANGE__",
        "Long text field": "__NO_CHANGE__",
    }
    # Update row 2 with new values
    row_2_updates = {
        "id": 2,
        "Single link to B": "__NO_CHANGE__",
        "Long text field": "Updated Long text A2",
        "Date field": {"year": 2024, "month": 12, "day": 31},
        "Multiple select": ["Option A"],
        "primary": "__NO_CHANGE__",
        "Text field": "__NO_CHANGE__",
        "Number field": "__NO_CHANGE__",
        "Datetime field": "__NO_CHANGE__",
        "Single select": "__NO_CHANGE__",
        "link": "__NO_CHANGE__",
    }

    update_table_rows = added_tools[0]
    result = update_table_rows(rows=[row_1_updates, row_2_updates])
    updated_row_ids = result["updated_row_ids"]
    assert len(updated_row_ids) == 2
    assert updated_row_ids == [1, 2]

    # Verify the rows were updated correctly
    list_table_rows = get_list_rows_tool(user, workspace, tool_helpers)
    row_1, row_2 = list_table_rows(table_id=table.id, offset=0, limit=2)["rows"]
    assert row_1 == {
        "primary": "Updated Row A1",
        "Long text field": "Long text A1",
        "Number field": 99.999,
        "Date field": {"year": 2023, "month": 1, "day": 1},
        "Datetime field": {"year": 2023, "month": 1, "day": 1, "hour": 10, "minute": 0},
        "Single link to B": "Row B2",
        "Multiple select": ["Option A", "Option B"],
        "Text field": "Updated Text A1",
        "Single select": "Option 2",
        "link": ["Row B3"],
        "id": 1,
    }
    assert row_2 == {
        "primary": "Row A2",
        "Long text field": "Updated Long text A2",
        "Number field": 20.456,
        "Date field": {"year": 2024, "month": 12, "day": 31},
        "Datetime field": {"year": 2023, "month": 2, "day": 1, "hour": 11, "minute": 0},
        "Single link to B": "Row B2",
        "Multiple select": ["Option A"],
        "Text field": "Text A2",
        "Single select": "Option 2",
        "link": ["Row B2", "Row B3"],
        "id": 2,
    }


@pytest.mark.django_db(transaction=True)
def test_delete_rows(data_fixture):
    res = _create_simple_database_with_linked_tables_and_rows(data_fixture)

    user = res["user"]
    workspace = res["workspace"]
    table = res["table_a"]
    tool_helpers = fake_tool_helpers

    meta_tool = get_rows_tools_factory(user, workspace, tool_helpers)
    assert callable(meta_tool)

    tools_upgrade = meta_tool([table.id], ["delete"])
    assert is_module_callback(tools_upgrade)
    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called
    added_tools = mock_module.init_module.call_args[1]["tools"]
    added_tools_names = [tool.name for tool in added_tools]
    assert len(added_tools) == 1
    assert f"delete_rows_in_table_{table.id}" in added_tools_names
    delete_table_rows = added_tools[0]

    table_model = table.get_model()
    assert table_model.objects.count() == 3

    # Delete rows with ids 1 and 3
    result = delete_table_rows(row_ids=[1, 3])
    assert result["deleted_row_ids"] == [1, 3]

    # Verify rows were deleted
    assert table_model.objects.count() == 1
    assert list(table_model.objects.values_list("id", flat=True)) == [2]
