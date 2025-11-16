from unittest.mock import MagicMock, Mock, patch

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.table.models import Table
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.database.tools import (
    get_generate_database_formula_tool,
    get_list_tables_tool,
    get_table_and_fields_tools_factory,
)
from baserow_enterprise.assistant.tools.database.types import (
    BooleanFieldItemCreate,
    DateFieldItemCreate,
    FileFieldItemCreate,
    LinkRowFieldItemCreate,
    ListTablesFilterArg,
    LongTextFieldItemCreate,
    MultipleSelectFieldItemCreate,
    NumberFieldItemCreate,
    RatingFieldItemCreate,
    SelectOptionCreate,
    SingleSelectFieldItemCreate,
    TableItemCreate,
    TextFieldItemCreate,
    field_item_registry,
)

from .utils import fake_tool_helpers


@pytest.mark.django_db
def test_list_tables_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database_1 = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    database_2 = data_fixture.create_database_application(
        workspace=workspace, name="Database 2"
    )
    table_1 = data_fixture.create_database_table(database=database_1, name="Table 1")
    table_2 = data_fixture.create_database_table(database=database_1, name="Table 2")
    table_3 = data_fixture.create_database_table(database=database_2, name="Table 3")

    tool = get_list_tables_tool(user, workspace, fake_tool_helpers)

    # Test 1: Filter by database_ids (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id],
            database_names=None,
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 2: Filter by database_names (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=["Database 2"],
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
    ]

    # Test 3: Filter by multiple database_ids - returns database wrapper structure
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id, database_2.id],
            database_names=None,
            table_ids=None,
            table_names=None,
        )
    )
    assert response == [
        {
            "id": database_1.id,
            "name": "Database 1",
            "tables": [
                {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
                {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
            ],
        },
        {
            "id": database_2.id,
            "name": "Database 2",
            "tables": [
                {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
            ],
        },
    ]

    # Test 4: Filter by table_ids (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=[table_1.id, table_2.id],
            table_names=None,
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 5: Filter by table_names (single database) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=None,
            table_names=["Table 1"],
        )
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
    ]

    # Test 6: Filter by table_ids across multiple databases - returns database wrapper
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=[table_1.id, table_3.id],
            table_names=None,
        )
    )
    assert response == [
        {
            "id": database_1.id,
            "name": "Database 1",
            "tables": [
                {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
            ],
        },
        {
            "id": database_2.id,
            "name": "Database 2",
            "tables": [
                {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
            ],
        },
    ]

    # Test 7: Combined filters (database_ids + table_names) - returns flat list
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=[database_1.id],
            database_names=None,
            table_ids=None,
            table_names=["Table 2"],
        )
    )
    assert response == [
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 8: No matching tables - returns "No tables found"
    response = tool(
        filters=ListTablesFilterArg(
            database_ids=None,
            database_names=None,
            table_ids=None,
            table_names=["Nonexistent Table"],
        )
    )
    assert response == "No tables found"


@pytest.mark.django_db
def test_create_simple_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )

    factory = get_table_and_fields_tools_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    assert len(added_tools) == 2  # create_tables and create_fields

    # Find the create_tables tool
    create_tables_tool = next(
        (tool for tool in added_tools if tool.name == "create_tables"), None
    )
    assert create_tables_tool is not None

    # Call the underlying function directly (not through udspy.Tool wrapper)
    response = create_tables_tool.func(
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field=TextFieldItemCreate(type="text", name="Name"),
                fields=[],
            )
        ],
        add_sample_rows=False,
    )

    assert response == {
        "created_tables": [{"id": AnyInt(), "name": "New Table"}],
        "notes": [],
    }

    # Ensure the table was actually created
    assert Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).exists()


