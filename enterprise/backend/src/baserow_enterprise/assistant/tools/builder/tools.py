"""
Builder assistant tool functions.

All tools use the ``RunContext[AssistantDeps]`` + ``FunctionToolset`` pattern.
Page-scoped ref tracking helpers are defined at the top of this module.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.tools import BuilderWriteOptions, helpers
from baserow.contrib.builder.tools import actions as shared_actions
from baserow.contrib.builder.tools import data_sources as shared_data_sources
from baserow.contrib.builder.tools import elements as shared_elements
from baserow.contrib.builder.tools import pages as shared_pages
from baserow.contrib.builder.tools import themes as shared_themes
from baserow.contrib.builder.tools.errors import (
    UnknownRefError,
    is_input_error,
    user_error_message,
)
from baserow.contrib.builder.tools.formulas import BuilderFormulaError
from baserow.contrib.builder.tools.lookups import get_builder_in_workspace
from baserow.contrib.builder.tools.registries import element_tool_type_registry
from baserow.contrib.builder.tools.themes import THEME_CATALOG, ThemeName
from baserow.contrib.builder.tools.types import (
    ActionChanges,
    ActionCreate,
    ActionItem,
    CollectionElementCreate,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayElementCreate,
    ElementItemCreate,
    ElementMove,
    ElementStyleChanges,
    ElementStyleUpdate,
    ElementUpdate,
    FormElementCreate,
    LayoutElementCreate,
    PageCreate,
    PageUpdate,
)
from baserow.contrib.builder.tools.types.changes import name_key
from baserow.contrib.builder.tools.types.table_columns import data_source_fields
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.formula.literals import FORMULA_PREFIX
from baserow.core.tools.errors import validation_messages
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    permission_denied_result,
    raise_if_permission_denied,
    require_payload,
)
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset
from baserow_enterprise.assistant.types import BuilderPageNavigationType
from baserow_enterprise.builder.tools import user_sources as shared_user_sources
from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup

from . import agents

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


def _not_on_page(page, element_ids) -> list[int]:
    """The IDs of ``element_ids`` that this page's tools can't reach."""

    reachable = set(
        Element.objects.filter(helpers.on_page(page), id__in=element_ids).values_list(
            "id", flat=True
        )
    )
    return [element_id for element_id in element_ids if element_id not in reachable]


def _named_field_beats_description(element: ElementItemCreate) -> None:
    """
    A new table column named like a field of its data source shows that field when
    its value is only a ``$formula:`` description: the model often describes the
    field it means. An explicit formula still wins.
    """

    if element.type != "table" or not element.fields:
        return
    table_fields = data_source_fields(element.data_source)
    for column in element.fields:
        if (
            column.type == "text"
            and column.value
            and column.value.strip().lower().startswith(FORMULA_PREFIX)
            and name_key(column.name) in table_fields
        ):
            column.value = None


def _get_builder(ctx: RunContext[AssistantDeps], application_id: int) -> Builder:
    """
    The application builder ``application_id`` of the workspace, through the getter
    MCP uses, so both answer alike: one the user can't see is not found.
    """

    try:
        return get_builder_in_workspace(ctx.deps.tool_context(), application_id)
    except ApplicationDoesNotExist:
        raise ToolInputError(
            f"Application with ID {application_id} not found in this workspace. "
            "Use list_builders to find valid application IDs."
        )


def _page_not_found(page_id: int) -> ToolInputError:
    return ToolInputError(
        f"Page with ID {page_id} not found or not accessible. "
        "Use list_pages to find valid page IDs."
    )


def item_error(exc: Exception) -> str:
    """
    The message Kuma gets for one item of a batch that failed with ``exc``. Kuma
    keeps refs across calls, so an unknown ref gets the message for that.
    """

    if isinstance(exc, UnknownRefError):
        return exc.message_with_known_refs
    if isinstance(exc, DRFValidationError):
        return validation_messages(exc)
    return user_error_message(exc) or str(exc)


def _input_item_error(exc: Exception) -> str:
    """
    The message for an item of a batch whose input is at fault. Anything else is a
    bug, which stops the call and undoes the batch.
    """

    if not is_input_error(exc):
        raise exc
    return item_error(exc)


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
    WHAT it does: Lists all non-shared pages with their id, name, path, parameters, and visibility.
    RETURNS: Pages, login_page_id, user_sources with table info, and available_roles.
    DO NOT USE when: You already have the page IDs you need.
    """

    try:
        result = shared_pages.list_pages(ctx.deps.tool_context(), application_id)
    except ApplicationDoesNotExist:
        raise ToolInputError(
            f"Application with ID {application_id} not found in this workspace. "
            "Use list_builders to find valid application IDs."
        )
    return {
        **result,
        "next_steps": (
            "For a requested new page, use create_pages with this application_id "
            "first, then use its returned page ID in setup_page or element tools. "
            "An application ID is not a page ID. Do not replace a different existing "
            "page when the user asked for a new one. If a new presentation page's "
            "CTA has no specified destination and a Home page is listed, link the "
            "CTA to that page and state this assumption instead of blocking the "
            "build with a question. Do not modify that destination page. "
            "For pages displaying records, "
            "find the matching table before creating the page; if the records are "
            "missing, ask where they should come from first."
        ),
    }


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
    REQUIRED: `application_id` and `pages` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Page Setup
    - Each page needs a unique name and path.
    - Use path parameters like :id for dynamic routes (e.g., '/products/:id').
    - Path params must be defined in path_params array with name and type.

    ## Navigation
    After creating pages, add navigation links (menu items, link elements) so users can reach them.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_pages", "pages", pages)

    builder = _get_builder(ctx, application_id)

    # Skip duplicates
    existing = {p.name.lower(): p for p in helpers.list_pages(user, builder)}
    new_pages = [p for p in pages if p.name.lower() not in existing]
    helpers.ensure_distinct_paths(new_pages)
    skipped_pages = [
        existing[p.name.lower()] for p in pages if p.name.lower() in existing
    ]

    created = shared_pages.create_pages_with_options(
        ctx.deps.tool_context(),
        application_id,
        new_pages,
        BuilderWriteOptions(item_error=_input_item_error),
    )
    created_pages = created["created_pages"]
    errors = created.get("errors", [])

    if created_pages:
        last = created_pages[-1]
        tool_helpers.navigate_to(
            BuilderPageNavigationType(
                type="builder-page",
                application_id=application_id,
                page_id=last["id"],
                page_name=last["name"],
            )
        )

    result: dict[str, Any] = {"created_pages": created_pages}
    if skipped_pages:
        result["existing_pages"] = [p.model_dump() for p in skipped_pages]
    if errors:
        result["errors"] = errors
    if created_pages:
        result["next_steps"] = (
            "Pages created. Add the requested content now. Draft sensible headings, "
            "descriptions, and button labels rather than asking for this copy. "
            "If the request names an internal navigation destination that is "
            "missing, create that supporting page too and link to its returned ID. "
            "Add data sources only for content backed by existing records "
            "(create_data_sources). Then add elements "
            "(create_display_elements, create_layout_elements, "
            "create_form_elements, create_collection_elements), "
            "then actions for buttons/forms (create_element_actions)."
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

    try:
        result = shared_pages.update_page(ctx.deps.tool_context(), page.page_id, page)
    except PageDoesNotExist:
        raise _page_not_found(page.page_id)

    response = {
        "status": "ok",
        "page": result["updated_page"],
        "updated_fields": page.get_updated_field_names(),
    }
    if "navigations_to_fix" in result:
        response["navigations_to_fix"] = result["navigations_to_fix"]
    return response


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

    try:
        return shared_data_sources.list_data_sources(ctx.deps.tool_context(), page_id)
    except PageDoesNotExist:
        raise _page_not_found(page_id)


def _split_reused_data_sources(
    user, page, data_sources: list[DataSourceCreate]
) -> tuple[dict[str, int], list[DataSourceCreate]]:
    """
    Skip the data sources the page has, by name or structural match.

    :return: The IDs to use for the refs of those it has, and the others.
    """

    existing_ds = helpers.list_data_sources(user, page)
    existing_by_name = {ds.name.lower(): ds for ds in existing_ds}
    reused: dict[str, int] = {}
    new_data_sources: list[DataSourceCreate] = []
    for ds_create in data_sources:
        ex = existing_by_name.get(ds_create.name.lower())
        if not ex:
            ex = next(
                (ds for ds in existing_ds if ds_create.matches_existing(ds)), None
            )
        if ex:
            reused[ds_create.ref] = ex.id
        else:
            new_data_sources.append(ds_create)
    return reused, new_data_sources


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
    REQUIRED: `page_id` and `data_sources` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Data Source Types
    - list_rows: Fetches multiple rows — use when the page displays a collection (table, repeat, dropdown).
    - get_row: Fetches a single row by ID — use when the page works with one specific record. Set row_id with $formula: to get the ID dynamically (e.g. from a page parameter).

    ## Dynamic Values with $formula:
    - get_row row_id: "$formula: the id from the page parameter"
    - list_rows search_query: "$formula: the text from the search input"

    ## Filtering
    To filter a data source, create it first, then call update_service_filters
    with its id and the user's filter request. Only pass a view_id to reuse an
    existing database view the user asked for: its filters and sortings are
    applied automatically.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_data_sources", "data_sources", data_sources)

    page = helpers.get_page(user, ctx.deps.workspace, page_id)

    reused, new_data_sources = _split_reused_data_sources(user, page, data_sources)

    tool_context = ctx.deps.tool_context()
    created = shared_data_sources.create_data_sources_with_options(
        tool_context,
        page_id,
        new_data_sources,
        BuilderWriteOptions(defer_required_formulas=True, item_error=_input_item_error),
    )

    # Formula generation (separate transactions)
    errors = created.get("errors", [])
    errors.extend(
        _create_data_source_formula_error(entry)
        for entry in agents.repair_builder_formula_errors(
            tool_context, tool_helpers, page, created.get("formula_errors", [])
        )
    )

    ids = {**reused, **created["ref_to_id_map"]}
    ref_to_id = {ds.ref: ids[ds.ref] for ds in data_sources if ds.ref in ids}
    _track_data_source_refs(tool_helpers, page_id, ref_to_id)

    result: dict[str, Any] = {
        "created_data_sources": created["created_data_sources"],
        "ref_to_id_map": ref_to_id,
    }
    if errors:
        result["errors"] = errors
    return result


def _create_data_source_formula_error(entry: BuilderFormulaError) -> str:
    """How Kuma words a value the repair of a new data source couldn't fill."""

    name = entry.item.name
    if entry.permission_denied:
        return (
            f"Permission denied while configuring data source '{name}'. "
            "It was created, but its formulas were not applied. "
            "Do not retry the denied operation."
        )
    return f"Formula generation failed for data source '{name}': {entry['error']}"


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
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, ctx.deps.workspace, page_id)
    tool_helpers.update_status(
        _("Updating data source %(id)d...") % {"id": data_source.data_source_id}
    )

    tool_context = ctx.deps.tool_context()
    _orm_ds, ds_type, formula_errors = shared_data_sources.update_data_source_on_page(
        tool_context, page, data_source
    )

    # Handle formula generation for $formula: fields (separate transaction)
    remaining = agents.repair_builder_formula_errors(
        tool_context, tool_helpers, page, formula_errors
    )
    errors = _kept_value_errors(remaining)
    not_applied = {entry["field"] for entry in remaining}
    updated_fields = [
        field
        for field in data_source.get_updated_field_names()
        if field not in not_applied
    ]

    result: dict[str, Any] = {
        "status": "partial" if errors else "ok",
        "data_source_id": data_source.data_source_id,
        "service_type": ds_type,
        "updated_fields": updated_fields,
    }
    if errors:
        result["errors"] = errors
    return result


