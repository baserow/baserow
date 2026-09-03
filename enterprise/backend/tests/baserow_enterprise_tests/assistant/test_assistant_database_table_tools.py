from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import ModelRetry

from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.table.models import Table
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.database.agents import FormulaGenerationResult
from baserow_enterprise.assistant.tools.database.reconciliation import (
    plan_table_creation,
    table_schema_conflict,
)
from baserow_enterprise.assistant.tools.database.tools import (
    create_fields,
    create_tables,
    generate_formula,
    list_tables,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItem,
    FieldItemCreate,
    InvalidFormulaFieldError,
    ListTablesFilterArg,
    SelectOption,
    SelectOptionCreate,
    TableItem,
    TableItemCreate,
)

from .utils import make_test_ctx


def _make_mock_formula_result(**kwargs):
    """Create a mock agent result with a FormulaGenerationResult output."""
    defaults = {
        "table_id": 1,
        "field_name": "test_formula",
        "formula": "'ok'",
        "formula_type": "text",
        "is_formula_valid": True,
        "error_message": "",
    }
    defaults.update(kwargs)
    result = FormulaGenerationResult(**defaults)
    mock_agent_result = MagicMock()
    mock_agent_result.output = result
    return mock_agent_result


def test_plan_table_creation_keeps_the_first_identical_request():
    request = TableItemCreate(name="Orders", primary_field_name="Order", fields=[])

    plan = plan_table_creation([request, request.model_copy(deep=True)], [])

    assert plan.requested == [request]
    assert plan.to_create == [request]
    assert plan.conflicting_names == []


def test_reused_table_detects_field_setting_mismatches():
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(name="Total", type="number", decimal_places=2, suffix="€"),
            FieldItemCreate(
                name="Status",
                type="single_select",
                options=[SelectOptionCreate(value="Pending", color="yellow")],
            ),
        ],
    )
    actual = TableItem(
        id=1,
        name="Orders",
        primary_field=FieldItem(id=2, name="Order", type="text"),
        fields=[
            FieldItem(id=3, name="Total", type="number", decimal_places=0, suffix=""),
            FieldItem(
                id=4,
                name="Status",
                type="single_select",
                options=[SelectOption(id=5, value="Pending", color="blue")],
            ),
        ],
    )

    conflict = table_schema_conflict(requested, actual)

    mismatches = {item["name"]: item for item in conflict["field_mismatches"]}
    assert mismatches["Total"]["decimal_places"] == {
        "actual": 0,
        "requested": 2,
    }
    assert mismatches["Total"]["suffix"] == {
        "actual": "",
        "requested": "€",
    }
    assert mismatches["Status"]["option_color_mismatches"] == [
        {
            "value": "Pending",
            "actual_color": "blue",
            "requested_color": "yellow",
        }
    ]


def test_reused_table_detects_a_non_text_primary_field():
    requested = TableItemCreate(name="Orders", primary_field_name="Order", fields=[])
    actual = TableItem(
        id=1,
        name="Orders",
        primary_field=FieldItem(
            id=2, name="Order", type="number", decimal_places=0, suffix=""
        ),
        fields=[],
    )

    conflict = table_schema_conflict(requested, actual)

    assert conflict["primary_field_mismatch"] == {
        "field_id": 2,
        "actual_type": "number",
        "requested_type": "text",
    }


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

    ctx = make_test_ctx(user, workspace)

    # Test 1: Filter by database_id (single database) - returns flat list
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name=database_1.id,
            table_ids_or_names=None,
        ),
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 2: Filter by database_name (single database) - returns flat list
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name="Database 2",
            table_ids_or_names=None,
        ),
    )
    assert response == [
        {"id": table_3.id, "name": "Table 3", "database_id": database_2.id},
    ]

    # Test 4: Filter by database + table_ids - returns flat list
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name=database_1.id,
            table_ids_or_names=[table_1.id, table_2.id],
        ),
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 5: Filter by database + table_names - returns flat list
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name=database_1.id,
            table_ids_or_names=["Table 1"],
        ),
    )
    assert response == [
        {"id": table_1.id, "name": "Table 1", "database_id": database_1.id},
    ]

    # Test 6: Combined filters (database_id + table_names) - returns flat list
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name=database_1.id,
            table_ids_or_names=["Table 2"],
        ),
    )
    assert response == [
        {"id": table_2.id, "name": "Table 2", "database_id": database_1.id},
    ]

    # Test 7: No matching tables - returns hint with available tables
    response = list_tables(
        ctx,
        thought="test",
        filters=ListTablesFilterArg(
            database_id_or_name=database_1.id,
            table_ids_or_names=["Nonexistent Table"],
        ),
    )
    info = response["_info"]
    assert "no tables matching" in info or "No tables found" in info


