"""
Deterministic tool-contract suite for the Kuma assistant.

No LLM, no network: every read/list tool is invoked against one richly seeded
workspace and its output is checked for shape. This is the guard against
backend refactors that silently break an assistant tool — e.g. b70bc968d
renamed ``Element.order`` to ``Element.compat_order`` while
``ElementItem.from_orm`` kept reading ``element.order``, so ``list_elements``
raised ``AttributeError`` in production for seven weeks.
"""

from dataclasses import dataclass
from typing import Any, Callable

from django.contrib.auth.models import AbstractUser

import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.graph.types import GraphPointPosition
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.automation.tools import (
    list_nodes,
    list_workflows,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    list_actions,
    list_data_sources,
    list_elements,
    list_pages,
)
from baserow_enterprise.assistant.tools.core.tools import list_builders
from baserow_enterprise.assistant.tools.database.tools import (
    get_tables_schema,
    list_rows,
    list_tables,
    list_views,
)
from baserow_enterprise.assistant.tools.database.types import ListTablesFilterArg
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .utils import make_test_ctx

# ===========================================================================
# Seeded workspace
# ===========================================================================

SEEDED_ELEMENT_TYPES = frozenset(
    {
        "heading",
        "text",
        "button",
        "link",
        "image",
        "column",
        "form_container",
        "input_text",
        "choice",
        "checkbox",
        "table",
        "menu",
    }
)

SEEDED_VIEW_TYPES = frozenset(
    {"grid", "gallery", "form", "kanban", "calendar", "timeline"}
)


@dataclass(frozen=True)
class SeededWorkspace:
    """One workspace holding every entity the read tools have to serialize."""

    user: AbstractUser
    workspace: Workspace
    database: Database
    table: Table
    linked_table: Table
    builder: Builder
    page: Page
    button: Element
    automation: Automation
    workflow: AutomationWorkflow


def _seed_database(fx: Any, user: AbstractUser, workspace: Workspace) -> dict[str, Any]:
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Contracts DB"
    )
    table, fields, _ = fx.build_table(
        user=user,
        database=database,
        name="Orders",
        columns=[
            ("Name", {"type": "text", "primary": True}),
            ("Notes", "long_text"),
            ("Amount", "number"),
            ("Due", "date"),
            ("Finished", "date"),
            ("Done", "boolean"),
        ],
        rows=[
            ["First order", "A note", 10, "2026-01-01", "2026-01-05", True],
            ["Second order", "Another note", 20, "2026-02-01", "2026-02-05", False],
        ],
    )
    linked_table, _, _ = fx.build_table(
        user=user,
        database=database,
        name="Customers",
        columns=[("Name", {"type": "text", "primary": True}), ("City", "text")],
        rows=[["Acme", "Berlin"], ["Globex", "Paris"]],
    )
    fx.create_link_row_field(name="Customer", table=table, link_row_table=linked_table)

    status_field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=status_field, value="Open", color="blue")
    cover_field = fx.create_file_field(table=table, name="Cover")
    due_field, finished_field = fields[3], fields[4]

    fx.create_grid_view(table=table, name="Grid", order=1)
    fx.create_gallery_view(
        table=table, name="Gallery", order=2, card_cover_image_field=cover_field
    )
    form_view = fx.create_form_view(table=table, name="Form", order=3)
    fx.create_form_view_field_options(form_view, enabled=True)
    fx.create_kanban_view(
        table=table, name="Kanban", order=4, single_select_field=status_field
    )
    fx.create_calendar_view(table=table, name="Calendar", order=5, date_field=due_field)
    fx.create_timeline_view(
        table=table,
        name="Timeline",
        order=6,
        start_date_field=due_field,
        end_date_field=finished_field,
    )

    return {
        "database": database,
        "table": table,
        "linked_table": linked_table,
        "name_field": fields[0],
    }