@pytest.mark.django_db
def test_create_complex_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    table = data_fixture.create_database_table(database=database, name="Table 1")

    factory = get_table_and_fields_tools_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    assert len(added_tools) == 2  # create_tables and create_fields

    # Find the create_tables tool
    create_tables_tool = next(
        (tool for tool in added_tools if tool.name == "create_tables"), None
    )
    assert create_tables_tool is not None

    primary_field = TextFieldItemCreate(type="text", name="Name")
    fields = [
        LongTextFieldItemCreate(
            type="long_text",
            name="Description",
            rich_text=True,
        ),
        NumberFieldItemCreate(
            type="number",
            name="Amount",
            decimal_places=2,
            suffix="$",
        ),
        DateFieldItemCreate(
            type="date",
            name="Due Date",
            include_time=False,
        ),
        DateFieldItemCreate(
            type="date",
            name="Event Time",
            include_time=True,
        ),
        BooleanFieldItemCreate(
            type="boolean",
            name="Done?",
        ),
        SingleSelectFieldItemCreate(
            type="single_select",
            name="Status",
            options=[
                SelectOptionCreate(value="New", color="blue"),
                SelectOptionCreate(value="In Progress", color="yellow"),
                SelectOptionCreate(value="Done", color="green"),
            ],
        ),
        MultipleSelectFieldItemCreate(
            type="multiple_select",
            name="Tags",
            options=[
                SelectOptionCreate(value="Red", color="red"),
                SelectOptionCreate(value="Yellow", color="yellow"),
                SelectOptionCreate(value="Green", color="green"),
                SelectOptionCreate(value="Blue", color="blue"),
            ],
        ),
        LinkRowFieldItemCreate(
            type="link_row",
            name="Related Items",
            linked_table=table.id,
        ),
        RatingFieldItemCreate(
            type="rating",
            name="Rating",
            max_value=5,
        ),
        FileFieldItemCreate(
            type="file",
            name="Attachments",
        ),
    ]
    # Call the underlying function directly (not through udspy.Tool wrapper)
    response = create_tables_tool.func(
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field=primary_field,
                fields=fields,
            )
        ],
        add_sample_rows=False,
    )

    assert response == {
        "created_tables": [{"id": AnyInt(), "name": "New Table"}],
        "notes": [],
    }

    # Ensure the table was actually created with all fields
    created_table = Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).first()
    assert created_table is not None
    assert created_table.field_set.count() == 11

    table_model = created_table.get_model()
    fields_map = {field.name: field for field in fields}
    fields_map[primary_field.name] = primary_field
    for field_object in table_model.get_field_objects():
        orm_field = field_object["field"]
        assert orm_field.name in fields_map
        field_item = fields_map.pop(orm_field.name).model_dump()
        orm_field_to_item = field_item_registry.from_django_orm(orm_field).model_dump()
        if orm_field.primary:
            assert field_item["name"] == primary_field.name

        for key, value in orm_field_to_item.items():
            if key == "id":
                continue
            if key == "options":
                # Saved options have an ID, so we need to remove them before comparison
                for option in value:
                    option.pop("id")

            assert field_item[key] == value


@pytest.mark.django_db
def test_generate_database_formula_no_save(data_fixture):
    """Test formula generation without saving to a field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Mock the udspy.ReAct to return a valid formula
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = True
    mock_prediction.formula = "'ok'"
    mock_prediction.formula_type = "text"
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = ""

    with patch("udspy.ReAct") as mock_react:
        mock_react.return_value.return_value = mock_prediction

        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)
        result = tool(
            database_id=database.id,
            description="Return a simple text",
            save_to_field=False,
        )

        # Verify formula is returned
        assert result["formula"] == "'ok'"
        assert result["formula_type"] == "text"

        # Verify no field was created
        assert not table.field_set.filter(name="test_formula").exists()


@pytest.mark.django_db
def test_generate_database_formula_create_new_field(data_fixture):
    """Test formula generation creates a new field when none exists."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Mock the udspy.ReAct to return a valid formula
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = True
    mock_prediction.formula = "'ok'"
    mock_prediction.formula_type = "text"
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = ""

    with patch("udspy.ReAct") as mock_react:
        mock_react.return_value.return_value = mock_prediction

        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)
        result = tool(
            database_id=database.id,
            description="Return a simple text",
            save_to_field=True,
        )

        # Verify formula is returned
        assert result["formula"] == "'ok'"
        assert result["formula_type"] == "text"
        assert result["table_id"] == table.id
        assert result["table_name"] == "Test Table"
        assert result["field_name"] == "test_formula"
        assert result["operation"] == "field created"

        # Verify field was created
        assert table.field_set.filter(name="test_formula").exists()
        field = table.field_set.get(name="test_formula")
        assert isinstance(field.specific, FormulaField)
        assert field.specific.formula == "'ok'"


