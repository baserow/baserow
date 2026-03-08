"""
Builder assistant tool functions.

All tools use the ``RunContext[AssistantDeps]`` + ``FunctionToolset`` pattern.
Page-scoped ref tracking helpers are defined at the top of this module.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.contrib.builder.pages.handler import PageHandler
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.core.types import (
    THEME_CATALOG,
    ThemeName,
    apply_theme,
)
from baserow_enterprise.assistant.types import BuilderPageNavigationType

from . import agents, helpers
from .types import (
    ActionCreate,
    CollectionElementCreate,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementItemCreate,
    ElementMove,
    ElementUpdate,
    FormElementCreate,
    LayoutElementCreate,
    PageCreate,
    PageItem,
    PageUpdate,
)

# ---------------------------------------------------------------------------
# Page-scoped ref tracking
# ---------------------------------------------------------------------------


def _get_page_context(tool_helpers, page_id: int) -> dict:
    """Get or create the ref-tracking context dict for a page."""
    key = f"builder_page_{page_id}"
    if key not in tool_helpers.request_context:
        tool_helpers.request_context[key] = {
            "element_refs": {},
            "data_source_refs": {},
        }
    return tool_helpers.request_context[key]


def _track_element_refs(tool_helpers, page_id: int, refs: dict[str, int]) -> None:
    _get_page_context(tool_helpers, page_id)["element_refs"].update(refs)


def _get_element_refs(tool_helpers, page_id: int) -> dict[str, int]:
    return _get_page_context(tool_helpers, page_id)["element_refs"].copy()


def _track_data_source_refs(tool_helpers, page_id: int, refs: dict[str, int]) -> None:
    _get_page_context(tool_helpers, page_id)["data_source_refs"].update(refs)


def _get_data_source_refs(tool_helpers, page_id: int) -> dict[str, int]:
    return _get_page_context(tool_helpers, page_id)["data_source_refs"].copy()


# ---------------------------------------------------------------------------
# Page tools
# ---------------------------------------------------------------------------


def list_pages(
    ctx: RunContext[AssistantDeps],
    application_id: Annotated[int, Field(description="The builder application ID.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List all pages in an application builder.

    WHEN to use: Check existing pages, find page IDs, or verify page names before creating new ones.
    WHAT it does: Lists all non-shared pages with their id, name, path, and parameters.
    RETURNS: Pages array with id, name, path, path_params, query_params, visibility.
    DO NOT USE when: You already have the page IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    builder = helpers.get_builder(user, workspace, application_id)
    tool_helpers.update_status(
        _("Listing pages in %(app_name)s...") % {"app_name": builder.name}
    )

    pages = helpers.list_pages(builder)
    return {"pages": [p.model_dump() for p in pages]}


def create_pages(
    ctx: RunContext[AssistantDeps],
    application_id: Annotated[int, Field(description="The builder application ID.")],
    pages: Annotated[list[PageCreate], Field(description="Pages to create.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create pages in an application builder.

    WHEN to use: User wants new pages in a builder app.
    WHAT it does: Creates pages with paths and parameters. Skips duplicates by name.
    RETURNS: Created pages with id, name, path.
    DO NOT USE when: Pages with those names already exist — check with list_pages first.

    ## Page Setup
    - Each page needs a unique name and path.
    - Use path parameters like :id for dynamic routes (e.g., '/products/:id').
    - Path params must be defined in path_params array with name and type.

    ## Navigation
    After creating pages, add navigation links (menu items, link elements) so users can reach them.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not pages:
        return {"created_pages": []}

    builder = helpers.get_builder(user, workspace, application_id)

    # Skip duplicates
    existing = {p.name.lower(): p for p in helpers.list_pages(builder)}
    created_pages: list[PageItem] = []
    skipped_pages: list[PageItem] = []

    with transaction.atomic():
        for page_create in pages:
            tool_helpers.raise_if_cancelled()
            ex = existing.get(page_create.name.lower())
            if ex:
                skipped_pages.append(ex)
                continue
            tool_helpers.update_status(
                _("Creating page %(name)s...") % {"name": page_create.name}
            )
            page = helpers.create_page(user, builder, page_create)
            created_pages.append(PageItem.from_orm(page))

    if created_pages:
        last = created_pages[-1]
        tool_helpers.navigate_to(
            BuilderPageNavigationType(
                type="builder-page",
                application_id=application_id,
                page_id=last.id,
                page_name=last.name,
            )
        )

    result: dict[str, Any] = {
        "created_pages": [p.model_dump() for p in created_pages],
    }
    if skipped_pages:
        result["existing_pages"] = [p.model_dump() for p in skipped_pages]
    if created_pages:
        result["next_steps"] = (
            "Pages created. Next: create data sources (create_data_sources), "
            "then elements (create_display_elements, create_layout_elements, "
            "create_form_elements, create_collection_elements), "
            "then actions for buttons/forms (create_actions)."
        )
    return result


# ---------------------------------------------------------------------------
# Page update tool
# ---------------------------------------------------------------------------


def update_page(
    ctx: RunContext[AssistantDeps],
    page: Annotated[PageUpdate, Field(description="Page update data.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update an existing page's properties.

    WHEN to use: User wants to rename a page, change its path, or modify parameters.
    WHAT it does: Updates the specified fields on a page. Only non-null fields are applied.
    RETURNS: Updated page with id, name, path.
    DO NOT USE when: You need to create a new page — use create_pages instead.

    ## Usage
    - page_id: ID of the page to update (from list_pages).
    - Only set the fields you want to change.
    - When changing path, also update path_params if the new path has different parameters.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    tool_helpers.update_status(_("Updating page %(id)d...") % {"id": page.page_id})

    updated_page = helpers.update_page(user, page)
    page_item = PageItem.from_orm(updated_page)

    return {
        "status": "ok",
        "page": page_item.model_dump(),
        "updated_fields": page.get_updated_field_names(),
    }


# ---------------------------------------------------------------------------
# Data source tools
# ---------------------------------------------------------------------------


def list_data_sources(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List all data sources on a page.

    WHEN to use: Check existing data sources or find data source IDs.
    WHAT it does: Lists data sources with id, name, type, table_id.
    RETURNS: Data sources array.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Listing data sources on %(name)s...") % {"name": page.name}
    )

    ds_list = helpers.list_data_sources(page)
    return {"data_sources": [ds.model_dump() for ds in ds_list]}


def create_data_sources(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    data_sources: Annotated[
        list[DataSourceCreate], Field(description="Data sources to create.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create data sources to connect page elements to database tables.

    WHEN to use: Page needs data from database tables for display or forms.
    WHAT it does: Creates list_rows or get_row data sources. Skips duplicates by name.
    RETURNS: Created data sources with ref-to-ID mapping.
    DO NOT USE when: Data sources with those names already exist on the page.

    ## Data Source Types
    - list_rows: Fetches multiple rows (for tables, repeaters, dropdowns).
    - get_row: Fetches a single row by ID (for detail pages).

    ## Dynamic Values with $formula:
    - get_row row_id: "$formula: the id from the page parameter"
    - list_rows search_query: "$formula: the text from the search input"
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    if not data_sources:
        return {"created_data_sources": [], "ref_to_id_map": {}}

    page = helpers.get_page(user, page_id)
    integration = helpers.get_local_baserow_integration(page.builder)

    existing = {ds.name.lower(): ds for ds in helpers.list_data_sources(page)}
    ref_to_id: dict[str, int] = {}
    created: list[dict] = []
    ds_pairs: list[tuple] = []

    with transaction.atomic():
        for ds_create in data_sources:
            tool_helpers.raise_if_cancelled()
            ex = existing.get(ds_create.name.lower())
            if ex:
                ref_to_id[ds_create.ref] = ex.id
                continue

            tool_helpers.update_status(
                _("Creating data source '%(name)s'...") % {"name": ds_create.name}
            )
            orm_ds, ds_id = helpers.create_data_source(
                user, page, ds_create, integration
            )
            ref_to_id[ds_create.ref] = ds_id
            ds_pairs.append((orm_ds, ds_create))
            created.append(
                {
                    "id": ds_id,
                    "ref": ds_create.ref,
                    "name": ds_create.name,
                    "type": ds_create.type,
                }
            )

    # Formula generation (separate transactions)
    agents.update_data_source_formulas(user, page, ds_pairs, tool_helpers)

    _track_data_source_refs(tool_helpers, page_id, ref_to_id)

    return {"created_data_sources": created, "ref_to_id_map": ref_to_id}


# ---------------------------------------------------------------------------
# Data source update tool
# ---------------------------------------------------------------------------


def update_data_source(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[
        int, Field(description="The page ID the data source belongs to.")
    ],
    data_source: Annotated[
        DataSourceUpdate, Field(description="Data source update data.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update an existing data source's properties.

    WHEN to use: User wants to change a data source's name, table, row_id, or search_query.
    WHAT it does: Updates the specified fields on a data source. Only non-null fields are applied.
    RETURNS: Updated data source ID and list of changed fields.
    DO NOT USE when: You need to create a new data source — use create_data_sources instead.

    ## Usage
    - data_source_id: ID of the data source to update (from list_data_sources).
    - Only set the fields you want to change.

    ## Dynamic Values with $formula:
    - row_id: "$formula: the id from the page parameter"
    - search_query: "$formula: the text from the search input"
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Updating data source %(id)d...") % {"id": data_source.data_source_id}
    )

    with transaction.atomic():
        orm_ds, ds_type = helpers.update_data_source(user, data_source, workspace)

    # Handle formula generation for $formula: fields (separate transaction)
    formulas = data_source.get_formulas_to_update(orm_ds, None)
    if formulas:
        agents.update_single_data_source_formulas(
            user, page, orm_ds, data_source, tool_helpers
        )

    updated_fields = data_source.get_updated_field_names()
    return {
        "status": "ok",
        "data_source_id": data_source.data_source_id,
        "service_type": ds_type,
        "updated_fields": updated_fields,
    }


# ---------------------------------------------------------------------------
# Element tools
# ---------------------------------------------------------------------------


def list_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List all elements on a page.

    WHEN to use: Check existing elements, find element IDs or container structure.
    WHAT it does: Lists elements with id, type, order, parent_element_id, is_container.
    RETURNS: Elements array.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Listing elements on %(name)s...") % {"name": page.name}
    )

    elements = helpers.list_elements(page)
    return {"elements": [el.model_dump() for el in elements]}


def _create_elements_internal(
    ctx: RunContext[AssistantDeps],
    page_id: int,
    elements: list[ElementItemCreate],
    before_element_id: int | None = None,
) -> dict[str, Any]:
    """Shared implementation for all create_*_elements tools."""

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    if not elements:
        return {"created_elements": [], "ref_to_id_map": {}}

    page = helpers.get_page(user, page_id)
    shared_page = PageHandler().get_shared_page(page.builder)

    tool_helpers.update_status(
        _("Creating %(count)d elements on %(name)s...")
        % {"count": len(elements), "name": page.name}
    )

    ref_to_id: dict[str, int] = _get_element_refs(tool_helpers, page_id)
    element_mapping: dict[str, tuple[Any, ElementItemCreate]] = {}
    ds_ref_to_id = _get_data_source_refs(tool_helpers, page_id)
    shared_page_refs: set[str] = set(
        _get_element_refs(tool_helpers, shared_page.id).keys()
    )
    created: list[dict] = []

    errors: list[str] = []
    with transaction.atomic():
        for el_create in elements:
            tool_helpers.raise_if_cancelled()
            try:
                element, el_id = helpers.create_element(
                    user,
                    page,
                    el_create,
                    ref_to_id,
                    ds_ref_to_id,
                    shared_page_refs,
                    before_element_id,
                )
            except (ValueError, Exception) as exc:
                errors.append(f"{el_create.ref}: {exc}")
                continue
            ref_to_id[el_create.ref] = el_id
            element_mapping[el_create.ref] = (element, el_create)
            created.append({"id": el_id, "ref": el_create.ref, "type": el_create.type})

    # Formula generation (separate transactions)
    agents.update_element_formulas(user, page, elements, element_mapping, tool_helpers)

    # Handle table button action formulas
    table_action_pairs = []
    for el_create in elements:
        if el_create.type == "table":
            table_action_pairs.extend(el_create._created_action_pairs)
    if table_action_pairs:
        agents.update_workflow_action_formulas(
            user, page, table_action_pairs, tool_helpers
        )

    _track_element_refs(tool_helpers, page_id, ref_to_id)
    _track_element_refs(
        tool_helpers,
        shared_page.id,
        {r: 0 for r in ref_to_id if r in shared_page_refs},
    )

    result: dict[str, Any] = {"created_elements": created, "ref_to_id_map": ref_to_id}

    if errors:
        result["errors"] = errors

    # Guide the model to create workflow actions for interactive elements
    actionable = [
        el.ref for el in elements if el.type in ("button", "link", "form_container")
    ]
    if actionable:
        result["next_steps"] = (
            f"Elements {actionable} need workflow actions. "
            "Call create_actions next: 'click' event for buttons/links, "
            "'submit' event for form_container."
        )

    return result


def create_display_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    elements: Annotated[
        list[DisplayElementCreate], Field(description="Display elements to create.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(default=None, description="Insert before this element ID."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create display elements on a page: heading, text, button, link, image.

    WHEN to use: User wants to add text content, headings, buttons, links, or images.
    WHAT it does: Creates display elements with formula support for dynamic values.
    RETURNS: Created elements with ref-to-ID mapping.

    ## Element Structure
    - parent_element: int ID (existing container) or string ref (same batch)
    - place_in_container: 0-indexed column position for column elements

    ## Dynamic Values with $formula:
    - Heading/text value: "$formula: the product name from the products data source"
    - Image URL: "$formula: the image URL from the product data source"
    - Static text: use plain strings (auto-wrapped in quotes)

    ## After Creating Buttons/Links
    Buttons/links need a click action (open_page, notification, etc.) via create_actions.
    ALWAYS call create_actions after creating buttons or links.
    """

    internal = [el.to_element_item_create() for el in elements]
    return _create_elements_internal(ctx, page_id, internal, before_element_id)