def _seed_builder(
    fx: Any, user: AbstractUser, workspace: Workspace, table: Table, name_field: Any
) -> dict[str, Any]:
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Customer Portal"
    )
    page = fx.create_builder_page(builder=builder, name="Home", path="/home")
    integration = fx.create_local_baserow_integration(application=builder, user=user)
    data_source = fx.create_builder_local_baserow_list_rows_data_source(
        page=page, name="Orders", table=table, integration=integration
    )

    fx.create_builder_heading_element(page=page, value="'Welcome'", level=1)
    fx.create_builder_text_element(page=page, value="'Some body copy'")
    fx.create_builder_image_element(page=page)
    fx.create_builder_link_element(page=page, value="'Go to docs'")
    fx.create_builder_table_element(page=page, data_source=data_source)
    fx.create_builder_menu_element_items(page=page)

    # Containers with children exercise parent_element_id / place_in_container.
    column = fx.create_builder_column_element(page=page, column_amount=2)
    fx.create_builder_text_element(
        page=page,
        value="'In a column'",
        position=GraphPointPosition.CHILD,
        reference_element=column,
        place_in_container="0",
    )
    form_container = fx.create_builder_form_container_element(page=page)
    fx.create_builder_input_text_element(
        page=page,
        label="'Your name'",
        position=GraphPointPosition.CHILD,
        reference_element=form_container,
        place_in_container="0",
    )
    fx.create_builder_choice_element(
        page=page,
        label="'Pick one'",
        position=GraphPointPosition.CHILD,
        reference_element=form_container,
        place_in_container="0",
    )
    fx.create_builder_checkbox_element(
        page=page,
        label="'Agree'",
        position=GraphPointPosition.CHILD,
        reference_element=form_container,
        place_in_container="0",
    )
    button = fx.create_builder_button_element(
        page=page,
        value="'Submit'",
        position=GraphPointPosition.CHILD,
        reference_element=form_container,
        place_in_container="0",
    )

    # Shared-page elements are merged into list_elements as page_name="[shared]".
    fx.create_builder_heading_element(page=builder.shared_page, value="'Header'")

    fx.create_notification_workflow_action(page=page, element=button, event="click")
    upsert_service = fx.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )
    upsert_service.field_mappings.create(field=name_field, value="'Ordered'")
    fx.create_local_baserow_create_row_workflow_action(
        page=page, element=button, event="click", service=upsert_service
    )

    return {"builder": builder, "page": page, "button": button}


def _seed_automation(
    fx: Any, user: AbstractUser, workspace: Workspace
) -> dict[str, Any]:
    automation = fx.create_automation_application(
        user=user, workspace=workspace, name="Ops"
    )
    workflow = fx.create_automation_workflow(
        user=user, automation=automation, name="Nightly sync"
    )
    fx.create_local_baserow_create_row_action_node(user=user, workflow=workflow)
    fx.create_local_baserow_update_row_action_node(user=user, workflow=workflow)
    return {"automation": automation, "workflow": workflow}


@pytest.fixture
def seed(premium_data_fixture: Any) -> SeededWorkspace:
    fx = premium_data_fixture
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)

    db_parts = _seed_database(fx, user, workspace)
    builder_parts = _seed_builder(
        fx, user, workspace, db_parts["table"], db_parts["name_field"]
    )
    automation_parts = _seed_automation(fx, user, workspace)

    return SeededWorkspace(
        user=user,
        workspace=workspace,
        database=db_parts["database"],
        table=db_parts["table"],
        linked_table=db_parts["linked_table"],
        builder=builder_parts["builder"],
        page=builder_parts["page"],
        button=builder_parts["button"],
        automation=automation_parts["automation"],
        workflow=automation_parts["workflow"],
    )


# ===========================================================================
# Shape assertions
# ===========================================================================


def assert_items(
    items: Any, required: dict[str, type | tuple[type, ...]], label: str
) -> None:
    """Assert ``items`` is a non-empty list of dicts carrying typed keys."""

    assert isinstance(items, list), f"{label}: expected a list, got {type(items)}"
    assert items, f"{label}: empty collection — the seed must populate this tool"
    for item in items:
        assert isinstance(item, dict), f"{label}: expected dicts, got {type(item)}"
        for key, expected in required.items():
            assert key in item, f"{label}: missing key {key!r} in {item!r}"
            assert isinstance(item[key], expected), (
                f"{label}: {key!r} is {type(item[key])}, expected {expected}"
            )


# ===========================================================================
# Read-tool contract cases
# ===========================================================================


@dataclass(frozen=True)
class ReadToolCase:
    """One read tool, how to call it, and what its output must look like."""

    name: str
    invoke: Callable[[Any, SeededWorkspace], Any]
    check: Callable[[Any, SeededWorkspace], None]


def _check_list_builders(result: Any, seed: SeededWorkspace) -> None:
    assert set(result) >= {"database", "application", "automation"}
    for builder_type in ("database", "application", "automation"):
        assert_items(
            result[builder_type],
            {"id": int, "name": str, "type": str},
            f"list_builders[{builder_type}]",
        )
    ids = {item["id"] for items in result.values() for item in items}
    assert {seed.database.id, seed.builder.id, seed.automation.id} <= ids


def _check_list_tables(result: Any, seed: SeededWorkspace) -> None:
    assert_items(result, {"id": int, "name": str, "database_id": int}, "list_tables")
    assert {t["id"] for t in result} == {seed.table.id, seed.linked_table.id}