@pytest.mark.django_db
def test_create_simple_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )

    ctx = make_test_ctx(user, workspace)

    # Call the tool function directly
    response = create_tables(
        ctx,
        thought="test",
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field_name="Name",
                fields=[],
            )
        ],
        add_sample_rows=False,
    )

    assert len(response["created_tables"]) == 1
    assert response["created_tables"][0]["name"] == "New Table"
    assert response["created_tables"][0]["id"] == AnyInt()
    assert response["notes"] == []
    # Full schema is included so callers have field IDs
    assert "primary_field" in response["created_tables"][0]

    # Ensure the table was actually created
    assert Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).exists()


@pytest.mark.django_db
def test_create_tables_reuses_exact_names_and_skips_side_effects_when_all_reused(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Restaurant"
    )
    existing = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=existing, name="Order", primary=True)
    ctx = make_test_ctx(user, workspace)
    ctx.deps.tool_helpers.navigate_to = MagicMock()
    table_specs = [
        TableItemCreate(name="Orders", primary_field_name="Order", fields=[]),
        TableItemCreate(name="Customers", primary_field_name="Customer", fields=[]),
    ]

    first = create_tables(
        ctx,
        database_id=database.id,
        tables=table_specs,
        add_sample_rows=False,
        thought="finish the database",
    )

    assert [table["name"] for table in first["created_tables"]] == ["Customers"]
    assert first["reused_tables"][0]["id"] == existing.id
    assert first["reused_tables"][0]["name"] == "Orders"
    assert "primary_field" in first["reused_tables"][0]
    assert Table.objects.filter(database=database).count() == 2

    ctx.deps.tool_helpers.navigate_to.reset_mock()
    with patch(
        "baserow_enterprise.assistant.tools.database.tools.generate_sample_rows"
    ) as generate_sample_rows:
        second = create_tables(
            ctx,
            database_id=database.id,
            tables=table_specs,
            add_sample_rows=True,
            thought="continue",
        )

    assert second["created_tables"] == []
    assert [table["name"] for table in second["reused_tables"]] == [
        "Orders",
        "Customers",
    ]
    assert Table.objects.filter(database=database).count() == 2
    generate_sample_rows.assert_not_called()
    ctx.deps.tool_helpers.navigate_to.assert_not_called()
    assert "incomplete_reused_tables" not in second
    assert "next_steps" not in second


@pytest.mark.django_db
def test_create_tables_does_not_reuse_a_table_the_user_cannot_see(
    data_fixture, enable_enterprise, synced_roles
):
    """A same-name table hidden by RBAC must not leak its schema via reuse."""

    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    database = data_fixture.create_database_application(workspace=workspace)
    hidden = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=hidden, name="Secret", primary=True)
    RoleAssignmentHandler().assign_role(
        member, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        member, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )

    result = create_tables(
        make_test_ctx(member, workspace),
        database_id=database.id,
        tables=[TableItemCreate(name="Orders", primary_field_name="Order", fields=[])],
        add_sample_rows=False,
        thought="create Orders",
    )

    assert result["reused_tables"] == []
    assert [table["name"] for table in result["created_tables"]] == ["Orders"]
    assert result["created_tables"][0]["id"] != hidden.id
    assert "Secret" not in str(result)
    assert Table.objects.filter(database=database, name="Orders").count() == 2


@pytest.mark.django_db
def test_reused_table_resolves_an_omitted_relation_target_from_the_database(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Restaurant"
    )
    customers = data_fixture.create_database_table(database=database, name="Customers")
    customer_name = data_fixture.create_text_field(
        table=customers, name="Customer", primary=True
    )
    orders = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=orders, name="Order", primary=True)
    customer_link = data_fixture.create_link_row_field(
        table=orders,
        name="Customer",
        link_row_table=customers,
    )
    data_fixture.create_lookup_field(
        table=orders,
        name="Customer Name",
        through_field=customer_link,
        target_field=customer_name,
        through_field_name=customer_link.name,
        target_field_name=customer_name.name,
    )

    result = create_tables(
        make_test_ctx(user, workspace),
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[
                    FieldItemCreate(
                        name="Customer",
                        type="link_row",
                        linked_table="Customers",
                    ),
                    FieldItemCreate(
                        name="Customer Name",
                        type="lookup",
                        linked_table="Customers",
                        target_field="Customer",
                    ),
                ],
            )
        ],
        add_sample_rows=False,
        thought="verify Orders",
    )

    assert result["created_tables"] == []
    assert [table["name"] for table in result["reused_tables"]] == ["Orders"]
    assert "incomplete_reused_tables" not in result
    assert "next_steps" not in result