def _kept_value_errors(remaining: list[BuilderFormulaError]) -> list[str]:
    """
    How Kuma words values the repair of an updated item couldn't fill.

    :raises PermissionException: When the user may not write one of them.
    """

    fields_by_error: dict[str, list[str]] = {}
    for entry in remaining:
        if entry.permission_denied:
            raise PermissionException()
        fields_by_error.setdefault(entry["error"], []).append(entry["field"])
    return [
        _kept_value_error(error, fields) for error, fields in fields_by_error.items()
    ]


def _kept_value_error(error: str, fields: list[str]) -> str:
    names = ", ".join(sorted(fields))
    if error == agents.NO_VALID_FORMULA:
        return (
            f"No valid formula was generated for {names}. The previous value was kept."
        )
    return (
        f"Formula generation failed for {names}: {error}. The previous value was kept."
    )


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
    NOT LISTED: What a button does when clicked, like the message it shows or the page it opens. Use list_element_actions for that.
    WHAT it does: Lists elements with id, type, parent_element_id, is_container. Tables also show their data_source_id and table_columns in display order: uid, name, type, and value (text, boolean, rating) or label (button). value and label are formulas: fixed text is quoted, and '' or "''" is an empty cell. Menus show their items in order: uid, name, type, page_id (or url, for a link to a custom address), and a top-level link's sub-links as children.
    RETURNS: Elements array.

    Elements with page_name="[shared]" are headers/footers visible on ALL pages.
    Do not add page-specific children to them.
    """

    try:
        return shared_elements.list_elements(ctx.deps.tool_context(), page_id)
    except PageDoesNotExist:
        raise _page_not_found(page_id)


def _create_element_formula_errors(entries: list[BuilderFormulaError]) -> list[str]:
    """
    How Kuma words the values the repair of new elements couldn't fill: one error per
    item. A value the model left out isn't reported.
    """

    errors: list[str] = []
    reported: set[tuple[str, int]] = set()
    for entry in entries:
        item_key = (entry.kind, entry.source.id)
        if entry["error"] == agents.NO_VALID_FORMULA or item_key in reported:
            continue
        reported.add(item_key)
        errors.append(_new_item_formula_error(entry))
    return errors


def _new_item_formula_error(entry: BuilderFormulaError) -> str:
    item = entry.item
    if entry.kind == "element":
        if entry.permission_denied:
            return (
                f"Permission denied while configuring element '{item.ref}'. "
                "The element was created, but its formulas were not applied. "
                "Do not retry the denied operation."
            )
        return f"Formula generation failed for '{item.ref}': {entry['error']}"
    if entry.permission_denied:
        return (
            f"Permission denied while configuring action on '{item.element}'. "
            "The action was created, but its formulas were not applied. "
            "Do not retry the denied operation."
        )
    ref = (
        item.element
        if isinstance(item.element, str)
        else f"element_{entry.source.element_id}"
    )
    return f"Formula generation failed for action on '{ref}': {entry['error']}"


def _create_elements_internal(
    ctx: RunContext[AssistantDeps],
    page_id: int,
    elements: list[ElementItemCreate],
    before_element_id: int | None = None,
) -> dict[str, Any]:
    """Shared implementation for all create_*_elements tools."""

    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(ctx.deps.user, ctx.deps.workspace, page_id)
    shared_page = PageHandler().get_shared_page(page.builder)

    known_refs = _get_element_refs(tool_helpers, page_id)
    shared_page_refs: set[str] = set(
        _get_element_refs(tool_helpers, shared_page.id).keys()
    )

    tool_context = ctx.deps.tool_context()
    shared = shared_elements.create_elements_with_options(
        tool_context,
        page_id,
        elements,
        before_element_id,
        BuilderWriteOptions(
            known_refs=known_refs,
            known_data_source_refs=_get_data_source_refs(tool_helpers, page_id),
            known_shared_page_refs=shared_page_refs,
            prepare_element=_named_field_beats_description,
            item_error=item_error,
        ),
    )
    created = shared["created_elements"]
    ref_to_id = {**known_refs, **shared["ref_to_id_map"]}

    # Formula generation (separate transactions)
    errors = shared.get("errors", [])
    errors.extend(
        _create_element_formula_errors(
            agents.repair_builder_formula_errors(
                tool_context, tool_helpers, page, shared.get("formula_errors", [])
            )
        )
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

    empty_containers = shared.get("empty_containers")
    next_steps = []
    if empty_containers:
        result["empty_containers"] = empty_containers
        next_steps.append(
            "The empty_containers have no child elements. If the user requested "
            "content, add that requested content before finishing, using "
            "parent_element with the returned container ID or ref. Creating a "
            "container does not complete its requested content. Inside a repeat, "
            "use current_record for each row's dynamic values. Do not add "
            "unrequested content or invent missing data."
        )

    # Guide the model to create workflow actions for interactive elements.
    created_refs = {item["ref"] for item in created}
    actionable = [
        el.ref
        for el in elements
        if el.ref in created_refs and el.type in ("button", "form_container")
    ]
    if actionable:
        next_steps.append(
            f"Elements {actionable} need workflow actions. "
            "Call create_element_actions next: 'click' event for buttons, "
            "'submit' event for form_container."
        )
    if next_steps:
        result["next_steps"] = " ".join(next_steps)

    # Navigate to the page containing the created elements
    if created:
        tool_helpers.navigate_to(
            BuilderPageNavigationType(
                type="builder-page",
                application_id=page.builder_id,
                page_id=page_id,
                page_name=page.name,
            )
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

    For navigation, use a link (link_variant='button' gives a button appearance),
    or create a button and then create_element_actions(type='open_page', event='click').
    Button elements do not accept navigation properties.

    PREREQUISITE: The page must already exist. Call create_pages first if it doesn't.
    WHEN to use: User wants to add text content, headings, buttons, links, or images.
    WHAT it does: Creates display elements with formula support for dynamic values.
    RETURNS: Created elements with ref-to-ID mapping.
    REQUIRED: `page_id` and `elements` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Element Structure
    - parent_element: int ID (existing container) or string ref (same batch)
    - place_in_container: 0-indexed column position for column elements

    ## Dynamic Values with $formula:
    - Heading/text value: "$formula: the product name from the products data source"
    - Image URL: "$formula: the image URL from the product data source"
    - Static text: use plain strings (auto-wrapped in quotes)
    - Inside a collection, descriptions use current_record for that collection's row.
      For intentional fixed-row access, supply an explicit runtime expression.

    ## After Creating Buttons
    Buttons need a click action (open_page, notification, etc.) via create_element_actions.
    Links use their navigation properties directly.

    ## Buttons/Links in Shared Headers
    - In shared headers, only use links that navigate to a FIXED page (navigate_to_page_id).
    - Do NOT create "back" buttons or context-dependent navigation in shared headers.
    - For page-specific navigation (back, contextual links), place buttons on the page itself.
    """

    require_payload("create_display_elements", "elements", elements)
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
    REQUIRED: `page_id` and `elements` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Element Structure
    - Layout elements are containers — add children via parent_element ref.
    - column: creates N columns, children use place_in_container "0", "1", etc.
    - menu: add menu_items to link to pages.

    ## Shared Elements (header, footer)
    - Headers/footers are shared across ALL pages by default (share_type="all").
    - Use share_type="only" + page_ids to limit which pages show them.
    - ONLY put absolute navigation in shared headers: links/menus to specific pages.
    - NEVER put page-specific content in shared headers (e.g., "back" button,
      page-specific data, breadcrumbs). These vary per page and will be wrong.
    - A menu element inside a header/footer is also shared.
    - `page_id` is still required for shared elements: pass any existing page of the
      application, such as the Home page from list_pages. There is no application_id.
    - Shared elements CANNOT reference page-specific data sources.
    """

    require_payload("create_layout_elements", "elements", elements)
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
    REQUIRED: `page_id` and `elements` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Form Structure
    - Create a form_container first, then add inputs inside it via parent_element.
    - Each input has label, placeholder, required, default_value.
    - input_text: validation_type (any, email, integer), is_multiline.
    - choice: choice_options, multiple.
    - record_selector: needs data_source.

    ## Edit Forms
    For forms that edit existing data, set default_value on each input using $formula: to reference the field value from the page's data source (e.g. "$formula: the Name field from the <data source name> data source").
    The form's submit action should be update_row with row_id referencing the page parameter.

    ## After Creating Forms
    Form containers need a submit action (create_row, update_row) via create_element_actions.
    ALWAYS call create_element_actions after creating form_container elements.
    """

    require_payload("create_form_elements", "elements", elements)
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
    REQUIRED: `page_id` and `elements` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Prerequisites
    Create data sources first (create_data_sources), then reference them here.

    ## Table
    - data_source: the data source ID or ref.
    - fields: the table's columns — always specify which columns to show. Each column has name and type ("text" or "button"); text columns take value ($formula: for dynamic content), button columns take label.

    ## Repeat
    - data_source: the data source ID or ref.
    - orientation: "vertical" or "horizontal".
    - Add child elements inside the repeat via parent_element ref.
    """

    require_payload("create_collection_elements", "elements", elements)
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

    WHEN to use: User wants to change properties of an existing element (text, label, settings, table columns, menu items, etc.).
    WHAT it does: Updates the specified properties on an element. Only non-null properties are applied.
    RETURNS: Updated element ID and list of changed properties. Table column changes also return the table's columns afterwards and the removed columns; menu item changes return the menu's items afterwards and the removed items.
    DO NOT USE when: You need to move elements, change data sources, or modify styles — use other tools for those.

    ## Usage
    - element_id: ID of the element to update (from list_elements).
    - Only set the properties you want to change — unset properties are left unchanged.
    - Unsupported properties reject the update without applying any changes.
    - Button navigation belongs in create_element_actions(type='open_page', event='click'),
      not in update_element. Links support navigation properties directly.
    - A button's text is what it says before it's clicked. What it shows or does when
      clicked, like the message of a notification, is a click action: find it with
      list_element_actions and change it with update_element_action.

    ## Table Columns
    - list_elements shows each table's columns with uid, name, type, and value or label.
      Change them by uid with add_table_columns, update_table_columns,
      reorder_table_columns and remove_table_columns; columns you don't list stay
      exactly as they are.
    - value and label take fixed text or a runtime formula such as
      get('current_record.field_<id>'). "$formula:" descriptions work only when
      creating a table.
    - To show a database field, set field_id (from get_tables_schema). Renaming a
      column doesn't change what it shows.
    - Only text and button columns can be created. Never remove a column to rebuild
      it or to work around a setting you can't change (a link's target, styles,
      link, tags or image settings): tell the user to change it in the table's
      editor.
    - Remove a column only when the user asked for it, and confirm first: undo
      doesn't revert column changes, and removed columns and their click actions
      are gone for good.

    ## Dynamic Values with $formula:
    - value: "$formula: the product name from the data source"
    - default_value: "$formula: the current user's email"
    - Inside a collection, descriptions use current_record for that collection's row.
      For intentional fixed-row access, supply an explicit runtime expression.
    - Switching a link/image to a generated URL applies only if that URL succeeds.
      Independent changes can still apply; updated_fields lists only saved changes.

    ## Menu Items
    - list_elements shows each menu's items with uid, name, type, page_id (or url, for
      a link to a custom address), and a top-level link's sub-links as children.
      Change them by uid with add_menu_items, update_menu_items, reorder_menu_items
      and remove_menu_items; items you don't list stay exactly as they are. On a
      header or footer, they change its menu.
    - add_menu_items adds page links, last unless before_uid is set; parent_uid makes
      one a sub-link of a top-level link.
    - update_menu_items renames an item or points a link to a page; the item keeps
      its type, click actions and sub-links, and a new page drops the old page's
      parameters. A button can't link to a page: give it an open_page action with
      create_element_actions.
    - reorder_menu_items lists every top-level item that stays; sub-links can't be
      reordered.
    - Remove an item only when the user asked for it: its sub-links go with it, undo
      doesn't restore removed items, and a removed button's click actions are gone for
      good.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    page = helpers.get_page(user, ctx.deps.workspace, page_id)
    tool_helpers.update_status(
        _("Updating element %(id)d...") % {"id": element.element_id}
    )

    tool_context = ctx.deps.tool_context()
    outcome, formula_errors = shared_elements.update_element_on_page(
        tool_context, page, element
    )
    orm_element, element_type = outcome.element, outcome.element_type

    # Handle formula generation for $formula: fields (separate transaction)
    remaining = agents.repair_builder_formula_errors(
        tool_context, tool_helpers, page, formula_errors
    )
    errors = _update_element_formula_errors(element.element_id, remaining)
    not_applied = {entry["field"] for entry in remaining}
    formulas = element.get_formulas_to_update(orm_element, None, element_type)
    applied_formulas = [field for field in formulas if field not in not_applied]

    dependent_fields = element.get_formula_dependent_fields(element_type)
    property_aliases = element_tool_type_registry.get_for(element_type).property_aliases
    updated_fields = []
    for field in element.get_updated_field_names():
        formula_field = property_aliases.get(field, field)
        formula_field = dependent_fields.get(field, formula_field)
        if formula_field not in formulas or formula_field in applied_formulas:
            updated_fields.append(field)
    result = {
        "status": ("partial" if updated_fields else "error") if errors else "ok",
        "element_id": element.element_id,
        "element_type": element_type,
        "updated_fields": updated_fields,
        **outcome.result,
    }
    if errors:
        result["errors"] = errors
    return result


def _update_element_formula_errors(
    element_id: int, entries: list[BuilderFormulaError]
) -> list[str]:
    """How Kuma words values the repair of an updated element couldn't fill."""

    if any(entry.permission_denied for entry in entries):
        return [
            "Permission denied while applying element formulas. "
            "Previous formula values were retained. Do not retry the denied operation."
        ]
    fields_by_error: dict[str, list[str]] = {}
    for entry in entries:
        fields_by_error.setdefault(entry["error"], []).append(entry["field"])
    return [
        (
            "No valid formula was generated for: "
            f"{', '.join(sorted(fields))}. Previous values were retained."
        )
        if error == agents.NO_VALID_FORMULA
        else (
            f"Formula generation failed for element {element_id}: {error}. "
            "Previous formula values were retained."
        )
        for error, fields in fields_by_error.items()
    ]


