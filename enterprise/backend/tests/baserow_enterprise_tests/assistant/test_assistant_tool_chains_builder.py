"""
Cross-tool chain tests for the builder and automation assistant tools.

Every test here drives the real tool functions in the order the agent drives
them and feeds each tool's OUTPUT into the next tool's INPUT — no LLM, no
network. Per-tool coverage cannot see a broken handoff: both regressions this
suite exists for wrote their objects successfully and only failed one step
later, when the next tool consumed the result.

- ``Element.order`` was renamed by a backend refactor while ``list_elements``
  still read it: elements were created fine, the read-back raised
  ``AttributeError`` in 94% of the traces that called it, for 36 days.
- ``setup_page`` is the composite the model is told to prefer over the granular
  create tools. Nothing today pins the two paths together, so the composite can
  silently drift into building a different page.

A failure here means a contract changed — a backend model, a serializer field,
or a tool's return shape — and the tools under
``baserow_enterprise/assistant/tools/`` must be updated to match.
"""

from dataclasses import dataclass
from typing import Any, Callable

from django.contrib.auth.models import AbstractUser

import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.automation.tools import (
    add_nodes,
    create_workflows,
    list_nodes,
    list_workflows,
    update_nodes,
)
from baserow_enterprise.assistant.tools.automation.types import (
    ActionNodeCreate,
    NodeUpdate,
    TriggerNodeCreate,
    WorkflowCreate,
)
from baserow_enterprise.assistant.tools.automation.types.node import (
    AutomationFieldValue,
    RowsTriggersSettings,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    create_actions,
    create_collection_elements,
    create_data_sources,
    create_display_elements,
    create_layout_elements,
    create_pages,
    list_actions,
    list_data_sources,
    list_elements,
    setup_page,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ActionCreate,
    CollectionElementCreate,
    DataSourceCreate,
    DisplayElementCreate,
    ElementItemCreate,
    FieldValueMapping,
    LayoutElementCreate,
    PageCreate,
    TableFieldConfig,
)
from baserow_enterprise.assistant.tools.core.tools import create_builders
from baserow_enterprise.assistant.tools.core.types import BuilderItemCreate
from baserow_enterprise.assistant.tools.database.tools import create_tables
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemCreate,
    SelectOptionCreate,
    TableItemCreate,
)

from .utils import create_fake_tool_helpers, make_test_ctx

READ_BACK_HINT = (
    "CONTRACT BREAK — the objects were written fine, but the assistant can no "
    "longer read them back. A backend model, serializer or tool return shape "
    "changed under the read tool (this is exactly how the removal of "
    "Element.order broke list_elements in production for 36 days). Fix the "
    "read path in baserow_enterprise/assistant/tools/; do not delete this test."
)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly instead of reaching a live model: chains must stay literal."""

    def forbid_generator(*args: Any, **kwargs: Any) -> Callable[..., dict[str, str]]:
        def generate(*inner_args: Any, **inner_kwargs: Any) -> dict[str, str]:
            raise AssertionError(
                "A tool in the chain asked the formula-generation agent for a "
                "formula. Chain tests must stay deterministic — pass literal "
                "values, never '$formula:' intents."
            )

        return generate

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.get_formula_generator",
        forbid_generator,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.automation.agents.get_formula_generator",
        forbid_generator,
    )


# ===========================================================================
# Chain helpers
# ===========================================================================


@dataclass(frozen=True)
class SeededTable:
    """A workspace plus the one table every chain below is built on."""

    user: AbstractUser
    workspace: Workspace
    ctx: Any
    table_id: int
    name_field_id: int
    status_field_id: int


@dataclass(frozen=True)
class PageFingerprint:
    """A page as the read tools describe it, with database ids normalised out."""

    elements: tuple[tuple[Any, ...], ...]
    data_sources: tuple[tuple[Any, ...], ...]
    actions: tuple[tuple[Any, ...], ...]


def _read_back(tool: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Call a read tool, turning any exception into a contract-break failure."""

    try:
        return tool(**kwargs)
    except Exception as exc:
        pytest.fail(
            f"{tool.__name__}() raised {type(exc).__name__}: {exc}\n{READ_BACK_HINT}"
        )