def create_layout_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    elements: Annotated[
        list[LayoutElementCreate], Field(description="Layout elements to create.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(default=None, description="Insert before this element ID."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create layout/navigation elements on a page: column, simple_container, header, footer, menu.

    WHEN to use: User wants page structure — columns, containers, headers, footers, menus.
    WHAT it does: Creates container elements that hold child elements.
    RETURNS: Created elements with ref-to-ID mapping.

    ## Element Structure
    - Layout elements are containers — add children via parent_element ref.
    - column: creates N columns, children use place_in_container "0", "1", etc.
    - header/footer: shared across pages by default.
    - menu: add menu_items to link to pages.
    """

    internal = [el.to_element_item_create() for el in elements]
    return _create_elements_internal(ctx, page_id, internal, before_element_id)


def create_form_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    elements: Annotated[
        list[FormElementCreate], Field(description="Form elements to create.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(default=None, description="Insert before this element ID."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create form elements on a page: form_container, input_text, choice, checkbox, datetime_picker, record_selector.

    WHEN to use: User wants a form to collect input data.
    WHAT it does: Creates form containers and input elements with validation.
    RETURNS: Created elements with ref-to-ID mapping.

    ## Form Structure
    - Create a form_container first, then add inputs inside it via parent_element.
    - Each input has label, placeholder, required, default_value.
    - input_text: validation_type (any, email, integer), is_multiline.
    - choice: choice_options, multiple.
    - record_selector: needs data_source.

    ## Edit Forms
    For update_row forms, set default_value="get('current_record.field_<id>')" on each input to pre-fill with existing data.

    ## After Creating Forms
    Form containers need a submit action (create_row, update_row) via create_actions.
    ALWAYS call create_actions after creating form_container elements.
    """

    internal = [el.to_element_item_create() for el in elements]
    return _create_elements_internal(ctx, page_id, internal, before_element_id)


def create_collection_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    elements: Annotated[
        list[CollectionElementCreate],
        Field(description="Collection elements to create."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(default=None, description="Insert before this element ID."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create collection elements on a page: table, repeat.

    WHEN to use: User wants to display data from a data source in a table or repeating layout.
    WHAT it does: Creates collection elements connected to data sources.
    RETURNS: Created elements with ref-to-ID mapping.

    ## Prerequisites
    Create data sources first (create_data_sources), then reference them here.

    ## Table
    - data_source: the data source ID or ref.
    - fields: column configurations (name, type, value). If omitted, auto-generated from data source.

    ## Repeat
    - data_source: the data source ID or ref.
    - orientation: "vertical" or "horizontal".
    - Add child elements inside the repeat via parent_element ref.
    """

    internal = [el.to_element_item_create() for el in elements]
    return _create_elements_internal(ctx, page_id, internal, before_element_id)


# ---------------------------------------------------------------------------
# Element update tool
# ---------------------------------------------------------------------------


def update_element(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID the element belongs to.")],
    element: Annotated[ElementUpdate, Field(description="Element update data.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update an existing element's properties.

    WHEN to use: User wants to change properties of an existing element (text, label, settings, etc.).
    WHAT it does: Updates the specified fields on an element. Only non-null fields are applied.
    RETURNS: Updated element ID and list of changed fields.
    DO NOT USE when: You need to move elements, change data sources, or modify styles — use other tools for those.

    ## Usage
    - element_id: ID of the element to update (from list_elements).
    - Only set the fields you want to change — unset fields are left unchanged.
    - Invalid fields for the element type are silently ignored.

    ## Dynamic Values with $formula:
    - value: "$formula: the product name from the data source"
    - default_value: "$formula: the current user's email"
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Updating element %(id)d...") % {"id": element.element_id}
    )

    with transaction.atomic():
        orm_element, element_type = helpers.update_element(user, element)

    # Handle formula generation for $formula: fields (separate transaction)
    formulas = element.get_formulas_to_update(orm_element, None, element_type)
    if formulas:
        agents.update_single_element_formulas(
            user, page, orm_element, element, element_type, tool_helpers
        )

    updated_fields = element.get_updated_field_names()
    return {
        "status": "ok",
        "element_id": element.element_id,
        "element_type": element_type,
        "updated_fields": updated_fields,
    }


# ---------------------------------------------------------------------------
# Element move tool
# ---------------------------------------------------------------------------


def move_elements(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    moves: Annotated[
        list[ElementMove], Field(description="Move operations to perform.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Move or reorder elements on a page.

    WHEN to use: User wants to reorder elements, move elements into/out of containers, or rearrange page layout.
    WHAT it does: Moves each element to a new position, parent, or container slot.
    RETURNS: List of moved elements with their new positions.
    DO NOT USE when: You need to create new elements — use create_*_elements instead.

    ## Parameters per move
    - element_id: ID of the element to move (from list_elements).
    - before_id: Place before this element. null = move to end.
    - parent_element_id: New parent container. null = move to root level.
    - place_in_container: Container slot (e.g. "0", "1" for columns). null = default.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    if not moves:
        return {"moved_elements": []}

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Moving %(count)d elements on %(name)s...")
        % {"count": len(moves), "name": page.name}
    )

    moved: list[dict] = []
    errors: list[str] = []

    for element_move in moves:
        tool_helpers.raise_if_cancelled()
        try:
            with transaction.atomic():
                element = helpers.move_element(user, element_move)
            moved.append(
                {
                    "element_id": element.id,
                    "parent_element_id": element.parent_element_id,
                    "place_in_container": element.place_in_container,
                    "order": str(element.order),
                }
            )
        except Exception as exc:
            errors.append(f"element {element_move.element_id}: {exc}")

    result: dict[str, Any] = {"moved_elements": moved}
    if errors:
        result["errors"] = errors
    return result


# ---------------------------------------------------------------------------
# Workflow action tools
# ---------------------------------------------------------------------------


def list_actions(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List all workflow actions on a page.

    WHEN to use: Check existing actions, find action IDs, or review field mappings.
    WHAT it does: Lists actions with id, type, element_id, event, field_mappings.
    RETURNS: Workflow actions array.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, page_id)
    tool_helpers.update_status(
        _("Listing actions on %(name)s...") % {"name": page.name}
    )

    actions = helpers.list_workflow_actions(page)
    return {"workflow_actions": [a.model_dump() for a in actions]}


def create_actions(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    actions: Annotated[
        list[ActionCreate], Field(description="Workflow actions to create.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create workflow actions attached to elements (click, submit events).

    WHEN to use: User wants buttons/forms to perform actions (navigate, create/update rows, show notifications).
    WHAT it does: Creates workflow actions with formula support for dynamic values.
    RETURNS: Created actions with id, type, element_ref, event.

    ## Attaching Actions
    - element_ref: attach to newly created element (auto-tracked)
    - element_id: attach to existing element (from list_elements)
    - event: "click" for buttons/links, "submit" for form containers

    ## Action Types
    - notification: Show a message (title/description are formulas)
    - open_page: Navigate to another page (set navigate_to_page_id)
    - create_row: Insert a row (needs table_id and field_values)
    - update_row: Update a row (needs table_id, row_id, field_values)
    - delete_row: Delete a row (needs table_id and row_id)
    - refresh_data_source: Reload a data source
    - logout: Log out the user

    ## Dynamic Values with $formula:
    - field_values: {"field_id": "123", "value": "$formula: the name from the Name input"}
    - row_id: "$formula: the id from the page parameter"
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    if not actions:
        return {"created_actions": []}

    page = helpers.get_page(user, page_id)
    integration = helpers.get_local_baserow_integration(page.builder)

    el_refs = _get_element_refs(tool_helpers, page_id)
    ds_refs = _get_data_source_refs(tool_helpers, page_id)
    created: list[dict] = []
    action_pairs: list[tuple] = []

    errors: list[str] = []
    with transaction.atomic():
        for action_create in actions:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(
                _("Creating %(type)s action...") % {"type": action_create.type}
            )
            try:
                orm_action, action_id = helpers.create_workflow_action(
                    user, page, action_create, el_refs, ds_refs, integration
                )
            except (ValueError, Exception) as exc:
                errors.append(f"{action_create.type} on {action_create.element}: {exc}")
                continue
            action_pairs.append((orm_action, action_create))
            created.append(
                {
                    "id": action_id,
                    "type": action_create.type,
                    "element": action_create.element,
                    "event": action_create.event,
                }
            )

    # Formula generation (separate transactions)
    agents.update_workflow_action_formulas(user, page, action_pairs, tool_helpers)

    result: dict[str, Any] = {"created_actions": created}
    if errors:
        result["errors"] = errors
    return result


def add_action_field_mapping(
    ctx: RunContext[AssistantDeps],
    action_id: Annotated[int, Field(description="The workflow action ID.")],
    field_id: Annotated[int, Field(description="The target table field ID.")],
    value_formula: Annotated[
        str,
        Field(
            description="Formula for the value, e.g. get('form_data.123') or get('page_parameter.id')."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add or update a field mapping on an existing create_row/update_row action.

    WHEN to use: Adding a new form input to an existing form that already has a row action.
    WHAT it does: Maps a table field to a formula value without recreating the action.
    RETURNS: Updated field mappings list.
    """

    tool_helpers = ctx.deps.tool_helpers
    tool_helpers.update_status(
        _("Adding field mapping to action %(id)d...") % {"id": action_id}
    )

    return helpers.add_field_mapping_to_action(action_id, field_id, value_formula)


# ---------------------------------------------------------------------------
# Theme tools
# ---------------------------------------------------------------------------


def set_theme(
    ctx: RunContext[AssistantDeps],
    application_id: Annotated[int, Field(description="The builder application ID.")],
    theme_name: Annotated[ThemeName, Field(description="Theme name to apply.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Change the theme of a builder application.

    WHEN to use: User wants to change the look and feel of an existing application.
    WHAT it does: Applies a predefined theme (colors, typography, button styles, etc.) to the application.
    RETURNS: Confirmation with applied theme name.
    DO NOT USE when: Creating a new application — use the theme parameter on create_builders instead.

    ## Available Themes
    {theme_list}
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    builder = helpers.get_builder(user, workspace, application_id)
    tool_helpers.update_status(
        _("Applying %(theme)s theme to %(app)s...")
        % {"theme": theme_name, "app": builder.name}
    )

    apply_theme(builder, theme_name, user=user)

    return {
        "status": "ok",
        "application_id": application_id,
        "theme": theme_name,
        "description": THEME_CATALOG.get(theme_name, ""),
    }


set_theme.__doc__ = set_theme.__doc__.format(
    theme_list="\n    ".join(
        f"- {name}: {desc}" for name, desc in THEME_CATALOG.items()
    )
)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = [
    list_pages,
    create_pages,
    update_page,
    list_data_sources,
    create_data_sources,
    update_data_source,
    list_elements,
    create_display_elements,
    create_layout_elements,
    create_form_elements,
    create_collection_elements,
    update_element,
    move_elements,
    list_actions,
    create_actions,
    add_action_field_mapping,
    set_theme,
]
builder_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