# ---------------------------------------------------------------------------
# Element style tool
# ---------------------------------------------------------------------------


def update_element_style(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID the element belongs to.")],
    style: Annotated[ElementStyleUpdate, Field(description="Style update data.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update visual style of an element (box model + theme overrides).

    WHEN to use: User wants to change borders, padding, margins, background, width, or theme style overrides (button colors, typography, input styles, etc.).
    WHAT it does: Applies box-model values and per-element-type theme overrides.
    RETURNS: Updated element ID, type, and list of changed fields.
    DO NOT USE when: You need to change content (text, label) or structural properties — use update_element instead.

    ## Box Model
    - border_color, border_size, padding, margin: pass a single value for all 4 sides, or a dict like {"left": 0, "top": 10} to set specific sides only.
    - border_radius, background_radius: corner rounding.
    - background: "none" or "color", background_color: hex color.
    - width: "full", "full-width", "normal", "medium", "small".

    ## Theme Style Overrides (per element type)
    - button: background_color, text_color, border_color, hover colors, font_size, width, alignment.
    - link: text_color, hover_text_color, font_size, font_weight.
    - typography: heading_1_*/body_* text_color, font_size, font_weight, text_alignment.
    - input: input_background_color, input_border_color, input_text_color, label_text_color.
    - table: header/cell colors, border_color, border_size.
    - image: image_alignment, max_width, max_height, border_radius.

    Only blocks valid for the element type are applied; others are ignored.

    ## Reset
    Set reset=true to restore all box-model fields to defaults and clear theme overrides.
    You can combine reset with new values to reset-then-apply.
    """

    page = helpers.get_page(ctx.deps.user, ctx.deps.workspace, page_id)
    if _not_on_page(page, [style.element_id]):
        raise ToolInputError(
            f"Element with ID {style.element_id} not found. "
            "Use list_elements to find valid element IDs."
        )
    shared = shared_elements.update_element_style(
        ctx.deps.tool_context(),
        style.element_id,
        ElementStyleChanges(**style.model_dump(exclude={"element_id"})),
    )
    element_type = shared["updated_element"]["type"]
    updated_fields = shared["updated_fields"]
    if not updated_fields:
        return {
            "status": "warning",
            "element_id": style.element_id,
            "element_type": element_type,
            "message": (
                "No style fields were applied. Make sure you pass style "
                "properties (padding, margin, border_size, border_color, "
                "background, width, etc.) in the style parameter. "
                "Theme overrides (button, link, typography, etc.) are only "
                "applied if the element type supports them."
            ),
        }
    return {
        "status": "ok",
        "element_id": style.element_id,
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
    - place_in_container: Slot inside parent_element_id (e.g. "0", "1" for columns). Only valid together with parent_element_id; null = default. When moving to the root level leave it null.
    """

    if not moves:
        return {"moved_elements": []}

    page = helpers.get_page(ctx.deps.user, ctx.deps.workspace, page_id)
    ctx.deps.tool_helpers.update_status(
        _("Moving %(count)d elements on %(name)s...")
        % {"count": len(moves), "name": page.name}
    )
    elsewhere = set(_not_on_page(page, [move.element_id for move in moves]))
    result = shared_elements.move_elements(
        ctx.deps.tool_context(),
        [move for move in moves if move.element_id not in elsewhere],
    )
    if elsewhere:
        result.setdefault("errors", []).extend(
            f"{element_id}: Element not found on page {page.id}. Use list_elements "
            "to find valid element IDs."
            for element_id in sorted(elsewhere)
        )
    return result


# ---------------------------------------------------------------------------
# Workflow action tools
# ---------------------------------------------------------------------------


def list_element_actions(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[int, Field(description="The page ID.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List all workflow actions on a page.

    WHEN to use: Check existing actions, find action IDs, review field mappings, or find what a button does when clicked, like the message it shows.
    WHAT it does: Lists actions with id, type, element_id, event, field_mappings.
    RETURNS: Workflow actions array.
    """

    try:
        return shared_actions.list_element_actions(ctx.deps.tool_context(), page_id)
    except PageDoesNotExist:
        raise _page_not_found(page_id)


def create_element_actions(
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
    RETURNS: Created actions with id, type, element, event.
    REQUIRED: `page_id` and `actions` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.

    ## Attaching Actions
    - element: a ref from the same batch, or an existing element ID (from list_elements)
    - event: "click" for buttons/links, "submit" for form containers
    - Per-row buttons: add a button column to the table element, then attach each action to the table element with event "<column name>_click" (e.g. "View_click", "Delete_click") or "<uid>_click" with the column uid from list_elements. Use the column name, not its button label. Bare "click" works only for a table with one button column; duplicate column names require the "<uid>_click" event. Pass the row with page_parameters, e.g. {"name": "id", "value": "$formula: get('current_record.id')"}.

    ## Action Types
    - notification: Show a message (title/description are formulas)
    - open_page: Navigate to another page (set navigate_to_page_id). Give page_parameters with exactly the names of the target page's path parameters, like the current row's ID: without them the action isn't created.
    - create_row: Insert a row (needs table_id and field_values)
    - update_row: Update a row (needs table_id, row_id, field_values)
    - delete_row: Delete a row (needs table_id and row_id)
    - refresh_data_source: Reload a data source
    - logout: Log out the user

    ## Dynamic Values with $formula:
    Use "$formula: <intent>" — describe the data you want using references or ids when possible.
    - field_values: {"field_id": "123", "value": "$formula: the Name form input"}
    - row_id: "$formula: the id from the page parameter"
    """

    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_element_actions", "actions", actions)

    page = helpers.get_page(ctx.deps.user, ctx.deps.workspace, page_id)

    tool_context = ctx.deps.tool_context()
    shared = shared_actions.create_actions_with_options(
        tool_context,
        page_id,
        actions,
        BuilderWriteOptions(
            known_refs=_get_element_refs(tool_helpers, page_id),
            known_data_source_refs=_get_data_source_refs(tool_helpers, page_id),
            defer_required_formulas=True,
            item_error=item_error,
        ),
    )

    # Formula generation (separate transactions)
    errors = shared.get("errors", [])
    errors.extend(
        _create_element_formula_errors(
            agents.repair_builder_formula_errors(
                tool_context, tool_helpers, page, shared.get("formula_errors", [])
            )
        )
    )

    result: dict[str, Any] = {"created_actions": shared["created_actions"]}
    if errors:
        result["errors"] = errors
    return result


def add_element_action_field_mapping(
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
    RETURNS: The updated action with its field mappings. A value that isn't a valid formula is refused and nothing changes.
    """

    return shared_actions.add_element_action_field_mapping(
        ctx.deps.tool_context(), action_id, field_id, value_formula
    )


def update_element_action(
    ctx: RunContext[AssistantDeps],
    action_id: Annotated[int, Field(description="The workflow action ID.")],
    changes: Annotated[
        ActionChanges,
        Field(description="The values to change. Set only what should change."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Change the values of an existing workflow action.

    WHEN to use: A notification, open_page, row or refresh_data_source action should do something else, like a new message (a notification's title), target page or row_id.
    WHAT it does: Changes the given values. Its type, element and event stay as they are. page_parameters and query_parameters replace the whole list; field_values change the named fields only.
    RETURNS: The updated action, with errors for values that kept their previous value.
    DO NOT USE when: The action doesn't exist yet — use create_element_actions instead.
    EXAMPLE: {"action_id": 12, "changes": {"title": "'Order placed'"}, "thought": "Change the message of the Buy button's notification."}. thought is required, however small the change.

    ## Dynamic Values with $formula:
    - title: "$formula: the name of the product"
    - row_id: "$formula: the id from the page parameter"
    - field_values: {"field_id": "123", "value": "$formula: the Name form input"}
    """

    tool_context = ctx.deps.tool_context()
    action, formula_errors = shared_actions.update_action_values(
        tool_context, action_id, changes
    )

    errors = _kept_value_errors(
        agents.repair_builder_formula_errors(
            tool_context, ctx.deps.tool_helpers, action.page, formula_errors
        )
    )
    updated = BuilderWorkflowActionHandler().get_workflow_action(action_id)
    result: dict[str, Any] = {
        "updated_action": ActionItem.from_orm(updated).model_dump()
    }
    if errors:
        result["errors"] = errors
    return result


# ---------------------------------------------------------------------------
# Composite page setup tool
# ---------------------------------------------------------------------------


def setup_page(
    ctx: RunContext[AssistantDeps],
    page_id: Annotated[
        int,
        Field(
            description="Existing page ID from list_pages or create_pages, never an application ID. Create a requested new page with create_pages first."
        ),
    ],
    data_sources: Annotated[
        list[DataSourceCreate] | None,
        Field(default=None, description="Data sources to create."),
    ] = None,
    elements: Annotated[
        list[ElementItemCreate] | None,
        Field(default=None, description="Elements to create (all types)."),
    ] = None,
    actions: Annotated[
        list[ActionCreate] | None,
        Field(default=None, description="Workflow actions to create."),
    ] = None,
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ] = "",
) -> dict[str, Any]:
    """\
    Populate an existing page with data sources, elements, and actions.

    WHEN to use: Building a complete page with data, UI elements, and interactions.
    WHAT it does: Adds content to an existing page; it does not create the page itself. For a requested new page, call create_pages first and use its returned ID. Creates data sources first, then elements (in order), then actions. Handles ref resolution across all three phases.
    RETURNS: Created items with ref-to-ID mappings and any errors. Partial success is possible — some items may be created even when others fail. Check the ``errors`` key.
    ARGS: ``page_id`` is WHERE to build; ``data_sources``, ``elements`` and ``actions`` are WHAT to build. Each of the three is optional on its own, but a call carrying none of them creates nothing and is rejected. To only open a page, use ``navigate``.

    ## Deduplication
    Data sources are deduplicated by name (case-insensitive) and by structural match (same type and table). Existing data sources are reused and their IDs mapped to the provided refs.

    ## Execution Order
    1. Data sources (list_rows, get_row) — so elements can reference them.
    2. Elements (in order — parents before children): heading, text, button, link, image, column, form_container, simple_container, input_text, choice, checkbox, datetime_picker, record_selector, table, repeat.
    3. Actions (click, submit) — attached to elements via ref.

    ## Element Fields by Type
    - heading: value (text), level (1-5)
    - text: value (text), format ("plain"/"markdown")
    - button/link: value (label)
    - image: image_url, alt_text
    - column: column_count
    - form_container: submit_button_label
    - input_text: label, placeholder, default_value, required, validation_type, is_multiline
    - choice: label, choice_options, multiple
    - checkbox: label, default_value
    - table: data_source (ref), fields [{name, type ("text"/"button"), value (text) or label (button)}]
    - repeat: data_source (ref), orientation

    ## Refs
    - data_source refs: referenced by elements (data_source field) and actions (data_source field)
    - element refs: referenced by child elements (parent_element field) and actions (element field)
    - Use string refs for items created in this call, int IDs for pre-existing items.

    ## Dynamic Values
    Use "$formula: <intent>" — describe the data you want using references or ids when possible.
    Examples: "$formula: the Name field from the projects data source", "$formula: the Email form input".

    ## Shared Elements (header, footer) — CRITICAL
    Headers and footers are shared across ALL pages. Any element placed inside
    a header/footer (as a child) is also shared and appears on every page.
    - ONLY put site-wide navigation in headers/footers: menus, logo, links to fixed pages.
    - NEVER put page-specific content as children of headers/footers: page titles,
      data-bound text, forms, "back" buttons, or content that varies per page.
    - Page-specific content belongs directly on the page root, NOT inside shared containers.
    - If a header already exists (page_name="[shared]" in list_elements), do NOT
      add page-specific children to it.
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    if not data_sources and not elements and not actions:
        raise ModelRetry(
            "setup_page was called with no content: `data_sources`, `elements` "
            "and `actions` were all empty, so nothing was created. An ID "
            "argument says where to act, never what to do — send the items to "
            "build in the same call that carries the ID. To only open a page, "
            "use `navigate` instead."
        )

    page = helpers.get_page(user, ctx.deps.workspace, page_id)
    shared_page = PageHandler().get_shared_page(page.builder)

    reused, new_data_sources = _split_reused_data_sources(
        user, page, data_sources or []
    )
    _track_data_source_refs(tool_helpers, page_id, reused)
    shared_page_refs: set[str] = set(
        _get_element_refs(tool_helpers, shared_page.id).keys()
    )
    tool_context = ctx.deps.tool_context()

    def after_phase(kind: str, phase: dict[str, Any]) -> list[BuilderFormulaError]:
        # Tracked as each phase ends, so a cancelled call keeps the refs it saved.
        if kind == "data_source":
            _track_data_source_refs(tool_helpers, page_id, phase["ref_to_id_map"])
        elif kind == "element":
            _track_element_refs(tool_helpers, page_id, phase["ref_to_id_map"])
            _track_element_refs(
                tool_helpers,
                shared_page.id,
                {
                    ref: 0
                    for ref in _get_element_refs(tool_helpers, page_id)
                    if ref in shared_page_refs
                },
            )
        return agents.repair_builder_formula_errors(
            tool_context, tool_helpers, page, phase.get("formula_errors", [])
        )

    shared = shared_pages.setup_page_with_options(
        tool_context,
        page_id,
        new_data_sources,
        elements,
        actions,
        BuilderWriteOptions(
            known_refs=_get_element_refs(tool_helpers, page_id),
            known_data_source_refs=_get_data_source_refs(tool_helpers, page_id),
            known_shared_page_refs=shared_page_refs,
            prepare_element=_named_field_beats_description,
            defer_required_formulas=True,
            item_error=item_error,
            after_phase=after_phase,
        ),
    )

    all_errors = shared.get("errors", [])
    formula_errors = shared.get("formula_errors", [])
    all_errors.extend(
        _create_data_source_formula_error(entry)
        for entry in formula_errors
        if entry.kind == "data_source"
    )
    all_errors.extend(
        _create_element_formula_errors(
            [entry for entry in formula_errors if entry.kind != "data_source"]
        )
    )

    result: dict[str, Any] = {
        key: shared[key]
        for key in ("created_data_sources", "created_elements", "created_actions")
        if shared[key]
    }

    if shared.get("permission_denied"):
        return {
            **result,
            "errors": all_errors,
            **permission_denied_result("setup_page"),
        }

    if all_errors:
        result["errors"] = all_errors

    # Navigate to the page
    tool_helpers.navigate_to(
        BuilderPageNavigationType(
            type="builder-page",
            application_id=page.builder_id,
            page_id=page_id,
            page_name=page.name,
        )
    )

    return result


# ---------------------------------------------------------------------------
# Tool: setup_user_source
# ---------------------------------------------------------------------------


def setup_user_source(
    ctx: RunContext[AssistantDeps],
    application_id: Annotated[int, Field(description="The builder application ID.")],
    setup: Annotated[UserSourceSetup, Field(description="User source configuration.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Set up a user source so the application can have logged-in users with roles.

    WHEN to use: User wants login, authentication, role-based access, or user accounts in their app.
    WHAT it does: Creates a users table (or uses an existing one) and configures a Local Baserow user source with password authentication.
    RETURNS: User source ID, table ID, available roles, login page ID.
    REUSE: If the application already has a Local Baserow user source on that table, it is reused instead of creating another, and the login page and its login form are still added when missing. One that isn't set up for password login is refused.
    HOW: If user mentions a specific table, use table_id. Otherwise use database_id to create a new users table.
    """

    try:
        _get_builder(ctx, application_id)
    except ToolInputError as exc:
        return {"error": str(exc)}

    try:
        shared = shared_user_sources.setup_user_source(
            ctx.deps.tool_context(), application_id, setup
        )
    except Exception as exc:
        raise_if_permission_denied(exc)
        return {"error": str(exc)}

    user_source = shared.get("created_user_source") or shared["reused_user_source"]
    result: dict[str, Any] = {
        "user_source_id": user_source["id"],
        "table_id": shared["table_id"],
        "roles": shared["roles"],
        "login_page_id": shared["login_page_id"],
    }
    if "hint" in shared:
        result["hint"] = shared["hint"]
    return result


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
    DO NOT USE when: Creating a new application — use the theme parameter on create_builder instead.

    ## Available Themes
    {theme_list}
    """

    _get_builder(ctx, application_id)

    try:
        shared_themes.set_theme(ctx.deps.tool_context(), application_id, theme_name)
    except ToolInputError as exc:
        return {
            "status": "error",
            "application_id": application_id,
            "theme": theme_name,
            "error": str(exc),
        }

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
    update_element_style,
    move_elements,
    list_element_actions,
    create_element_actions,
    add_element_action_field_mapping,
    update_element_action,
    setup_page,
    setup_user_source,
    set_theme,
]
builder_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)