def _seed_table(data_fixture: Any) -> SeededTable:
    """Create the workspace and, through create_tables, the Projects table."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Portfolio"
    )
    ctx = make_test_ctx(user, workspace, create_fake_tool_helpers())

    result = create_tables(
        ctx,
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Projects",
                primary_field_name="Name",
                fields=[
                    FieldItemCreate(name="Budget", type="number", decimal_places=2),
                    FieldItemCreate(
                        name="Status",
                        type="single_select",
                        options=[
                            SelectOptionCreate(value="Active", color="green"),
                            SelectOptionCreate(value="Done", color="blue"),
                        ],
                    ),
                ],
            )
        ],
        add_sample_rows=False,
        thought="chain: the table the page and the workflow are built on",
    )

    assert result["notes"] == [], (
        f"create_tables reported problems while seeding the chain: "
        f"{result['notes']}. Every later step consumes the field ids it "
        f"returns, so fix the table creation contract first."
    )
    table = result["created_tables"][0]
    fields_by_name = {f["name"]: f["id"] for f in table["fields"]}
    assert "Status" in fields_by_name, (
        f"create_tables no longer reports non-primary fields under 'fields' "
        f"(got keys {sorted(table)} / field names {sorted(fields_by_name)}). "
        f"Everything downstream — data sources, table columns, row actions, "
        f"automation field values — reads field ids from this payload."
    )

    return SeededTable(
        user=user,
        workspace=workspace,
        ctx=ctx,
        table_id=table["id"],
        name_field_id=table["primary_field"]["id"],
        status_field_id=fields_by_name["Status"],
    )


def _create_builder_app(ctx: Any, name: str) -> int:
    """Create a builder application through the tool and return its id."""

    created = create_builders(
        ctx,
        builders=[BuilderItemCreate(name=name, type="application")],
        thought="chain: the application the page lives in",
    )["created_builders"]

    assert len(created) == 1 and "id" in created[0], (
        f"create_builders no longer returns [{{'id': ...}}] (got {created}). "
        f"create_pages, setup_page and list_pages all take that id as their "
        f"application_id."
    )
    return created[0]["id"]


def _create_page(ctx: Any, application_id: int, name: str, path: str) -> int:
    """Create a page through the tool and return its id."""

    created = create_pages(
        ctx,
        application_id=application_id,
        pages=[PageCreate(name=name, path=path)],
        thought="chain: the page the data sources and elements attach to",
    )["created_pages"]

    assert len(created) == 1 and "id" in created[0], (
        f"create_pages no longer returns [{{'id': ...}}] (got {created}). "
        f"Every builder tool after it is addressed by that page_id."
    )
    return created[0]["id"]


def _fingerprint_page(ctx: Any, page_id: int) -> PageFingerprint:
    """Describe a page through the read tools, with ids replaced by positions."""

    elements = _read_back(
        list_elements, ctx=ctx, page_id=page_id, thought="chain: read the tree back"
    )["elements"]
    data_sources = _read_back(
        list_data_sources, ctx=ctx, page_id=page_id, thought="chain: read the tree back"
    )["data_sources"]
    actions = _read_back(
        list_actions, ctx=ctx, page_id=page_id, thought="chain: read the tree back"
    )["workflow_actions"]

    at = {element["id"]: position for position, element in enumerate(elements)}
    return PageFingerprint(
        elements=tuple(
            (
                element["type"],
                element["label"],
                element["is_container"],
                element["place_in_container"],
                at.get(element["parent_element_id"]),
            )
            for element in elements
        ),
        data_sources=tuple(
            (ds["name"], ds["type"], ds["table_id"]) for ds in data_sources
        ),
        actions=tuple(
            (
                action["type"],
                action["event"],
                at.get(action["element_id"]),
                action["table_id"],
                tuple(
                    sorted(
                        (m["field_id"], m["value"])
                        for m in action["field_mappings"] or []
                    )
                ),
            )
            for action in actions
        ),
    )


def _reported_node_type(tool_vocabulary_type: str) -> str:
    """Map a node type the tools accept onto the type list_nodes reports back."""

    try:
        return automation_node_type_registry.get(tool_vocabulary_type).type
    except Exception as exc:
        pytest.fail(
            f"The automation tools accept type={tool_vocabulary_type!r} but the "
            f"node registry no longer resolves it ({type(exc).__name__}: {exc}). "
            f"The Literal vocabulary in assistant/tools/automation/types/node.py "
            f"survives only as a compat_type alias of the registered node type — "
            f"if the alias is dropped, every create_workflows/add_nodes call "
            f"fails. Update the tool types together with the registry."
        )


def _element_ids_by_ref(result: dict[str, Any], tool_name: str) -> dict[str, int]:
    """Read the ref → id mapping a create_*_elements call returned."""

    created = result.get("created_elements")
    assert created and not result.get("errors"), (
        f"{tool_name} created nothing usable: {result}. The refs it returns are "
        f"how the next tool in the chain addresses these elements."
    )
    return {element["ref"]: element["id"] for element in created}


# ===========================================================================
# Chain 1: table -> application -> page -> data source -> elements -> actions
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_chain_builds_a_page_against_a_real_table(data_fixture):
    """Drive the whole builder chain, passing each tool's output to the next."""

    seed = _seed_table(data_fixture)
    ctx = seed.ctx

    application_id = _create_builder_app(ctx, "Project Portal")
    page_id = _create_page(ctx, application_id, "Projects", "/projects")

    # Data source, bound to the table id create_tables returned.
    ds_result = create_data_sources(
        ctx,
        page_id=page_id,
        data_sources=[
            DataSourceCreate(
                ref="projects_ds",
                name="Projects",
                type="list_rows",
                table_id=seed.table_id,
            )
        ],
        thought="chain: feed the page from the table just created",
    )
    ds_id = ds_result["ref_to_id_map"].get("projects_ds")
    assert isinstance(ds_id, int), (
        f"create_data_sources no longer maps refs to ids in 'ref_to_id_map' "
        f"(got {ds_result}). Collection elements and refresh actions bind to "
        f"data sources through that ref."
    )

    # Collection element, bound to the data source by ref (not by id).
    table_result = create_collection_elements(
        ctx,
        page_id=page_id,
        elements=[
            CollectionElementCreate(
                ref="projects_table",
                type="table",
                data_source="projects_ds",
                fields=[
                    TableFieldConfig(name="Name"),
                    TableFieldConfig(name="Status"),
                ],
            )
        ],
        thought="chain: show the data source rows",
    )
    table_element_id = _element_ids_by_ref(table_result, "create_collection_elements")[
        "projects_table"
    ]

    layout_result = create_layout_elements(
        ctx,
        page_id=page_id,
        elements=[
            LayoutElementCreate(ref="cols", type="column", column_amount=2),
        ],
        thought="chain: a container for the heading and the button",
    )
    column_element_id = _element_ids_by_ref(layout_result, "create_layout_elements")[
        "cols"
    ]

    # Children reference the container by the ref returned in the previous call.
    display_result = create_display_elements(
        ctx,
        page_id=page_id,
        elements=[
            DisplayElementCreate(
                ref="title",
                type="heading",
                value="Projects",
                level=1,
                parent_element="cols",
                place_in_container="0",
            ),
            DisplayElementCreate(
                ref="new_btn",
                type="button",
                value="New project",
                parent_element="cols",
                place_in_container="1",
            ),
        ],
        thought="chain: title and call to action inside the container",
    )
    display_ids = _element_ids_by_ref(display_result, "create_display_elements")

    # Action attached to the button by ref, writing to the seeded table.
    action_result = create_actions(
        ctx,
        page_id=page_id,
        actions=[
            ActionCreate(
                type="create_row",
                element="new_btn",
                event="click",
                table_id=seed.table_id,
                field_values=[
                    FieldValueMapping(field_id=str(seed.name_field_id), value="'New'"),
                    FieldValueMapping(
                        field_id=str(seed.status_field_id), value="'Active'"
                    ),
                ],
            )
        ],
        thought="chain: the button writes a row into the seeded table",
    )
    assert not action_result.get("errors") and action_result["created_actions"], (
        f"create_actions could not attach an action to the 'new_btn' ref created "
        f"by the previous call: {action_result}. Element refs are tracked per "
        f"page in ToolHelpers.request_context — a change there breaks every "
        f"multi-call page build."
    )
    action_id = action_result["created_actions"][0]["id"]

    # --- read the whole tree back -----------------------------------------

    elements = _read_back(
        list_elements, ctx=ctx, page_id=page_id, thought="chain: verify the tree"
    )["elements"]
    by_id = {element["id"]: element for element in elements}
    expected_ids = {
        table_element_id,
        column_element_id,
        display_ids["title"],
        display_ids["new_btn"],
    }
    assert expected_ids <= set(by_id), (
        f"list_elements did not return the elements the create tools reported "
        f"creating (missing {sorted(expected_ids - set(by_id))}, got "
        f"{sorted(by_id)}). Either creation silently dropped elements or the "
        f"listing no longer covers this page."
    )
    assert by_id[table_element_id]["type"] == "table", (
        f"list_elements reports the collection element as "
        f"{by_id[table_element_id]['type']!r}, not 'table'."
    )
    assert by_id[column_element_id]["is_container"] is True, (
        "list_elements no longer flags the column element as a container; the "
        "model uses is_container to decide what it may nest elements into."
    )
    for ref in ("title", "new_btn"):
        assert by_id[display_ids[ref]]["parent_element_id"] == column_element_id, (
            f"element {ref!r} was created with parent_element='cols' but reads "
            f"back with parent_element_id="
            f"{by_id[display_ids[ref]]['parent_element_id']} instead of "
            f"{column_element_id}. The ref → parent handoff is broken."
        )
    assert by_id[display_ids["title"]]["label"] == "'Projects'", (
        f"list_elements returns label "
        f"{by_id[display_ids['title']]['label']!r} for the heading; the label "
        f"preview is read off the element's formula value and its storage "
        f"shape changed."
    )

    read_data_sources = _read_back(
        list_data_sources, ctx=ctx, page_id=page_id, thought="chain: verify the data"
    )["data_sources"]
    assert [ds["id"] for ds in read_data_sources] == [ds_id], (
        f"list_data_sources returned {read_data_sources}, but "
        f"create_data_sources reported id {ds_id}."
    )
    assert read_data_sources[0]["table_id"] == seed.table_id, (
        f"the data source reads back bound to table "
        f"{read_data_sources[0]['table_id']}, not to the table create_tables "
        f"returned ({seed.table_id})."
    )

    read_actions = _read_back(
        list_actions, ctx=ctx, page_id=page_id, thought="chain: verify the actions"
    )["workflow_actions"]
    assert [action["id"] for action in read_actions] == [action_id], (
        f"list_actions returned {read_actions}, but create_actions reported id "
        f"{action_id}."
    )
    assert read_actions[0]["element_id"] == display_ids["new_btn"], (
        f"the action reads back attached to element "
        f"{read_actions[0]['element_id']} instead of the button "
        f"{display_ids['new_btn']} it was created against."
    )
    assert read_actions[0]["table_id"] == seed.table_id, (
        f"the create_row action reads back targeting table "
        f"{read_actions[0]['table_id']} instead of {seed.table_id}."
    )
    mapped_field_ids = {m["field_id"] for m in read_actions[0]["field_mappings"] or []}
    assert mapped_field_ids == {seed.name_field_id, seed.status_field_id}, (
        f"the action maps fields {sorted(mapped_field_ids)}, not the field ids "
        f"create_tables returned "
        f"({sorted([seed.name_field_id, seed.status_field_id])}). The "
        f"database → builder field-id handoff is broken."
    )

    # --- final database state ---------------------------------------------

    table_element = Element.objects.get(id=table_element_id).specific
    assert table_element.data_source_id == ds_id, (
        f"the table element is stored against data source "
        f"{table_element.data_source_id}, not the {ds_id} that "
        f"create_data_sources returned for ref 'projects_ds'."
    )
    action_service = BuilderWorkflowAction.objects.get(id=action_id).specific.service
    assert action_service.specific.table_id == seed.table_id, (
        f"the stored workflow action service points at table "
        f"{action_service.specific.table_id}, not {seed.table_id}."
    )


