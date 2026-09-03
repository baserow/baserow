"""
Deterministic tool-CHAIN suite for the Kuma assistant's database tools.

The sibling suites call one tool at a time. These tests drive the tools in the
order a real turn does — the id a tool RETURNS is the id the next tool is CALLED
with — so they fail when a tool starts returning a shape the next tool can no
longer consume. That is the regression class that hurts in production: a
refactor removed ``Element.order`` and ``list_elements`` failed in 94% of the
traces that called it for 36 days, and reloading row tools for an
already-loaded table used to raise a tool-name conflict.

No LLM and no network: ``add_sample_rows`` is always False, and tools needing a
live model (``generate_formula``, ``search_user_docs``) are out of scope.
"""

from typing import Any

import pytest
from pydantic_ai import Tool

from baserow.contrib.database.fields.models import Field as BaserowField
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View, ViewFilter
from baserow_enterprise.assistant.agents import dynamic_toolset
from baserow_enterprise.assistant.tools.core.tools import create_builders
from baserow_enterprise.assistant.tools.core.types import BuilderItemCreate
from baserow_enterprise.assistant.tools.database.tools import (
    create_fields,
    create_tables,
    create_view_filters,
    create_views,
    get_tables_schema,
    list_tables,
    list_views,
    load_row_tools,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemCreate,
    ListTablesFilterArg,
    SelectOptionCreate,
    TableItemCreate,
    ViewFilterItemCreate,
    ViewFiltersArgs,
    ViewItemCreate,
)

from .utils import make_test_ctx

# ===========================================================================
# Chain helpers — a failure below means a tool contract changed
# ===========================================================================

CONTRACT_CHANGED = (
    "A tool contract, model or data type changed: the tools on both sides of "
    "this handoff must be updated together."
)


def schema_field(table_schema: dict[str, Any], name: str) -> dict[str, Any]:
    """Find a field by name in a table schema, primary field included."""

    fields = [table_schema["primary_field"], *table_schema["fields"]]
    match = next((f for f in fields if f["name"] == name), None)
    assert match is not None, (
        f"field {name!r} is missing from the returned schema "
        f"(has: {[f['name'] for f in fields]}). {CONTRACT_CHANGED}"
    )
    return match


def schema_field_names(table_schema: dict[str, Any]) -> set[str]:
    """Every field name in a table schema, primary field included."""

    return {
        field["name"]
        for field in [table_schema["primary_field"], *table_schema["fields"]]
    }


def row_tool_field_names(tool: Tool) -> set[str]:
    """Field names a dynamic row tool accepts, read from its own JSON schema."""

    schema = tool.function_schema.json_schema
    return set(schema["properties"]["rows"]["items"]["properties"])


def call_row_tool(tool: Tool, **kwargs: Any) -> Any:
    """Validate arguments against the generated schema, then run the tool."""

    validated = tool.function_schema.validator.validate_python(kwargs)
    return tool.function(**validated)


# ===========================================================================
# CHAIN 1 — build a database from nothing (the onboarding path)
# ===========================================================================


def onboarding_tables() -> list[TableItemCreate]:
    """Two related tables, as the agent sends them in one create_tables call."""

    return [
        TableItemCreate(
            name="Customers",
            primary_field_name="Name",
            fields=[FieldItemCreate(name="City", type="text")],
        ),
        TableItemCreate(
            name="Orders",
            primary_field_name="Order",
            fields=[
                FieldItemCreate(name="Amount", type="number", decimal_places=2),
                FieldItemCreate(name="Due", type="date"),
                FieldItemCreate(
                    name="Status",
                    type="single_select",
                    options=[
                        SelectOptionCreate(value="Open", color="green"),
                        SelectOptionCreate(value="Closed", color="red"),
                    ],
                ),
                FieldItemCreate(
                    name="Customer", type="link_row", linked_table="Customers"
                ),
            ],
        ),
    ]