def _check_get_tables_schema(result: Any, seed: SeededWorkspace) -> None:
    schemas = result["tables_schema"]
    assert_items(
        schemas,
        {"id": int, "name": str, "fields": list, "primary_field": dict},
        "get_tables_schema",
    )
    assert {s["id"] for s in schemas} == {seed.table.id, seed.linked_table.id}
    for schema in schemas:
        assert_items(
            schema["fields"],
            {"id": int, "name": str, "type": str},
            f"get_tables_schema[{schema['name']}].fields",
        )
    orders = next(s for s in schemas if s["id"] == seed.table.id)
    orders_fields = [orders["primary_field"], *orders["fields"]]
    assert {f["type"] for f in orders_fields} >= {
        "text",
        "long_text",
        "number",
        "date",
        "boolean",
        "single_select",
        "link_row",
        "file",
    }


def _check_list_rows(result: Any, seed: SeededWorkspace) -> None:
    assert result["total"] == 2
    assert_items(result["rows"], {"id": int, "Name": str}, "list_rows")
    assert {row["Name"] for row in result["rows"]} == {"First order", "Second order"}


def _check_list_views(result: Any, seed: SeededWorkspace) -> None:
    views = result["views"]
    assert_items(
        views, {"id": int, "name": str, "type": str, "public": bool}, "list_views"
    )
    assert {v["type"] for v in views} == set(SEEDED_VIEW_TYPES)


def _check_list_workflows(result: Any, seed: SeededWorkspace) -> None:
    assert_items(
        result["workflows"], {"id": int, "name": str, "state": str}, "list_workflows"
    )
    assert [w["id"] for w in result["workflows"]] == [seed.workflow.id]


def _check_list_nodes(result: Any, seed: SeededWorkspace) -> None:
    assert_items(result["nodes"], {"id": int, "label": str, "type": str}, "list_nodes")
    assert len(result["nodes"]) == 3


def _check_list_pages(result: Any, seed: SeededWorkspace) -> None:
    assert_items(
        result["pages"],
        {"id": int, "name": str, "path": str, "visibility": str, "roles": list},
        "list_pages",
    )
    assert [p["id"] for p in result["pages"]] == [seed.page.id]
    assert isinstance(result["user_sources"], list)
    assert isinstance(result["available_roles"], list)


def _check_list_data_sources(result: Any, seed: SeededWorkspace) -> None:
    sources = result["data_sources"]
    assert_items(sources, {"id": int, "name": str, "type": str}, "list_data_sources")
    orders = next(ds for ds in sources if ds["name"] == "Orders")
    assert orders["type"] == "local_baserow_list_rows"
    assert orders["table_id"] == seed.table.id
    assert orders["table_name"] == seed.table.name


def _check_list_elements(result: Any, seed: SeededWorkspace) -> None:
    elements = result["elements"]
    assert_items(
        elements,
        {"id": int, "type": str, "is_container": bool, "page_name": str},
        "list_elements",
    )
    assert set(SEEDED_ELEMENT_TYPES) <= {el["type"] for el in elements}
    assert any(el["parent_element_id"] is not None for el in elements)
    assert any(el["page_name"] == "[shared]" for el in elements)
    menu = next(el for el in elements if el["type"] == "menu")
    assert_items(menu["menu_items"], {"name": str, "type": str}, "list_elements.menu")


def _check_list_actions(result: Any, seed: SeededWorkspace) -> None:
    actions = result["workflow_actions"]
    assert_items(
        actions,
        {"id": int, "type": str, "element_id": int, "event": str},
        "list_actions",
    )
    assert {a["type"] for a in actions} == {"notification", "create_row"}
    create_row = next(a for a in actions if a["type"] == "create_row")
    assert create_row["table_id"] == seed.table.id
    assert_items(
        create_row["field_mappings"],
        {"field_id": int, "field_name": str, "value": str},
        "list_actions.field_mappings",
    )