# ===========================================================================
# Chain 2: setup_page must agree with the granular tools
# ===========================================================================


def _build_page_step_by_step(
    ctx: Any, application_id: int, table_id: int, field_id: int
) -> int:
    """Build a page with the granular create tools and return its id."""

    page_id = _create_page(ctx, application_id, "Step by step", "/step-by-step")

    create_data_sources(
        ctx,
        page_id=page_id,
        data_sources=[
            DataSourceCreate(
                ref="ds", name="Projects", type="list_rows", table_id=table_id
            )
        ],
        thought="chain: granular build",
    )
    create_collection_elements(
        ctx,
        page_id=page_id,
        elements=[
            CollectionElementCreate(
                ref="grid",
                type="table",
                data_source="ds",
                fields=[TableFieldConfig(name="Name")],
            )
        ],
        thought="chain: granular build",
    )
    create_layout_elements(
        ctx,
        page_id=page_id,
        elements=[LayoutElementCreate(ref="cols", type="column", column_amount=2)],
        thought="chain: granular build",
    )
    create_display_elements(
        ctx,
        page_id=page_id,
        elements=[
            DisplayElementCreate(
                ref="title",
                type="heading",
                value="Projects",
                level=1,
                parent_element="cols",
                place_in_container="0",
            ),
            DisplayElementCreate(
                ref="btn",
                type="button",
                value="New project",
                parent_element="cols",
                place_in_container="1",
            ),
        ],
        thought="chain: granular build",
    )
    create_actions(
        ctx,
        page_id=page_id,
        actions=[
            ActionCreate(
                type="create_row",
                element="btn",
                event="click",
                table_id=table_id,
                field_values=[FieldValueMapping(field_id=str(field_id), value="'New'")],
            )
        ],
        thought="chain: granular build",
    )
    return page_id