@pytest.mark.django_db
def test_chain_build_a_database_from_nothing(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    # --- create_builders -> database id -----------------------------------
    builders = create_builders(
        ctx,
        builders=[BuilderItemCreate(name="Sales", type="database")],
        thought="chain",
    )["created_builders"]
    assert len(builders) == 1
    database_id = builders[0]["id"]

    # --- database id -> create_tables -------------------------------------
    result = create_tables(
        ctx,
        database_id=database_id,
        tables=onboarding_tables(),
        add_sample_rows=False,
        thought="chain",
    )
    assert result["notes"] == [], (
        f"create_tables reported errors while building the chain's tables: "
        f"{result['notes']}"
    )
    created = result["created_tables"]
    assert len(created) == 2
    customers_id = created[0]["id"]
    orders_id = created[1]["id"]

    # --- table ids -> get_tables_schema -> field ids ----------------------
    schemas = get_tables_schema(
        ctx,
        table_ids=[customers_id, orders_id],
        full_schema=True,
        thought="chain",
    )["tables_schema"]
    assert [s["id"] for s in schemas] == [customers_id, orders_id]
    orders_schema = schemas[1]

    # Disagreement here means the agent silently works from stale field ids.
    assert schema_field_names(orders_schema) == schema_field_names(created[1]), (
        "create_tables and get_tables_schema disagree about the fields of the "
        f"same table: {sorted(schema_field_names(created[1]))} vs "
        f"{sorted(schema_field_names(orders_schema))}. {CONTRACT_CHANGED}"
    )

    link = schema_field(orders_schema, "Customer")
    assert link["linked_table"] == customers_id

    status = schema_field(orders_schema, "Status")
    status_id = status["id"]
    amount_id = schema_field(orders_schema, "Amount")["id"]
    options = status["options"]
    open_option = next((o for o in options if o["value"] == "Open"), None)
    assert open_option is not None, (
        f"the single_select schema no longer carries its options (got "
        f"{options!r}), so a filter cannot be built from it. {CONTRACT_CHANGED}"
    )

    # --- table id -> create_fields -> new field ids -----------------------
    result = create_fields(
        ctx,
        table_id=orders_id,
        fields=[
            FieldItemCreate(name="Cover", type="file"),
            FieldItemCreate(name="Priority", type="rating", max_value=5),
        ],
        thought="chain",
    )
    assert "field_errors" not in result and "formula_errors" not in result, (
        f"create_fields could not add fields to the table create_tables built: {result}"
    )
    cover_id = next(f for f in result["created_fields"] if f["name"] == "Cover")["id"]

    # --- field ids -> create_views ----------------------------------------
    views = create_views(
        ctx,
        table_id=orders_id,
        views=[
            ViewItemCreate(name="All orders", public=False, type="grid"),
            ViewItemCreate(
                name="Board", public=False, type="kanban", column_field_id=status_id
            ),
            ViewItemCreate(
                name="Covers", public=False, type="gallery", cover_field_id=cover_id
            ),
        ],
        thought="chain",
    )["created_views"]
    assert [v["name"] for v in views] == ["All orders", "Board", "Covers"]
    grid_view_id = views[0]["id"]

    # --- view id + field ids -> create_view_filters -----------------------
    per_view = create_view_filters(
        ctx,
        view_filters=[
            ViewFiltersArgs(
                view_id=grid_view_id,
                filters=[
                    ViewFilterItemCreate(
                        field_id=status_id,
                        type="single_select",
                        operator="is_any_of",
                        value=["Open"],
                    ),
                    ViewFilterItemCreate(
                        field_id=amount_id,
                        type="number",
                        operator="higher_than",
                        value=100,
                    ),
                ],
            )
        ],
        thought="chain",
    )["created_view_filters"]
    assert len(per_view) == 1 and per_view[0]["view_id"] == grid_view_id
    # create_view_filters logs and skips filters it cannot build, hence the count.
    assert len(per_view[0]["filters"]) == 2, (
        f"only {len(per_view[0]['filters'])} of 2 filters were created; the rest "
        f"were skipped because the field ids or types no longer match what the "
        f"schema reports. {CONTRACT_CHANGED}"
    )

    # --- list_views / list_tables confirm what the chain built -------------
    listed = list_views(ctx, table_id=orders_id, thought="chain")["views"]
    by_name = {v["name"]: v for v in listed}
    assert {"All orders", "Board", "Covers"} <= set(by_name)
    assert by_name["Board"]["column_field_id"] == status_id
    # The gallery cover round-trip has its own regression test below.
    assert views[2]["cover_field_id"] == cover_id

    listed_tables = list_tables(
        ctx,
        filters=ListTablesFilterArg(
            database_id_or_name=database_id, table_ids_or_names=None
        ),
        thought="chain",
    )
    assert {t["id"] for t in listed_tables} == {customers_id, orders_id}

    # --- final ORM state ---------------------------------------------------
    orders = Table.objects.get(id=orders_id)
    assert orders.database_id == database_id
    assert orders.database.workspace_id == workspace.id
    assert set(
        BaserowField.objects.filter(table=orders).values_list("name", flat=True)
    ) == {"Order", "Amount", "Due", "Status", "Customer", "Cover", "Priority"}
    # The default grid view every new table gets, plus the three created here.
    assert View.objects.filter(table=orders).count() == 4
    assert ViewFilter.objects.filter(view_id=grid_view_id).count() == 2
    select_filter = ViewFilter.objects.get(view_id=grid_view_id, field_id=status_id)
    assert select_filter.value == str(open_option["id"]), (
        f"the 'Open' option id get_tables_schema reported ({open_option['id']}) "
        f"is not what the stored filter resolves to ({select_filter.value!r}). "
        f"{CONTRACT_CHANGED}"
    )


@pytest.mark.django_db
def test_chain_gallery_cover_field_survives_create_views(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)

    result = create_tables(
        ctx,
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Products",
                primary_field_name="Product",
                fields=[FieldItemCreate(name="Photo", type="file")],
            )
        ],
        add_sample_rows=False,
        thought="chain",
    )
    table_id = result["created_tables"][0]["id"]

    schemas = get_tables_schema(
        ctx, table_ids=[table_id], full_schema=True, thought="chain"
    )["tables_schema"]
    photo_id = schema_field(schemas[0], "Photo")["id"]

    views = create_views(
        ctx,
        table_id=table_id,
        views=[
            ViewItemCreate(
                name="Catalogue",
                public=False,
                type="gallery",
                cover_field_id=photo_id,
            )
        ],
        thought="chain",
    )["created_views"]
    view_id = views[0]["id"]

    listed = list_views(ctx, table_id=table_id, thought="chain")["views"]
    gallery = next(v for v in listed if v["id"] == view_id)
    assert gallery["cover_field_id"] == photo_id, (
        f"create_views was given cover_field_id={photo_id} and echoed it back, "
        f"but list_views reads {gallery['cover_field_id']!r}: the cover field "
        "was never persisted, so the user gets a gallery with no cover image."
    )
    assert View.objects.get(id=view_id).specific.card_cover_image_field_id == photo_id