READ_TOOL_CASES: list[ReadToolCase] = [
    ReadToolCase(
        "list_builders",
        lambda ctx, s: list_builders(ctx, builder_types=None, thought="contract"),
        _check_list_builders,
    ),
    ReadToolCase(
        "list_tables",
        lambda ctx, s: list_tables(
            ctx,
            filters=ListTablesFilterArg(
                database_id_or_name=s.database.id, table_ids_or_names=None
            ),
            thought="contract",
        ),
        _check_list_tables,
    ),
    ReadToolCase(
        "get_tables_schema",
        lambda ctx, s: get_tables_schema(
            ctx,
            table_ids=[s.table.id, s.linked_table.id],
            full_schema=True,
            thought="contract",
        ),
        _check_get_tables_schema,
    ),
    ReadToolCase(
        "list_rows",
        lambda ctx, s: list_rows(
            ctx,
            table_id=s.table.id,
            offset=0,
            limit=20,
            field_ids=None,
            thought="contract",
        ),
        _check_list_rows,
    ),
    ReadToolCase(
        "list_views",
        lambda ctx, s: list_views(ctx, table_id=s.table.id, thought="contract"),
        _check_list_views,
    ),
    ReadToolCase(
        "list_workflows",
        lambda ctx, s: list_workflows(
            ctx, automation_id=s.automation.id, thought="contract"
        ),
        _check_list_workflows,
    ),
    ReadToolCase(
        "list_nodes",
        lambda ctx, s: list_nodes(ctx, workflow_id=s.workflow.id, thought="contract"),
        _check_list_nodes,
    ),
    ReadToolCase(
        "list_pages",
        lambda ctx, s: list_pages(ctx, application_id=s.builder.id, thought="contract"),
        _check_list_pages,
    ),
    ReadToolCase(
        "list_data_sources",
        lambda ctx, s: list_data_sources(ctx, page_id=s.page.id, thought="contract"),
        _check_list_data_sources,
    ),
    ReadToolCase(
        "list_elements",
        lambda ctx, s: list_elements(ctx, page_id=s.page.id, thought="contract"),
        _check_list_elements,
    ),
    ReadToolCase(
        "list_actions",
        lambda ctx, s: list_actions(ctx, page_id=s.page.id, thought="contract"),
        _check_list_actions,
    ),
]

COVERED_TOOLS: frozenset[str] = frozenset(case.name for case in READ_TOOL_CASES)


@pytest.mark.django_db
@pytest.mark.parametrize("case", READ_TOOL_CASES, ids=lambda case: case.name)
def test_read_tool_contract(case: ReadToolCase, seed: SeededWorkspace) -> None:
    ctx = make_test_ctx(seed.user, seed.workspace)
    case.check(case.invoke(ctx, seed), seed)


# ===========================================================================
# Registry coverage guard
# ===========================================================================

_WRITE = "Mutating tool; its ORM round-trip is covered by the per-domain write tests."
_LLM = "Needs a live model call, so it cannot run deterministically here."
_CONTROL = "Control-flow only; serializes no ORM entity."

EXEMPT_TOOLS: dict[str, str] = {
    "switch_mode": _CONTROL,
    "navigate": _CONTROL,
    "ask_user": _CONTROL,
    "load_row_tools": _CONTROL,
    "search_user_docs": _LLM,
    "generate_formula": _LLM,
    "create_builders": _WRITE,
    "update_builder": _WRITE,
    "create_tables": _WRITE,
    "create_fields": _WRITE,
    "update_fields": _WRITE,
    "delete_fields": _WRITE,
    "create_views": _WRITE,
    "create_view_filters": _WRITE,
    "create_workflows": _WRITE,
    "add_nodes": _WRITE,
    "update_nodes": _WRITE,
    "delete_nodes": _WRITE,
    "create_pages": _WRITE,
    "update_page": _WRITE,
    "create_data_sources": _WRITE,
    "update_data_source": _WRITE,
    "create_display_elements": _WRITE,
    "create_layout_elements": _WRITE,
    "create_form_elements": _WRITE,
    "create_collection_elements": _WRITE,
    "update_element": _WRITE,
    "update_element_style": _WRITE,
    "move_elements": _WRITE,
    "create_actions": _WRITE,
    "add_action_field_mapping": _WRITE,
    "setup_page": _WRITE,
    "setup_user_source": _WRITE,
    "set_theme": _WRITE,
}


def registered_tool_names() -> set[str]:
    """Every tool function name reachable through the assistant tool registry."""

    return {
        func.__name__
        for tool_type in assistant_tool_registry.get_all()
        for func in tool_type.get_tool_functions()
    }


def test_every_registered_tool_is_covered_or_exempt() -> None:
    registered = registered_tool_names()
    unclassified = registered - COVERED_TOOLS - set(EXEMPT_TOOLS)
    assert not unclassified, (
        f"New assistant tools {sorted(unclassified)} have no contract coverage. "
        "Add a ReadToolCase for read tools, or an EXEMPT_TOOLS entry with a reason."
    )


def test_coverage_sets_match_the_registry() -> None:
    registered = registered_tool_names()
    stale = (COVERED_TOOLS | set(EXEMPT_TOOLS)) - registered
    assert not stale, f"Tools {sorted(stale)} are no longer registered; drop them."


def test_read_tools_are_not_hidden_in_the_exempt_set() -> None:
    assert not COVERED_TOOLS & set(EXEMPT_TOOLS)
    assert not {name for name in EXEMPT_TOOLS if name.startswith("list_")}