def _build_page_with_setup_page(
    ctx: Any, application_id: int, table_id: int, field_id: int
) -> int:
    """Build the same page in a single setup_page call and return its id."""

    page_id = _create_page(ctx, application_id, "One shot", "/one-shot")

    result = setup_page(
        ctx,
        page_id=page_id,
        data_sources=[
            DataSourceCreate(
                ref="ds", name="Projects", type="list_rows", table_id=table_id
            )
        ],
        elements=[
            ElementItemCreate(
                ref="grid",
                type="table",
                data_source="ds",
                fields=[TableFieldConfig(name="Name")],
            ),
            ElementItemCreate(ref="cols", type="column", column_amount=2),
            ElementItemCreate(
                ref="title",
                type="heading",
                value="Projects",
                level=1,
                parent_element="cols",
                place_in_container="0",
            ),
            ElementItemCreate(
                ref="btn",
                type="button",
                value="New project",
                parent_element="cols",
                place_in_container="1",
            ),
        ],
        actions=[
            ActionCreate(
                type="create_row",
                element="btn",
                event="click",
                table_id=table_id,
                field_values=[FieldValueMapping(field_id=str(field_id), value="'New'")],
            )
        ],
        thought="chain: composite build",
    )

    assert not result.get("errors"), (
        f"setup_page reported errors while building the same page the granular "
        f"tools build without complaint: {result['errors']}. The composite and "
        f"the granular tools share the same phase helpers — one of them changed."
    )
    return page_id