@pytest.mark.django_db
def test_create_tables_reports_missing_fields_on_a_reused_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Restaurant"
    )
    orders = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=orders, name="Order", primary=True)
    ctx = make_test_ctx(user, workspace)

    result = create_tables(
        ctx,
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[
                    FieldItemCreate(
                        name="Status",
                        type="single_select",
                        options=[
                            SelectOptionCreate(value="Pending", color="blue"),
                            SelectOptionCreate(value="Processing", color="yellow"),
                        ],
                    )
                ],
            )
        ],
        add_sample_rows=False,
        thought="finish Orders",
    )

    assert result["created_tables"] == []
    assert result["reused_tables"][0]["fields"] == []
    conflict = result["incomplete_reused_tables"][0]
    assert conflict["id"] == orders.id
    assert [field["name"] for field in conflict["missing_fields"]] == ["Status"]
    assert "create_fields" in result["next_steps"]
    assert "Status" in result["next_steps"]

    status = data_fixture.create_single_select_field(table=orders, name="Status")
    data_fixture.create_select_option(field=status, value="Pending", color="blue")
    result = create_tables(
        ctx,
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[
                    FieldItemCreate(
                        name="Status",
                        type="single_select",
                        options=[
                            SelectOptionCreate(value="Pending", color="blue"),
                            SelectOptionCreate(value="Processing", color="yellow"),
                        ],
                    )
                ],
            )
        ],
        add_sample_rows=False,
        thought="verify Orders",
    )

    mismatch = result["incomplete_reused_tables"][0]["field_mismatches"][0]
    assert mismatch["name"] == "Status"
    assert [option["value"] for option in mismatch["missing_options"]] == ["Processing"]
    assert "update_fields" in result["next_steps"]


@pytest.mark.django_db
def test_create_tables_rejects_conflicting_same_name_requests(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)

    with pytest.raises(ModelRetry, match="Conflicting table definitions.*Orders"):
        create_tables(
            ctx,
            database_id=database.id,
            tables=[
                TableItemCreate(name="Orders", primary_field_name="Order", fields=[]),
                TableItemCreate(
                    name="Orders", primary_field_name="Reference", fields=[]
                ),
            ],
            add_sample_rows=False,
            thought="create Orders",
        )

    assert not Table.objects.filter(database=database, name="Orders").exists()


@pytest.mark.django_db
def test_create_complex_table_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Database 1"
    )
    table = data_fixture.create_database_table(database=database, name="Table 1")

    ctx = make_test_ctx(user, workspace)

    primary_field_name = "Name"
    fields = [
        FieldItemCreate(name="Description", type="long_text", rich_text=True),
        FieldItemCreate(name="Amount", type="number", decimal_places=2, suffix="$"),
        FieldItemCreate(name="Due Date", type="date", include_time=False),
        FieldItemCreate(name="Event Time", type="date", include_time=True),
        FieldItemCreate(name="Done?", type="boolean"),
        FieldItemCreate(
            name="Status",
            type="single_select",
            options=[
                SelectOptionCreate(value="New", color="blue"),
                SelectOptionCreate(value="In Progress", color="yellow"),
                SelectOptionCreate(value="Done", color="green"),
            ],
        ),
        FieldItemCreate(
            name="Tags",
            type="multiple_select",
            options=[
                SelectOptionCreate(value="Red", color="red"),
                SelectOptionCreate(value="Yellow", color="yellow"),
                SelectOptionCreate(value="Green", color="green"),
                SelectOptionCreate(value="Blue", color="blue"),
            ],
        ),
        FieldItemCreate(
            name="Related Items",
            type="link_row",
            linked_table=table.id,
        ),
        FieldItemCreate(name="Rating", type="rating", max_value=5),
        FieldItemCreate(name="Attachments", type="file"),
    ]
    # Call the tool function directly
    response = create_tables(
        ctx,
        thought="test",
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="New Table",
                primary_field_name=primary_field_name,
                fields=fields,
            )
        ],
        add_sample_rows=False,
    )

    assert len(response["created_tables"]) == 1
    assert response["created_tables"][0]["name"] == "New Table"
    assert response["created_tables"][0]["id"] == AnyInt()
    assert response["notes"] == []
    # Full schema is included with all field details
    assert "primary_field" in response["created_tables"][0]
    assert "fields" in response["created_tables"][0]

    # Ensure the table was actually created with all fields
    created_table = Table.objects.filter(
        id=response["created_tables"][0]["id"], name="New Table"
    ).first()
    assert created_table is not None
    assert created_table.field_set.count() == 11

    table_model = created_table.get_model()
    fields_map = {field.name: field for field in fields}
    for field_object in table_model.get_field_objects():
        orm_field = field_object["field"]
        read_item = FieldItem.from_django_orm(orm_field).model_dump()

        if orm_field.primary:
            assert orm_field.name == primary_field_name
            continue

        assert orm_field.name in fields_map
        create_item = fields_map.pop(orm_field.name)
        create_dump = create_item.model_dump()

        # Both create and read are flat: type is top-level
        assert create_dump["type"] == read_item["type"]

        # Compare type-specific fields present in both
        skip_keys = {"name", "type"}
        for key, value in create_dump.items():
            if key in skip_keys:
                continue
            read_value = read_item.get(key)
            if read_value is None:
                continue  # read model excludes None; defaults aren't relevant
            if key == "options":
                # Saved options have an ID, so remove them before comparison
                for option in read_value:
                    option.pop("id")
            assert read_value == value, (
                f"Field '{orm_field.name}' key '{key}': "
                f"expected {value}, got {read_value}"
            )