@pytest.mark.django_db
def test_generate_database_formula_update_existing_formula_field(data_fixture):
    """Test formula generation updates an existing formula field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Create existing formula field
    existing_field = data_fixture.create_formula_field(
        table=table, name="test_formula", formula="'old'"
    )
    existing_field_id = existing_field.id

    # Mock the udspy.ReAct to return a new formula
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = True
    mock_prediction.formula = "'new'"
    mock_prediction.formula_type = "text"
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = ""

    with patch("udspy.ReAct") as mock_react:
        mock_react.return_value.return_value = mock_prediction

        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)
        result = tool(
            database_id=database.id,
            description="Return updated text",
            save_to_field=True,
        )

        # Verify formula is returned
        assert result["formula"] == "'new'"
        assert result["formula_type"] == "text"
        assert result["table_id"] == table.id
        assert result["table_name"] == "Test Table"
        assert result["field_name"] == "test_formula"
        assert result["operation"] == "field updated"

        # Verify field was updated (same ID, new formula)
        field = table.field_set.get(name="test_formula")
        assert field.id == existing_field_id  # Same field, not recreated
        assert isinstance(field.specific, FormulaField)
        assert field.specific.formula == "'new'"


@pytest.mark.django_db
def test_generate_database_formula_replace_non_formula_field(data_fixture):
    """Test formula generation replaces a non-formula field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Create existing text field with same name
    existing_text_field = data_fixture.create_text_field(
        table=table, name="test_formula"
    )
    existing_field_id = existing_text_field.id

    # Mock the udspy.ReAct to return a valid formula
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = True
    mock_prediction.formula = "'ok'"
    mock_prediction.formula_type = "text"
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = ""

    with patch("udspy.ReAct") as mock_react:
        mock_react.return_value.return_value = mock_prediction

        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)
        result = tool(
            database_id=database.id,
            description="Return a simple text",
            save_to_field=True,
        )

        # Verify formula is returned
        assert result["formula"] == "'ok'"
        assert result["formula_type"] == "text"
        assert result["table_id"] == table.id
        assert result["table_name"] == "Test Table"
        assert result["field_name"] == "test_formula"
        assert result["operation"] == "field created"

        # Verify new formula field was created
        field = table.field_set.get(name="test_formula", trashed=False)
        assert field.id != existing_field_id  # Different field ID (old one trashed)
        assert isinstance(field.specific, FormulaField)
        assert field.specific.formula == "'ok'"

        # Verify old field was trashed
        from baserow.contrib.database.fields.models import Field

        old_field = Field.objects_and_trash.get(id=existing_field_id)
        assert old_field.trashed is True


@pytest.mark.django_db
def test_generate_database_formula_invalid_formula(data_fixture):
    """Test error handling when formula generation fails."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Mock the udspy.ReAct to return an invalid formula
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = False
    mock_prediction.formula = ""
    mock_prediction.formula_type = ""
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = "Formula syntax error: invalid expression"

    with patch("udspy.ReAct") as mock_react:
        mock_react.return_value.return_value = mock_prediction

        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)

        # Verify exception is raised
        with pytest.raises(Exception) as exc_info:
            tool(
                database_id=database.id,
                description="Invalid formula test",
                save_to_field=True,
            )

        assert "Error generating formula:" in str(exc_info.value)
        assert "Formula syntax error: invalid expression" in str(exc_info.value)

        # Verify no field was created
        assert not table.field_set.filter(name="test_formula").exists()


@pytest.mark.django_db
def test_generate_database_formula_documentation_completeness(data_fixture):
    """Test that formula documentation contains all required functions."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    # Mock the udspy.ReAct to capture the formula_documentation argument
    mock_prediction = MagicMock()
    mock_prediction.is_formula_valid = True
    mock_prediction.formula = "'ok'"
    mock_prediction.formula_type = "text"
    mock_prediction.field_name = "test_formula"
    mock_prediction.table_id = table.id
    mock_prediction.error_message = ""

    captured_formula_docs = None

    class MockReAct:
        def __init__(self, signature, tools=None, max_iters=10):
            nonlocal captured_formula_docs
            # Don't capture anything here - wait for the call
            self.mock_instance = MagicMock(return_value=mock_prediction)

        def __call__(self, **kwargs):
            nonlocal captured_formula_docs
            captured_formula_docs = kwargs.get("formula_documentation")
            return mock_prediction

    with patch("udspy.ReAct", MockReAct):
        tool = get_generate_database_formula_tool(user, workspace, fake_tool_helpers)
        tool(
            database_id=database.id,
            description="Test documentation",
            save_to_field=False,
        )

    # Verify formula_documentation was provided
    assert captured_formula_docs is not None
    assert len(captured_formula_docs) > 0

    # Known exceptions (internal functions not documented)
    formula_exceptions = [
        "tovarchar",
        "error_to_nan",
        "bc_to_null",
        "error_to_null",
        "array_agg",
        "array_agg_unnesting",
        "multiple_select_options_agg",
        "get_single_select_value",
        "multiple_select_count",
        "string_agg_multiple_select_values",
        "jsonb_extract_path_text",
        "array_agg_no_nesting",
        "string_agg_many_to_many_values",
        "many_to_many_agg",
        "many_to_many_count",
    ]

    missing_functions = []
    present_functions = []

    # Sanity check: baseline count of registered formula functions (snapshot 2025-10-17)
    assert len(formula_function_registry.registry.keys()) > 110

    for function_name in formula_function_registry.registry.keys():
        if function_name in formula_exceptions:
            continue

        if function_name not in captured_formula_docs:
            missing_functions.append(function_name)
        else:
            present_functions.append(function_name)

    if missing_functions:
        pytest.fail(
            f"The following functions are missing from formula_documentation:\n"
            f"{', '.join(missing_functions)}\n\n"
            f"Present functions: {len(present_functions)}\n"
            f"Missing functions: {len(missing_functions)}"
        )

    # Verify at least some expected functions are present
    expected_common_functions = ["concat", "field", "if", "upper", "lower"]
    for func in expected_common_functions:
        assert (
            func in captured_formula_docs
        ), f"Expected function '{func}' not found in documentation"