@pytest.mark.django_db(transaction=True)
def test_setup_page_matches_the_granular_tools(data_fixture):
    """The composite tool and the step-by-step chain must build the same page."""

    seed = _seed_table(data_fixture)
    ctx = seed.ctx
    application_id = _create_builder_app(ctx, "Comparison")

    step_page_id = _build_page_step_by_step(
        ctx, application_id, seed.table_id, seed.name_field_id
    )
    one_shot_page_id = _build_page_with_setup_page(
        ctx, application_id, seed.table_id, seed.name_field_id
    )

    step = _fingerprint_page(ctx, step_page_id)
    one_shot = _fingerprint_page(ctx, one_shot_page_id)

    assert one_shot.data_sources == step.data_sources, (
        f"setup_page produced different data sources than create_data_sources:\n"
        f"  setup_page:  {one_shot.data_sources}\n"
        f"  granular:    {step.data_sources}\n"
        f"The two paths are documented as interchangeable and the model is told "
        f"to prefer setup_page, so this drift ships as a silent behaviour change."
    )
    assert one_shot.elements == step.elements, (
        f"setup_page produced a different element tree than the create_*_elements "
        f"tools:\n"
        f"  setup_page:  {one_shot.elements}\n"
        f"  granular:    {step.elements}\n"
        f"Tuples are (type, label, is_container, place_in_container, "
        f"parent position). The two paths are documented as interchangeable."
    )
    assert one_shot.actions == step.actions, (
        f"setup_page produced different workflow actions than create_actions:\n"
        f"  setup_page:  {one_shot.actions}\n"
        f"  granular:    {step.actions}\n"
        f"Tuples are (type, event, element position, table_id, field mappings)."
    )
    # Each page must own its data source: refs are tracked per page.
    step_grid, one_shot_grid = (
        Element.objects.filter(page_id=page_id, content_type__model="tableelement")
        .first()
        .specific
        for page_id in (step_page_id, one_shot_page_id)
    )
    assert step_grid.data_source_id != one_shot_grid.data_source_id, (
        "both pages' table elements point at the same data source; data source "
        "refs are tracked per page and must not leak across pages."
    )
    assert None not in (step_grid.data_source_id, one_shot_grid.data_source_id), (
        "a table element was stored without a data source: the ref → id "
        "resolution in the element creation path is broken."
    )