@pytest.mark.django_db
def test_generate_formula_no_save(data_fixture):
    """Test formula generation without saving to a field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="'ok'",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = generate_formula(
            ctx,
            thought="test",
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
def test_generate_formula_create_new_field(data_fixture):
    """Test formula generation creates a new field when none exists."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="'ok'",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = generate_formula(
            ctx,
            thought="test",
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
def test_generate_formula_update_existing_formula_field(data_fixture):
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

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="'new'",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = generate_formula(
            ctx,
            thought="test",
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
def test_generate_formula_replace_non_formula_field(data_fixture):
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

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="'ok'",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = generate_formula(
            ctx,
            thought="test",
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
def test_generate_formula_invalid_formula(data_fixture):
    """Test error handling when formula generation fails."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="",
        formula_type="",
        is_formula_valid=False,
        error_message="Formula syntax error: invalid expression",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)

        # A generation failure is recoverable: it must become a retry prompt.
        with pytest.raises(ModelRetry) as exc_info:
            generate_formula(
                ctx,
                thought="test",
                database_id=database.id,
                description="Invalid formula test",
                save_to_field=True,
            )

        assert "Formula syntax error: invalid expression" in str(exc_info.value)

        # Verify no field was created
        assert not table.field_set.filter(name="test_formula").exists()


@pytest.mark.django_db
def test_generate_formula_documentation_completeness(data_fixture):
    """Test that formula documentation contains all required functions."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test Table")
    data_fixture.create_text_field(table=table, name="text_field", primary=True)

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="test_formula",
        formula="'ok'",
        formula_type="text",
    )

    captured_prompt = None

    def mock_run_sync(prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return mock_result

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync",
        side_effect=mock_run_sync,
    ):
        ctx = make_test_ctx(user, workspace)
        generate_formula(
            ctx,
            thought="test",
            database_id=database.id,
            description="Test documentation",
            save_to_field=False,
        )

    # Verify formula documentation was included in the prompt
    assert captured_prompt is not None
    assert len(captured_prompt) > 0

    # The formula_documentation is now embedded in the prompt string
    captured_formula_docs = captured_prompt

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
        "string_agg_collaborator_values",
        "many_to_many_agg",
        "many_to_many_count",
        "array_length",
        "array_join_values",
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
        assert func in captured_formula_docs, (
            f"Expected function '{func}' not found in documentation"
        )


@pytest.mark.django_db
def test_formula_field_validation_raises_on_invalid_formula(data_fixture):
    """Invalid formula in to_django_orm_kwargs raises InvalidFormulaFieldError."""

    table = data_fixture.create_database_table(name="Test")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    item = FieldItemCreate(
        name="Bad Formula",
        type="formula",
        formula="this is not a valid formula!!!",
    )
    with pytest.raises(InvalidFormulaFieldError) as exc_info:
        item.to_django_orm_kwargs(table)

    assert exc_info.value.field_name == "Bad Formula"
    assert exc_info.value.formula == "this is not a valid formula!!!"
    assert exc_info.value.table == table


@pytest.mark.django_db
def test_formula_field_validation_passes_for_valid_formula(data_fixture):
    """Valid formula in to_django_orm_kwargs returns kwargs without error."""

    table = data_fixture.create_database_table(name="Test")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    item = FieldItemCreate(
        name="Good Formula",
        type="formula",
        formula="field('Name')",
    )
    result = item.to_django_orm_kwargs(table)
    assert result == {"name": "Good Formula", "formula": "field('Name')"}