# ===========================================================================
# CHAIN 2 — reloading row tools for a table the agent already loaded
# ===========================================================================

ROW_OPERATIONS = ["create", "update", "delete"]


@pytest.mark.django_db(transaction=True)
def test_chain_reloading_row_tools_for_the_same_table_is_harmless(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    ctx = make_test_ctx(user, workspace)

    result = create_tables(
        ctx,
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Tasks",
                primary_field_name="Task",
                fields=[FieldItemCreate(name="Notes", type="long_text")],
            )
        ],
        add_sample_rows=False,
        thought="chain",
    )
    created = result["created_tables"][0]
    table_id = created["id"]

    load_row_tools(
        ctx, table_ids=[table_id], operations=ROW_OPERATIONS, thought="chain"
    )
    load_row_tools(
        ctx, table_ids=[table_id], operations=ROW_OPERATIONS, thought="chain"
    )

    toolset = dynamic_toolset(ctx)
    expected_names = {f"{op}_rows_in_table_{table_id}" for op in ROW_OPERATIONS}
    assert set(toolset.tools) == expected_names, (
        f"Reloading row tools for table {table_id} left the agent with "
        f"{sorted(toolset.tools)}; one tool per name is the only usable state."
    )

    create_tool = toolset.tools[f"create_rows_in_table_{table_id}"]
    # The row tools embed their schema; that is why the agent skips a schema lookup.
    assert row_tool_field_names(create_tool) == schema_field_names(created), (
        f"the generated row tool accepts "
        f"{sorted(row_tool_field_names(create_tool))} but the schema "
        f"create_tables returned says {sorted(schema_field_names(created))}. "
        f"{CONTRACT_CHANGED}"
    )

    result = call_row_tool(
        create_tool,
        rows=[{"Task": "Write the chain test", "Notes": "done"}],
        thought="chain",
    )
    assert len(result["created_row_ids"]) == 1
    assert Table.objects.get(id=table_id).get_model().objects.count() == 1