# ===========================================================================
# Chain 3: automation -> workflow -> nodes
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_chain_builds_an_automation_workflow(data_fixture):
    """Drive automation creation, workflow, node insertion and node update."""

    seed = _seed_table(data_fixture)
    ctx = seed.ctx

    created_builders = create_builders(
        ctx,
        builders=[BuilderItemCreate(name="Project Ops", type="automation")],
        thought="chain: the automation the workflow lives in",
    )["created_builders"]
    assert len(created_builders) == 1 and "id" in created_builders[0], (
        f"create_builders no longer returns [{{'id': ...}}] for automations "
        f"(got {created_builders}); create_workflows takes that id."
    )
    automation_id = created_builders[0]["id"]

    workflow_result = create_workflows(
        ctx,
        automation_id=automation_id,
        workflows=[
            WorkflowCreate(
                name="On new project",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    label="Project created",
                    type="rows_created",
                    rows_triggers_settings=RowsTriggersSettings(table_id=seed.table_id),
                ),
            )
        ],
        thought="chain: watch the table create_tables returned",
    )
    created_workflows = workflow_result["created_workflows"]
    assert len(created_workflows) == 1 and "id" in created_workflows[0], (
        f"create_workflows no longer returns [{{'id': ...}}] (got "
        f"{created_workflows}); add_nodes, update_nodes and list_nodes are all "
        f"addressed by that workflow id."
    )
    workflow_id = created_workflows[0]["id"]

    trigger_nodes = _read_back(
        list_nodes,
        ctx=ctx,
        workflow_id=workflow_id,
        thought="chain: find the node to attach to",
    )["nodes"]
    assert len(trigger_nodes) == 1 and trigger_nodes[0]["type"] == _reported_node_type(
        "rows_created"
    ), (
        f"list_nodes reports {trigger_nodes} for a workflow created with a "
        f"single rows_created trigger. Note the two vocabularies: the tools take "
        f"'rows_created' and read back the registered "
        f"{_reported_node_type('rows_created')!r}. add_nodes attaches to the node "
        f"id read from here, so a wrong or empty listing strands every later node."
    )
    trigger_id = trigger_nodes[0]["id"]

    # Node one wires to an existing node id, node two to a temp ref.
    add_result = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            ActionNodeCreate(
                ref="log_row",
                label="Log the project",
                type="create_row",
                previous_node_ref=str(trigger_id),
                table_id=seed.table_id,
                values=[
                    AutomationFieldValue(field_id=seed.name_field_id, value="Logged")
                ],
            ),
            ActionNodeCreate(
                ref="notify",
                label="Notify the team",
                type="smtp_email",
                previous_node_ref="log_row",
                to_emails="team@baserow.io",
                subject="A project was created",
                body="Check the portal.",
            ),
        ],
        thought="chain: append the actions after the trigger",
    )
    created_nodes = add_result["created_nodes"]
    assert [node["type"] for node in created_nodes] == [
        _reported_node_type("create_row"),
        _reported_node_type("smtp_email"),
    ], (
        f"add_nodes returned {created_nodes}. The first node references the "
        f"trigger id list_nodes reported and the second references the first "
        f"node's ref — a break in either wiring loses nodes silently."
    )
    log_node_id, notify_node_id = (node["id"] for node in created_nodes)

    update_result = update_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[
            NodeUpdate(
                node_id=notify_node_id,
                label="Email the team",
                subject="A new project was created",
            )
        ],
        thought="chain: rename and retitle the node just created",
    )
    assert update_result["updated_nodes"] == [
        {"node_id": notify_node_id, "label": "Email the team"}
    ], (
        f"update_nodes returned {update_result} for the node id add_nodes "
        f"reported ({notify_node_id}); the create → update handoff is broken."
    )

    # --- read the workflow back -------------------------------------------

    nodes = _read_back(
        list_nodes,
        ctx=ctx,
        workflow_id=workflow_id,
        thought="chain: verify the workflow",
    )["nodes"]
    assert [node["id"] for node in nodes] == [
        trigger_id,
        log_node_id,
        notify_node_id,
    ], (
        f"list_nodes returned {[n['id'] for n in nodes]}; the chain built "
        f"trigger {trigger_id} → create_row {log_node_id} → smtp_email "
        f"{notify_node_id}. list_nodes walks the workflow graph, so a change to "
        f"the graph's edge storage reorders or truncates it."
    )
    assert nodes[2]["label"] == "Email the team", (
        f"the node reads back labelled {nodes[2]['label']!r} after update_nodes "
        f"set 'Email the team'."
    )

    workflows = _read_back(
        list_workflows,
        ctx=ctx,
        automation_id=automation_id,
        thought="chain: verify the workflow list",
    )["workflows"]
    assert workflows == [
        {"id": workflow_id, "name": "On new project", "state": "draft"}
    ], (
        f"list_workflows returned {workflows} for the automation "
        f"create_builders returned; create_workflows reported id {workflow_id}."
    )

    # --- final database state ---------------------------------------------

    log_service = AutomationNode.objects.get(id=log_node_id).service.specific
    assert log_service.table_id == seed.table_id, (
        f"the create_row node is stored against table {log_service.table_id}, "
        f"not the table id create_tables returned ({seed.table_id})."
    )
    notify_service = AutomationNode.objects.get(id=notify_node_id).service.specific
    assert "A new project was created" in str(notify_service.subject), (
        f"update_nodes did not persist the new subject (stored: "
        f"{notify_service.subject!r})."
    )