@pytest.mark.django_db
def test_formula_field_validation_passes_for_empty_formula(data_fixture):
    """Empty formula string skips validation."""

    table = data_fixture.create_database_table(name="Test")

    item = FieldItemCreate(
        name="Empty Formula",
        type="formula",
        formula="",
    )
    result = item.to_django_orm_kwargs(table)
    assert result == {"name": "Empty Formula", "formula": ""}


@pytest.mark.django_db
def test_create_fields_tool_with_invalid_formula_auto_fixes(data_fixture):
    """
    When a formula field has an invalid formula, create_fields
    auto-fixes it via the formula generation pipeline.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="Fixed Formula",
        formula="field('Name')",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = create_fields(
            ctx,
            thought="test",
            table_id=table.id,
            fields=[
                FieldItemCreate(name="Description", type="text"),
                FieldItemCreate(
                    name="Bad Formula",
                    type="formula",
                    formula="invalid_stuff!!!",
                ),
            ],
        )

    # The text field should be created successfully
    assert len(result["created_fields"]) == 2
    # No formula errors since auto-fix succeeded
    assert "formula_errors" not in result

    # Verify the formula field was created with the original name and fixed formula
    formula_field = table.field_set.filter(name="Bad Formula").first()
    assert formula_field is not None


@pytest.mark.django_db
def test_create_fields_tool_reports_error_when_auto_fix_fails(data_fixture):
    """
    When auto-fix also fails, create_fields reports the error
    without failing the entire batch.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    mock_result = _make_mock_formula_result(
        is_formula_valid=False,
        error_message="Could not fix formula",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = create_fields(
            ctx,
            thought="test",
            table_id=table.id,
            fields=[
                FieldItemCreate(name="Description", type="text"),
                FieldItemCreate(
                    name="Bad Formula",
                    type="formula",
                    formula="invalid_stuff!!!",
                ),
            ],
        )

    # The text field should still be created successfully
    assert len(result["created_fields"]) == 1
    assert result["created_fields"][0]["name"] == "Description"

    # Formula errors should be reported
    assert len(result["formula_errors"]) == 1
    assert result["formula_errors"][0]["field_name"] == "Bad Formula"
    assert "hint" in result["formula_errors"][0]


@pytest.mark.django_db
def test_create_fields_reports_the_error_when_the_fixed_field_cannot_be_created(
    data_fixture,
):
    """
    Regression: the fixer returned a formula but creating the field failed on a
    duplicate name; the handler must record the formula error, not raise
    UnboundLocalError from except-as shadowing.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Test")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_text_field(table=table, name="Collides")

    mock_result = _make_mock_formula_result(
        table_id=table.id,
        field_name="Collides",
        formula="field('Name')",
        formula_type="text",
    )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync"
    ) as mock_agent:
        mock_agent.return_value = mock_result

        ctx = make_test_ctx(user, workspace)
        result = create_fields(
            ctx,
            thought="test",
            table_id=table.id,
            fields=[
                FieldItemCreate(
                    name="Collides", type="formula", formula="invalid_stuff!!!"
                )
            ],
        )

    assert result["created_fields"] == []
    assert result["formula_errors"][0]["field_name"] == "Collides"


@pytest.mark.django_db
def test_create_tables_with_invalid_formula_auto_fixes(data_fixture):
    """
    When create_tables encounters an invalid formula, it auto-fixes
    via the formula generation pipeline.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    def mock_run_sync(prompt, **kwargs):
        # The table doesn't exist yet when the mock is created, so we
        # dynamically set table_id on call.
        tables = Table.objects.filter(database=database).order_by("-id")
        return _make_mock_formula_result(
            table_id=tables.first().id,
            field_name="My Formula",
            formula="'fixed'",
            formula_type="text",
        )

    with patch(
        "baserow_enterprise.assistant.tools.database.agents.formula_generation_agent.run_sync",
        side_effect=mock_run_sync,
    ):
        ctx = make_test_ctx(user, workspace)
        result = create_tables(
            ctx,
            thought="test",
            database_id=database.id,
            tables=[
                TableItemCreate(
                    name="Test Table",
                    primary_field_name="Name",
                    fields=[
                        FieldItemCreate(
                            name="My Formula",
                            type="formula",
                            formula="bad formula!!!",
                        ),
                    ],
                )
            ],
            add_sample_rows=False,
        )

    assert len(result["created_tables"]) == 1
    # No formula error notes since auto-fix succeeded
    assert result["notes"] == []