@pytest.mark.django_db(transaction=True)
def test_add_nodes_persists_literal_field_values_like_create_workflows(data_fixture):
    """Both node-creation paths must store the literal values they were given."""

    seed = _seed_table(data_fixture)
    ctx = seed.ctx
    automation_id = create_builders(
        ctx,
        builders=[BuilderItemCreate(name="Parity", type="automation")],
        thought="chain: compare the two node creation paths",
    )["created_builders"][0]["id"]

    def create_row_node(
        ref: str, previous_node_ref: str, value: str
    ) -> ActionNodeCreate:
        return ActionNodeCreate(
            ref=ref,
            label=ref,
            type="create_row",
            previous_node_ref=previous_node_ref,
            table_id=seed.table_id,
            values=[AutomationFieldValue(field_id=seed.name_field_id, value=value)],
        )

    workflow_id = create_workflows(
        ctx,
        automation_id=automation_id,
        workflows=[
            WorkflowCreate(
                name="Parity",
                trigger=TriggerNodeCreate(
                    ref="trigger",
                    label="Project created",
                    type="rows_created",
                    rows_triggers_settings=RowsTriggersSettings(table_id=seed.table_id),
                ),
                nodes=[create_row_node("inline", "trigger", "from create_workflows")],
            )
        ],
        thought="chain: node created together with the workflow",
    )["created_workflows"][0]["id"]

    inline_node_id = _read_back(
        list_nodes, ctx=ctx, workflow_id=workflow_id, thought="chain: find the node"
    )["nodes"][1]["id"]
    appended_node_id = add_nodes(
        ctx,
        workflow_id=workflow_id,
        nodes=[create_row_node("appended", str(inline_node_id), "from add_nodes")],
        thought="chain: same node appended to the same workflow",
    )["created_nodes"][0]["id"]

    def mapped_field_ids(node_id: int) -> set[int]:
        service = AutomationNode.objects.get(id=node_id).service.specific
        return {mapping.field_id for mapping in service.field_mappings.all()}

    assert mapped_field_ids(inline_node_id) == {seed.name_field_id}, (
        f"create_workflows did not store the literal field value it was given "
        f"for field {seed.name_field_id}."
    )
    assert mapped_field_ids(appended_node_id) == {seed.name_field_id}, (
        f"add_nodes stored no field mapping for field {seed.name_field_id}, "
        f"while create_workflows stored one for the identical node. The node the "
        f"assistant appends to an existing workflow will create empty rows."
    )
