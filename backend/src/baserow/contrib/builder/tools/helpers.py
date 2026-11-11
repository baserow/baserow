"""
Shared helpers for the builder tools that Kuma and MCP call.

Contains permission-checked accessors, listing functions, and the element/data
source/action creation orchestrators used by ``tools.py`` and ``agents.py``.
"""

from collections import Counter
from typing import Any, Callable, NamedTuple

from django.contrib.auth.models import AbstractUser
from django.db import DatabaseError, transaction
from django.db.models import Q

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.data_sources.actions import (
    CreateDataSourceActionType,
    UpdateDataSourceActionType,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    ReadDataSourceOperationType,
    UpdateDataSourceOperationType,
)
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    MoveElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import (
    CollectionField,
    Element,
    LinkElement,
    MenuElement,
    MenuItemElement,
)
from baserow.contrib.builder.elements.operations import (
    ReadElementOperationType,
    UpdateElementOperationType,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.operations import ListPagesBuilderOperationType
from baserow.contrib.builder.pages.actions import (
    CreatePageActionType,
    UpdatePageActionType,
)
from baserow.contrib.builder.pages.exceptions import (
    DuplicatePageParams,
    DuplicatePathParamsInPath,
    InvalidPagePath,
    InvalidPagePathParamType,
    InvalidQueryParamName,
    PagePathNotUnique,
    PathParamNotDefined,
    PathParamNotInPath,
    SharedPageIsReadOnly,
)
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.actions import (
    CreateBuilderWorkflowActionActionType,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    OpenPageWorkflowAction,
)
from baserow.contrib.builder.workflow_actions.operations import (
    ReadBuilderWorkflowActionOperationType,
    UpdateBuilderWorkflowActionOperationType,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowViewServiceType,
)
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.graph.types import GraphPointPosition
from baserow.core.handler import CoreHandler
from baserow.core.integrations.actions import CreateIntegrationActionType
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.models import Workspace
from baserow.core.services.registries import service_type_registry
from baserow.core.tools.errors import (
    ToolInputError,
    raise_if_permission_denied,
    validation_messages,
)
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist

from .errors import UnknownRefError
from .lookups import get_readable_page
from .page_parameters import parameters_in_page_order
from .registries import element_tool_type_registry
from .types import (
    ActionCreate,
    ActionItem,
    ActionUpdate,
    DataSourceCreate,
    DataSourceItem,
    DataSourceUpdate,
    ElementItem,
    ElementItemCreate,
    ElementMove,
    ElementStyleUpdate,
    ElementUpdate,
    PageCreate,
    PageItem,
    PageUpdate,
)
from .types.page import PagePathParam, with_path_parameters
from .types.workflow_action import raise_if_read_only_field

# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def on_page(page: Page) -> Q:
    """
    Filter for the elements or data sources a tool working on ``page`` may reach:
    those on the page itself and on its builder's shared page.
    """

    return Q(page=page) | Q(page__builder_id=page.builder_id, page__shared=True)


def forget_page_graphs(page: Page) -> None:
    """
    Reload the graphs of ``page`` and of its builder's shared page and drop their
    cached elements, after an element's savepoint rolled back or a transaction that
    locked the graph ended. The request's caches still hold the rolled back element
    and a handler that thinks it holds the lock.
    """

    for graph_page in (page, page.builder.shared_page):
        graph_page.reload_graph()
        ElementHandler().invalidate_element_cache(graph_page)


def check_data_source_on_page(page: Page, data_source_id: int) -> None:
    """
    :raises ToolInputError: When the data source is neither on ``page`` nor on its
        builder's shared page.
    """

    if not DataSource.objects.filter(on_page(page), id=data_source_id).exists():
        if page.shared:
            raise ToolInputError(
                f"Data source with ID {data_source_id} is not on the shared page. A "
                "header or footer shows on every page, so its actions and elements "
                "can only use a data source of the shared page."
            )
        raise ToolInputError(
            f"Data source with ID {data_source_id} not found on this page. "
            "Use list_data_sources to find valid data source IDs. No changes were "
            "applied."
        )


def check_pages_in_builder(builder: Builder, page_ids: list[int]) -> None:
    """
    Check the pages a header or footer is shown on. The element would leave out a
    page of another builder, or the shared page, without saying so.

    :raises ToolInputError: When one is a page of another application or the
        shared page.
    """

    found = set(
        Page.objects_without_shared.filter(
            builder=builder, id__in=page_ids
        ).values_list("id", flat=True)
    )
    missing = [page_id for page_id in page_ids if page_id not in found]
    if missing:
        raise ToolInputError(
            f"Page with ID {missing[0]} not found in this application. "
            "Use list_pages to find valid page IDs. No changes were applied."
        )


def get_page(user: AbstractUser, workspace: Workspace, page_id: int) -> Page:
    """
    Get a page of the workspace with permission check.

    :param user: The acting user.
    :param workspace: The workspace the page must belong to.
    :param page_id: The ID of the page to fetch.
    :returns: The matching page.
    :raises ToolInputError: When the page is missing or not accessible.
    """

    try:
        return get_readable_page(user, workspace, page_id)
    except Exception as exc:
        raise_if_permission_denied(exc)
        raise ToolInputError(
            f"Page with ID {page_id} not found or not accessible. "
            "Use list_pages to find valid page IDs."
        )


def get_local_baserow_integration(user: AbstractUser, builder: Builder) -> Integration:
    """Get or create the LocalBaserow integration for a builder."""

    integrations = IntegrationService().get_integrations(user, builder)
    for integration in integrations:
        if integration.get_type().type == "local_baserow":
            return integration.specific

    return create_local_baserow_integration(user, builder)


def create_local_baserow_integration(
    user: AbstractUser, builder: Builder
) -> Integration:
    """
    Connect a builder to the workspace's data. The audit log records it, but it stays
    out of the undo stack: undoing it would trash the connection under the data
    sources and actions that use it.
    """

    with without_undo_redo_registration(user):
        return CreateIntegrationActionType.do(
            user,
            integration_type_registry.get("local_baserow"),
            builder,
            name="Local Baserow",
        ).specific


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def list_pages(user: AbstractUser, builder: Builder) -> list[PageItem]:
    """List all non-shared pages in a builder."""
    pages = CoreHandler().filter_queryset(
        user,
        ListPagesBuilderOperationType.type,
        PageHandler().get_pages(builder, Page.objects.filter(shared=False)),
        workspace=builder.workspace,
    )
    return [PageItem.from_orm(p) for p in pages]


def list_data_sources(user: AbstractUser, page: Page) -> list[DataSourceItem]:
    """List all data sources on a page."""
    return [
        DataSourceItem.from_orm(ds)
        for ds in DataSourceService().get_data_sources(user, page)
    ]


def list_data_sources_on_page(user: AbstractUser, page: Page) -> list[DataSourceItem]:
    """List the data sources of a page and of its builder's shared page."""

    return [
        DataSourceItem.from_orm(ds)
        for ds in DataSourceService().get_data_sources(user, page, with_shared=True)
    ]


def _place_order(place: str) -> int:
    """Where a place shows in its container: a column's places are its numbers."""

    return int(place) if place.isdecimal() else 0


def _in_page_order(page: Page, elements: list) -> list:
    """
    Sort a page's elements by their place in its graph, with a container's children
    right after it. Elements the graph doesn't reach go last.
    """

    ordered = page.get_graph().get_ordered_point_ids(edge_order=_place_order)
    position = {point_id: index for index, point_id in enumerate(ordered)}
    return sorted(elements, key=lambda el: position.get(el.id, len(position)))


def list_elements(user: AbstractUser, page: Page) -> list[ElementItem]:
    """
    List all elements on a page, including shared elements visible on it.
    Elements are listed in page order, with a container's children right after it.
    """

    def page_elements(listed_page: Page) -> list:
        listed = list(ElementService().get_elements(user, listed_page))
        # The items name the page, which is loaded already.
        for element in listed:
            element.page = listed_page
        return _in_page_order(listed_page, listed)

    elements = page_elements(page)

    # Also include shared elements (headers/footers) visible on this page
    if not page.shared:
        elements = page_elements(page.builder.shared_page) + elements

    return [ElementItem.from_orm(el) for el in elements]


def list_workflow_actions(user: AbstractUser, page: Page) -> list[ActionItem]:
    """List the workflow actions of a page and of its builder's shared page."""

    service = BuilderWorkflowActionService()
    return [
        ActionItem.from_orm(action)
        for listed_page in dict.fromkeys((page, page.builder.shared_page))
        for action in service.get_workflow_actions(user, listed_page)
    ]


# ---------------------------------------------------------------------------
# Page creation
# ---------------------------------------------------------------------------


def _taken_path_error(
    builder: Builder,
    path: str,
    page_id: int | None = None,
    outcome: str = "Nothing was changed in this call.",
) -> ToolInputError:
    """
    Describe a path that another page of the builder already uses.

    :param builder: The builder application the path must be unique in.
    :param path: The path that is already used.
    :param page_id: The page that asked for the path, which is not a clash.
    :param outcome: What the call did about it.
    :return: The error to raise, naming the page that uses the path.
    """

    try:
        page = PageHandler().get_page_with_clashing_path(
            builder, path, base_queryset=Page.objects_and_trash.exclude(id=page_id)
        )
    except DatabaseError:
        # The clash can surface as an IntegrityError that aborts the transaction.
        page = None
    if page is None:
        owner = "another page"
    elif page.trashed:
        owner = (
            f"page {page.id} ('{page.name}'), which is in the trash and keeps the "
            "path until it is permanently deleted"
        )
    else:
        owner = f"page {page.id} ('{page.name}')"
    return ToolInputError(
        f"The path '{path}' is already used by {owner}. {outcome} Pick another path."
    )


def ensure_distinct_paths(pages: list[PageCreate]) -> None:
    """
    Check that pages created together do not share a path.

    :param pages: The pages one call creates.
    :raises ToolInputError: When two of them use clashing paths.
    """

    handler = PageHandler()
    pages_by_path: dict[str, PageCreate] = {}
    for page in pages:
        generalised = handler.generalise_path(page.path)
        if generalised in pages_by_path:
            other = pages_by_path[generalised]
            raise ToolInputError(
                f"Pages '{other.name}' at '{other.path}' and '{page.name}' at "
                f"'{page.path}' use the same path, as parameter names do not make "
                "paths different. Nothing was created. Give each page its own path."
            )
        pages_by_path[generalised] = page


# Raised for a page's path or parameters.
_PAGE_PARAM_ERRORS = (
    InvalidPagePath,
    PathParamNotInPath,
    PathParamNotDefined,
    DuplicatePathParamsInPath,
    InvalidPagePathParamType,
    InvalidQueryParamName,
    DuplicatePageParams,
)


def create_page(user: AbstractUser, builder: Builder, page_create: PageCreate) -> Page:
    """
    Create a page in a builder application.

    :raises ToolInputError: When another page already uses the path, or the path or
        parameters are not valid.
    """

    try:
        # Visibility and roles are part of the creation, so one undo removes the
        # page instead of leaving it visible to everyone.
        return CreatePageActionType.do(
            user,
            builder,
            page_create.name,
            page_create.path,
            path_params=[p.model_dump() for p in page_create.path_params],
            query_params=[p.model_dump() for p in page_create.query_params],
            visibility=page_create.visibility,
            role_type=page_create.role_type,
            roles=page_create.roles,
        )
    except PagePathNotUnique:
        # create_pages saves the other pages of the call.
        raise _taken_path_error(
            builder, page_create.path, outcome="This page was not created."
        )
    except _PAGE_PARAM_ERRORS as exc:
        raise ToolInputError(f"{exc}. This page was not created.")


# ---------------------------------------------------------------------------
# Page update
# ---------------------------------------------------------------------------


def update_page(
    user: AbstractUser,
    workspace: Workspace,
    page_update: PageUpdate,
) -> Page:
    """
    Update an existing page by ID.

    Returns the updated page.

    :raises ToolInputError: When the new path or parameters are not valid.
    """

    page = get_page(user, workspace, page_update.page_id)
    kwargs = page_update.to_update_kwargs()
    if "path" in kwargs:
        # Parameters left out of path_params keep their type if the new path still
        # names them; new ones are text.
        names = PageHandler().get_path_param_names(kwargs["path"])
        given = page_update.path_params or []
        given_names = {param.name for param in given}
        try:
            kept = [
                PagePathParam(**param)
                for param in page.path_params
                if param["name"] in names and param["name"] not in given_names
            ]
            path_params = with_path_parameters(kwargs["path"], [*given, *kept])
        except ValueError as exc:
            raise ToolInputError(f"{exc} Nothing was changed in this call.") from exc
        kwargs["path_params"] = [param.model_dump() for param in path_params]
    if kwargs:
        try:
            UpdatePageActionType.do(user, page, **kwargs)
        except PagePathNotUnique:
            raise _taken_path_error(
                page.builder, kwargs.get("path", page.path), page_id=page.id
            )
        except SharedPageIsReadOnly:
            raise ToolInputError(
                f"Page {page.id} is the shared page, which can't be changed."
            )
        except _PAGE_PARAM_ERRORS as exc:
            raise ToolInputError(f"{exc}. Nothing was changed in this call.")
        page.refresh_from_db()
    return page


def navigations_out_of_step(page: Page) -> list[dict[str, Any]]:
    """
    The links, table link columns, menu items and open page actions that go to a page with parameter
    names other than the page's, in its order. The frontend shows them as errors and
    a publish hides them.

    :param page: The page they open.
    :return: Each one, with what it gives and how to fix it.
    """

    expected = [param["name"] for param in page.path_params or []]

    def names(navigation) -> list[str]:
        return [param["name"] for param in navigation.page_parameters or []]

    on_page = {"navigate_to_page": page, "navigation_type": "page"}
    found: list[dict[str, Any]] = []
    for link in LinkElement.objects.filter(**on_page, page__trashed=False):
        if names(link) != expected:
            found.append(
                {
                    "type": "link",
                    "element_id": link.id,
                    "page_parameters": names(link),
                    "fix": "Give the link link_page_parameters named "
                    f"{', '.join(expected) or 'nothing'} with update_element.",
                }
            )
    for action in OpenPageWorkflowAction.objects.filter(**on_page, page__trashed=False):
        if names(action) != expected:
            found.append(
                {
                    "type": "open_page action",
                    "action_id": action.id,
                    "element_id": action.element_id,
                    "page_parameters": names(action),
                    "fix": "Change the page_parameters of this click action to "
                    f"{', '.join(expected) or 'none'}.",
                }
            )
    # Table link columns keep their navigation in the column's config. The tools
    # can't make or change them, so the fix is in the editor.
    for column in CollectionField.objects.filter(
        type="link",
        config__navigation_type="page",
        config__navigate_to_page_id=page.id,
    ).prefetch_related("tableelement_set__page"):
        if [param["name"] for param in column.config.get("page_parameters") or []] == (
            expected
        ):
            continue
        tables = [
            table for table in column.tableelement_set.all() if not table.page.trashed
        ]
        if not tables:
            continue
        found.append(
            {
                "type": "table link column",
                "element_id": tables[0].id,
                "column_name": column.name,
                "page_parameters": [
                    param["name"]
                    for param in column.config.get("page_parameters") or []
                ],
                "fix": "Change the page parameters of this table column in the "
                f"editor to {', '.join(expected) or 'none'}; the tools can't.",
            }
        )
    # The editor sets a menu item's page parameters; the tools only point it to a
    # page, so the fix offers both.
    for item in MenuItemElement.objects.filter(**on_page).prefetch_related(
        "menuelement_set__page"
    ):
        if names(item) == expected:
            continue
        menus = [menu for menu in item.menuelement_set.all() if not menu.page.trashed]
        if not menus:
            continue
        found.append(
            {
                "type": "menu item",
                "element_id": menus[0].id,
                "uid": str(item.uid),
                "page_parameters": names(item),
                "fix": "Change the page parameters of this menu item in the editor "
                f"to {', '.join(expected) or 'none'}, or point it to another page "
                "with update_element.",
            }
        )
    return found


# ---------------------------------------------------------------------------
# Data source creation
# ---------------------------------------------------------------------------


def create_data_source(
    user: AbstractUser,
    page: Page,
    ds_create: DataSourceCreate,
    integration: Integration,
) -> tuple[Any, int]:
    """
    Create a data source on a page.

    :raises ToolInputError: When a sort names a field of another table.
    """

    service_type = service_type_registry.get(ds_create.get_service_type())
    service_kwargs = ds_create.to_service_kwargs(user, page.builder.workspace)
    service_kwargs["integration"] = integration
    sortings = ds_create.get_sortings()
    with transaction.atomic():
        data_source = CreateDataSourceActionType.do(
            user,
            page,
            service_type=service_type,
            name=ds_create.name,
            **service_kwargs,
        )

        if sortings:
            try:
                data_source = UpdateDataSourceActionType.do(
                    user,
                    data_source,
                    service_type=service_type,
                    service_sorts=sortings,
                )
            except DRFValidationError as exc:
                # The service refuses a sort on a field of another table.
                raise ToolInputError(
                    f"{validation_messages(exc)} Use a field of the data source's "
                    "table. No changes were applied."
                ) from exc

    return data_source, data_source.id


# ---------------------------------------------------------------------------
# Data source update
# ---------------------------------------------------------------------------


def update_data_source(
    user: AbstractUser,
    page: Page,
    ds_update: DataSourceUpdate,
) -> tuple[Any, str]:
    """
    Update an existing data source of the page or its builder's shared page by ID.

    :param user: The acting user.
    :param page: The page the data source must be on, or whose builder's shared
        page it must be on. Referenced tables must be in its workspace.
    :param ds_update: The update definition.
    :returns: ``(orm_data_source, service_type_str)``.
    :raises ToolInputError: When the data source does not exist.
    """

    workspace = page.builder.workspace
    try:
        ds = DataSourceHandler().get_data_source_for_update(
            ds_update.data_source_id,
            base_queryset=DataSource.objects.filter(on_page(page)),
        )
    except Exception as exc:
        raise_if_permission_denied(exc)
        raise ToolInputError(
            f"Data source with ID {ds_update.data_source_id} not found. "
            "Use list_data_sources to find valid data source IDs."
        )

    service_type = (
        service_type_registry.get_by_model(ds.service.specific) if ds.service else None
    )
    # Other services leave these out without saying so.
    for field in ("row_id", "search_query"):
        if getattr(ds_update, field) is not None and (
            service_type is None or field not in service_type.allowed_fields
        ):
            raise ToolInputError(
                f"Data source {ds.id} can't use '{field}': it isn't a kind of data "
                "source that has one. No changes were applied."
            )
    kwargs = ds_update.to_update_kwargs(user, workspace)
    if "view_id" in kwargs and not isinstance(
        service_type, LocalBaserowViewServiceType
    ):
        # Other services leave a view out without saying so.
        raise ToolInputError(
            f"Data source {ds.id} can't use a view. Only list_rows and get_row data "
            "sources read through a view. No changes were applied."
        )
    if kwargs:
        ds = UpdateDataSourceActionType.do(
            user, ds, service_type=service_type, **kwargs
        )
    else:
        # Formulas are written once generated; refuse before asking the model.
        operation_type = (
            UpdateDataSourceOperationType
            if ds_update.get_formulas_to_update(ds, None)
            else ReadDataSourceOperationType
        )
        CoreHandler().check_permissions(
            user, operation_type.type, workspace=workspace, context=ds
        )

    ds_type = ds.service.get_type().type if ds.service else ""
    return ds, ds_type


# ---------------------------------------------------------------------------
# Element creation
# ---------------------------------------------------------------------------


def create_element(
    user: AbstractUser,
    page: Page,
    element_create: ElementItemCreate,
    ref_to_id_map: dict[str, int],
    data_source_ref_to_id_map: dict[str, int],
    shared_page_refs: set[str] | None = None,
    before_id: int | None = None,
    prepare: Callable[[ElementItemCreate], None] | None = None,
) -> tuple[Any, int]:
    """
    Create an element on a page, resolving refs to IDs. ``prepare`` is called with
    the element once its data source ref is an ID, before anything is saved.

    Returns ``(orm_element, element_id)``.
    """

    if shared_page_refs is None:
        shared_page_refs = set()
    elements = Element.objects.filter(on_page(page))

    try:
        element_type = element_type_registry.get(element_create.type)
    except element_type_registry.does_not_exist_exception_class:
        # auth_form comes from enterprise, which an instance can run without.
        raise ToolInputError(
            f"This instance has no {element_create.type} element, so it wasn't created."
        )

    # Determine target page
    use_shared_page = element_create.use_shared_page
    parent = element_create.parent_element
    if isinstance(parent, str) and parent in shared_page_refs:
        use_shared_page = True
    elif isinstance(parent, int):
        # Check if the parent element lives on the shared page
        try:
            parent_el = ElementHandler().get_element(parent, base_queryset=elements)
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Parent element with ID {parent} not found on this page. "
                "Use list_elements to find valid element IDs. No changes were applied."
            )
        if parent_el.page.shared:
            use_shared_page = True

    target_page = page.builder.shared_page if use_shared_page else page

    # Resolve data source ref to integer ID early so that to_orm_kwargs
    # (e.g. _convert_table_fields) can look up the data source's table fields.
    ds = element_create.data_source
    if isinstance(ds, str) and ds in data_source_ref_to_id_map:
        element_create.data_source = data_source_ref_to_id_map[ds]
    # An id sent as text, such as "12", still names an existing data source.
    elif isinstance(ds, str) and not ds.strip().isdecimal():
        raise UnknownRefError(
            f"Unknown data source ref '{ds}'. Refs only work inside one call; use the "
            "data source ID from list_data_sources.",
            f"Data source ref '{ds}' not found. Create the data source with "
            "create_data_sources first, or use an id from list_data_sources. No "
            "changes were applied.",
        )
    # Checked before to_orm_kwargs, which reads the data source's table fields.
    if element_create.data_source is not None:
        check_data_source_on_page(page, int(element_create.data_source))
    if prepare is not None:
        prepare(element_create)

    # In place: a formula's field names its parameter by position in this list.
    element_create.link_page_parameters = parameters_in_page_order(
        page.builder_id,
        element_create.navigate_to_page_id,
        element_create.link_page_parameters,
    )
    kwargs = element_create.to_orm_kwargs(user, target_page)
    if "navigate_to_page_id" in kwargs:
        problem = page_parameters_problem(
            page.builder_id,
            kwargs["navigate_to_page_id"],
            [param["name"] for param in kwargs["page_parameters"]],
        )
        if problem:
            raise ToolInputError(
                f"{problem} Give link_page_parameters with exactly those names."
            )
    if element_create.menu_items:
        problem = menu_links_problem(
            page.builder_id, [item.page_id for item in element_create.menu_items]
        )
        if problem:
            raise ToolInputError(problem)
    if element_create.share_type == "only" and not element_create.page_ids:
        raise ToolInputError(
            "share_type 'only' needs page_ids: with no pages it is hidden everywhere."
        )
    if element_create.page_ids and element_create.share_type in (None, "all"):
        raise ToolInputError(
            "page_ids need share_type 'only' or 'except': otherwise they do nothing."
        )
    if element_create.page_ids:
        check_pages_in_builder(page.builder, element_create.page_ids)
        kwargs["pages"] = list(
            Page.objects.filter(builder=page.builder, id__in=element_create.page_ids)
        )

    # Resolve parent
    if isinstance(parent, int):
        kwargs["parent_element_id"] = parent
    elif isinstance(parent, str):
        if parent not in ref_to_id_map:
            raise UnknownRefError(
                f"Unknown ref '{parent}'. Refs only work inside one call; use the "
                "element ID.",
                f"Parent ref '{parent}' not found. "
                "Define parent elements before children.",
            )
        kwargs["parent_element_id"] = ref_to_id_map[parent]

    # A place only exists inside a container. Without a parent the element is
    # appended (or inserted north of `before`) on the default output, where a
    # slot is rejected by `validate_position` (and used to be written as a
    # stray `next` output that nothing renders), so it is only forwarded
    # together with a parent.
    if "parent_element_id" in kwargs:
        if element_create.place_in_container:
            kwargs["place_in_container"] = element_create.place_in_container
        else:
            try:
                parent = ElementHandler().get_element(
                    kwargs["parent_element_id"], base_queryset=elements
                )
                if parent.get_type().type == "column":
                    kwargs["place_in_container"] = "0"
            except Exception:
                pass
    else:
        kwargs.pop("place_in_container", None)

    # Set data_source_id in kwargs (may already be set by to_orm_kwargs)
    if isinstance(element_create.data_source, int):
        kwargs["data_source_id"] = element_create.data_source

    before = None
    if before_id is not None:
        try:
            before = ElementHandler().get_element(before_id, base_queryset=elements)
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Before element with ID {before_id} not found on this page. "
                "Use list_elements to find valid element IDs. No changes were applied."
            )
        CoreHandler().check_permissions(
            user,
            ReadElementOperationType.type,
            workspace=page.builder.workspace,
            context=before,
        )

    parent_element_id = kwargs.pop("parent_element_id", None)
    if parent_element_id is not None and (
        before is None or before.parent_element_id != parent_element_id
    ):
        reference_element_id, position, place = ElementHandler().get_end_position(
            target_page, parent_element_id, kwargs.pop("place_in_container", "") or ""
        )
        if place:
            kwargs["place_in_container"] = place
    elif before is not None:
        if (
            element_create.place_in_container
            and parent_element_id is not None
            and element_create.place_in_container != before.place_in_container
        ):
            raise ToolInputError(
                f"Element {before.id} is in place '{before.place_in_container}' of "
                f"element {parent_element_id}, not "
                f"'{element_create.place_in_container}'. Leave place_in_container "
                "out to create it before that element."
            )
        kwargs.pop("place_in_container", None)
        reference_element_id = before.id
        position = "north"
    else:
        reference_element_id = None
        position = "south"

    # A post-create hook can still be refused, e.g. a menu linking to another
    # application, and then nothing of the element is kept.
    with transaction.atomic():
        element = CreateElementActionType.do(
            user,
            element_type,
            target_page,
            {
                "reference_element_id": reference_element_id,
                "position": position,
                **kwargs,
            },
        )
        element_create.post_create(user, element, target_page)
    # Added once the element exists, so a failed one doesn't send the children of a
    # later element with the same ref to the shared page.
    if use_shared_page:
        shared_page_refs.add(element_create.ref)
    return element, element.id


# ---------------------------------------------------------------------------
# Element update
# ---------------------------------------------------------------------------


def move_element(
    user: AbstractUser,
    page: Page,
    element_move: ElementMove,
) -> Any:
    """
    Move an element to a new position/parent on its page.

    Returns the moved ORM element.
    """

    elements = Element.objects.filter(on_page(page))
    try:
        element = ElementHandler().get_element(
            element_move.element_id, base_queryset=elements
        )
    except ElementDoesNotExist:
        raise ToolInputError(
            f"Element with ID {element_move.element_id} not found. "
            "Use list_elements to find valid element IDs."
        )
    CoreHandler().check_permissions(
        user,
        UpdateElementOperationType.type,
        workspace=page.builder.workspace,
        context=element,
    )
    element = ElementHandler().get_element_for_update(element.id)

    parent = None
    if element_move.parent_element_id is not None:
        try:
            parent = ElementHandler().get_element(
                element_move.parent_element_id, base_queryset=elements
            )
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Parent element with ID {element_move.parent_element_id} not found."
            )

    before = None
    if element_move.before_id is not None:
        try:
            before = ElementHandler().get_element(
                element_move.before_id, base_queryset=elements
            )
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Before element with ID {element_move.before_id} not found."
            )

    # A place only exists inside a container. Without a parent the element
    # lands north/south of a sibling on the default output, where a slot is
    # rejected by `validate_position` (and used to be written as a stray
    # `next` output that nothing renders). The `ElementMove` schema already
    # refuses that combination; this keeps direct callers safe too.
    place = (element_move.place_in_container or "") if parent is not None else ""
    if parent is not None and not place and parent.get_type().type == "column":
        place = "0"

    if (
        parent is not None
        and before is not None
        and before.parent_element_id != parent.id
    ):
        raise ToolInputError(
            f"Element {before.id} isn't in element {parent.id}, so nothing can go "
            "before it there. Leave before_id out to move to the end."
        )

    if parent is not None and before is None:
        reference_element_id, position, place = ElementHandler().get_end_position(
            parent.page, parent.id, place
        )
        # A container's own id comes back when it is empty: the move refuses that.
        if reference_element_id == element.id and position != GraphPointPosition.CHILD:
            return element  # Already the last one there.
    elif before is not None:
        if (
            parent is not None
            and element_move.place_in_container
            and element_move.place_in_container != before.place_in_container
        ):
            raise ToolInputError(
                f"Element {before.id} is in place '{before.place_in_container}' of "
                f"element {parent.id}, not '{element_move.place_in_container}'. "
                "Leave place_in_container out to move before it."
            )
        position = "north"
        reference_element_id = before.id
        place = ""
    else:
        # before_id=None means "move to end" — append after the current last element.
        reference_element_id, position, place = ElementHandler().get_end_position(
            element.page
        )
        if reference_element_id == element.id:
            # Already at the end — no-op.
            return element

    return MoveElementActionType.do(
        user, element, element.page, place, reference_element_id, position
    )


class ElementUpdateOutcome(NamedTuple):
    """An updated element, its type, and the keys its type adds to the result."""

    element: Element
    element_type: str
    result: dict[str, Any]


def _accepted_update_keys(element: Element) -> set[str]:
    """
    Return the keys the element update API accepts for the element's type. They
    include the relations the type saves itself, such as a menu's items.

    :param element: The element to update.
    :return: The accepted keys.
    """

    return (
        set(ElementHandler.allowed_fields_update)
        | set(element.get_type().allowed_fields)
        | set(
            element.get_type().get_field_names(request_serializer=True, extra_params={})
        )
    )


def update_element(
    user: AbstractUser,
    page: Page,
    element_update: ElementUpdate,
) -> ElementUpdateOutcome:
    """
    Update an existing element by ID.

    The element type's hooks check the update, add what they save with it, apply
    what the element's own update doesn't save, and report on it.

    :param user: The user updating the element.
    :param page: The page the element must be on, or whose builder's shared page it
        must be on.
    :param element_update: The properties to change.
    :return: The updated element, its type, and the keys its type's hooks add to
        update_element's result.
    :raises ToolInputError: When the element doesn't exist or a property can't be
        applied. Nothing is saved then.
    :raises PermissionDenied: When the user can't update the element.
    """

    with transaction.atomic():
        try:
            element = ElementHandler().get_element_for_update(
                element_update.element_id,
                base_queryset=Element.objects.filter(on_page(page)),
            )
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Element with ID {element_update.element_id} not found. "
                "Use list_elements to find valid element IDs."
            )

        CoreHandler().check_permissions(
            user,
            UpdateElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        element_type = element.get_type().type
        hooks = element_tool_type_registry.get_for(element_type)
        kwargs = element_update.to_update_kwargs(element_type)
        allowed = _accepted_update_keys(element)
        kwargs = {name: value for name, value in kwargs.items() if name in allowed}
        prepared = hooks.prepare_update(user, element, element_update)
        kwargs.update(prepared.kwargs)
        unsupported = element_update.unsupported_fields(
            kwargs, hooks.property_aliases, hooks.properties_applied_after_update
        ) + hooks.conflicting_properties(element_update)
        if unsupported:
            supported = set(element.get_type().allowed_fields) & set(
                ElementUpdate.model_fields
            )
            supported.update(("visibility", "role_type", "roles"))
            supported.update(hooks.property_aliases)
            supported.update(hooks.properties_applied_after_update)
            raise ToolInputError(
                f"Unsupported properties for {element_type}: {', '.join(unsupported)}. "
                f"No changes were applied. {hooks.unsupported_guidance(supported)}"
            )
        # Deferred so a failed generation keeps the existing link or image.
        deferred_fields = set(
            element_update.get_formulas_to_update(element, None, element_type)
        ) | set(element_update.get_formula_dependent_fields(element_type))
        for field in deferred_fields:
            kwargs.pop(field, None)
        if kwargs:
            element = UpdateElementActionType.do(user, element, kwargs)
        after_update_result = hooks.after_update(user, element, element_update)

        result = (
            hooks.updated_result(element, element_update)
            | prepared.result
            | after_update_result
        )
        return ElementUpdateOutcome(element, element_type, result)


def child_menu(container: Element) -> MenuElement | None:
    """
    Find the menu inside a header or footer, however deeply it is nested, and lock it
    for update. Call it inside a transaction.

    :param container: The header or footer.
    :return: Its menu, locked for update, or None when it has none.
    :raises ToolInputError: When it holds more than one menu.
    """

    descendant_ids = container.page.get_graph().collect_descendant_ids(container.id)
    menus = [
        element
        for element in ElementHandler().get_elements(container.page)
        if element.id in descendant_ids and element.get_type().type == "menu"
    ]
    if len(menus) > 1:
        raise ToolInputError(
            f"{container.get_type().type.capitalize()} {container.id} holds more than "
            f"one menu: elements {[menu.id for menu in menus]}. Change one of them "
            "with update_element and that menu's element_id. No changes were applied."
        )
    return ElementHandler().get_element_for_update(menus[0].id) if menus else None


def save_child_menu(
    user: AbstractUser,
    container: Element,
    menu: MenuElement | None,
    menu_items: list[dict[str, Any]],
) -> Element:
    """
    Save a header's or footer's menu items, and create its menu when it has none.

    :param user: The user updating the header or footer, who may update it.
    :param container: The header or footer.
    :param menu: Its menu, or None to create one.
    :param menu_items: The menu's full item list, each top-level item with its
        sub-links as children.
    :return: The saved menu.
    :raises PermissionDenied: When the user can't update or create the menu.
    """

    if menu is not None:
        return UpdateElementActionType.do(user, menu, {"menu_items": menu_items})
    # A new menu has no sub-links yet, and creating one doesn't take children.
    top_level = [
        {key: value for key, value in item.items() if key != "children"}
        for item in menu_items
    ]
    return CreateElementActionType.do(
        user,
        element_type_registry.get("menu"),
        container.page,
        {
            "reference_element_id": container.id,
            "position": "child",
            "menu_items": top_level,
        },
    )


# ---------------------------------------------------------------------------
# Element style update
# ---------------------------------------------------------------------------


def update_element_style(
    user: AbstractUser,
    page: Page,
    style_update: ElementStyleUpdate,
) -> tuple[Any, str]:
    """
    Update an element's visual styles (box model + theme overrides).

    Returns ``(orm_element, element_type_str)``.
    """

    try:
        element = ElementHandler().get_element_for_update(
            style_update.element_id,
            base_queryset=Element.objects.filter(on_page(page)),
        )
    except ElementDoesNotExist:
        raise ToolInputError(
            f"Element with ID {style_update.element_id} not found. "
            "Use list_elements to find valid element IDs."
        )

    element_type = element.get_type().type
    existing_styles = getattr(element, "styles", None) or {}
    kwargs = style_update.to_update_kwargs(element_type, existing_styles)
    if kwargs:
        element = UpdateElementActionType.do(user, element, kwargs)
    else:
        CoreHandler().check_permissions(
            user,
            ReadElementOperationType.type,
            workspace=page.builder.workspace,
            context=element,
        )
    return element, element_type


# ---------------------------------------------------------------------------
# Workflow action creation
# ---------------------------------------------------------------------------


def _resolve_event(
    user: AbstractUser, page: Page, element_id: int, event: str
) -> tuple[str, Element]:
    """
    Resolve a human-friendly event name to the actual event string for
    any element type.

    Button collection fields store ``"{uid}_click"`` events. A unique
    ``"<column name>_click"`` selects a column by name, and ``"click"``
    is accepted only when there is exactly one button column. Ambiguous
    or invalid events must not attach an action to a guessed column.

    For all other elements (``ButtonElement``, ``FormContainerElement``,
    etc.) the event is returned unchanged since they use static event
    names (``"click"``, ``"submit"``, ``"after_login"``).

    :return: The event, and the element it belongs to.
    """

    try:
        element = ElementHandler().get_element(
            element_id,
            base_queryset=Element.objects.filter(on_page(page)),
        )
    except ElementDoesNotExist:
        raise ToolInputError(
            f"Element with ID {element_id} not found on this page. "
            "Use list_elements to find valid element IDs."
        )

    # Check access before exposing column names or event UIDs in a retry error.
    CoreHandler().check_permissions(
        user,
        ReadElementOperationType.type,
        workspace=element.page.builder.workspace,
        context=element,
    )

    # Check if the element has a `fields` relation to CollectionField
    # (currently TableElement; works for any future collection element).
    if not hasattr(element, "fields"):
        return event, element

    button_fields = list(element.fields.filter(type="button").order_by("order"))
    if not button_fields:
        return event, element

    if event in {f"{field.uid}_click" for field in button_fields}:
        return event, element

    if event == "click" and len(button_fields) == 1:
        return f"{button_fields[0].uid}_click", element

    if event.endswith("_click"):
        name = event.removesuffix("_click").strip().casefold()
        matching_fields = [
            field for field in button_fields if field.name.strip().casefold() == name
        ]
        if len(matching_fields) == 1:
            return f"{matching_fields[0].uid}_click", element

    name_counts = Counter(field.name.strip().casefold() for field in button_fields)
    valid_events = ", ".join(
        f"'{field.name}_click' ({field.uid}_click)"
        if name_counts[field.name.strip().casefold()] == 1
        else f"'{field.uid}_click' (column '{field.name}')"
        for field in button_fields
    )
    raise ToolInputError(
        f"Event '{event}' does not identify one button column of element {element_id}. "
        f"Use a unique column name or an exact UID event: {valid_events}. "
        "This action was not created."
    )


def _action_data_source_id(
    data_source: int | str, page: Page, data_source_ref_to_id_map: dict[str, int]
) -> int:
    """
    The ID of the data source a refresh action names.

    :param page: The page of the action's element, which decides what it can reach.
    :raises ToolInputError: When it's an unknown ref or the element can't reach it.
    """

    if isinstance(data_source, str) and data_source in data_source_ref_to_id_map:
        data_source_id = data_source_ref_to_id_map[data_source]
    # An id sent as text, such as "12", still names an existing data source.
    elif isinstance(data_source, str) and not data_source.strip().isdecimal():
        raise UnknownRefError(
            f"Unknown data source ref '{data_source}'. Refs only work inside one "
            "call; use the data source ID from list_data_sources.",
            f"Data source ref '{data_source}' not found. Create the data source with "
            "create_data_sources first, or use an id from list_data_sources.",
        )
    else:
        data_source_id = int(data_source)
    check_data_source_on_page(page, data_source_id)
    return data_source_id


def create_workflow_action(
    user: AbstractUser,
    page: Page,
    action_create: ActionCreate,
    element_ref_to_id_map: dict[str, int],
    data_source_ref_to_id_map: dict[str, int],
    integration: Integration | None = None,
) -> tuple[Any, int]:
    """Create a workflow action attached to an element."""

    # Resolve element
    el = action_create.element
    if isinstance(el, int):
        element_id = el
    elif isinstance(el, str):
        if el not in element_ref_to_id_map:
            raise UnknownRefError(
                f"Unknown ref '{el}'. Refs only work inside one call; use the element "
                "ID.",
                f"Element ref '{el}' not found.",
            )
        element_id = element_ref_to_id_map[el]
    else:
        raise ValueError("element is required for workflow actions.")

    action_type = builder_workflow_action_type_registry.get(
        action_create.get_action_type()
    )

    # Resolve human-friendly event names (e.g. "click" → "{uid}_click"
    # for collection elements with button fields).
    event, element = _resolve_event(user, page, element_id, action_create.event)

    kwargs: dict[str, Any] = {
        "element_id": element_id,
        "event": event,
    }
    # In place: a formula's field names its parameter by position in this list.
    action_create.page_parameters = parameters_in_page_order(
        page.builder_id,
        action_create.navigate_to_page_id,
        action_create.page_parameters,
    )
    kwargs.update(action_create.to_orm_kwargs())

    service_kwargs = action_create.to_service_kwargs(user, page.builder.workspace)
    if service_kwargs is not None:
        if integration:
            service_kwargs["integration"] = integration
        field_mappings = action_create.get_field_mappings()
        if field_mappings:
            service_kwargs["field_mappings"] = field_mappings
        kwargs["service"] = service_kwargs

    if action_create.type == "refresh_data_source":
        kwargs["data_source_id"] = _action_data_source_id(
            action_create.data_source, element.page, data_source_ref_to_id_map
        )
    # An element's actions are read from the page it is on, so a header's button
    # keeps its action on the shared page.
    action = CreateBuilderWorkflowActionActionType.do(
        user, action_type, element.page, **kwargs
    )
    return action, action.id


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


def get_writable_action(
    user: AbstractUser, workspace: Workspace, action_id: int
) -> BuilderWorkflowAction:
    """
    Get a workflow action of the workspace the user can read and update.

    :raises ToolInputError: When it is missing, or its page or application is trashed
        or in another workspace.
    :raises PermissionException: When the user can't read or update it.
    """

    try:
        action = (
            BuilderWorkflowAction.objects.filter(
                page__trashed=False,
                page__builder__workspace=workspace,
                page__builder__trashed=False,
            )
            .get(id=action_id)
            .specific
        )
    except BuilderWorkflowAction.DoesNotExist:
        raise ToolInputError(
            f"Action with ID {action_id} not found in this workspace. "
            "List the page's actions to find valid action IDs."
        )
    for operation_type in (
        ReadBuilderWorkflowActionOperationType,
        UpdateBuilderWorkflowActionOperationType,
    ):
        CoreHandler().check_permissions(
            user, operation_type.type, workspace=workspace, context=action
        )
    return action


def page_parameters_problem(
    builder_id: int, page_id: int | None, names: list[str]
) -> str | None:
    """
    Why page parameters with these names don't fit the page they open, if so.

    :param builder_id: The application the page must be in.
    :param page_id: The page they open.
    :param names: The names of the parameters.
    :return: The problem, or None when they fit or the page isn't in the application,
        which is left to the writer.
    """

    page = Page.objects.filter(id=page_id, builder_id=builder_id).first()
    if page is None:
        return None
    expected = [param["name"] for param in page.path_params or []]
    missing = [name for name in expected if name not in names]
    unknown = [name for name in dict.fromkeys(names) if name not in expected]
    # The frontend hides a link or button whose list has a name twice.
    repeated = [name for name in dict.fromkeys(names) if names.count(name) > 1]
    if not missing and not unknown and not repeated:
        return None
    problems = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if unknown:
        problems.append(f"unknown: {', '.join(unknown)}")
    if repeated:
        problems.append(f"repeated: {', '.join(repeated)}")
    return (
        f"The page parameters don't fit page {page.id}, which takes "
        f"{', '.join(expected) or 'none'} ({'; '.join(problems)})."
    )


def menu_links_problem(builder_id: int, page_ids: list[int]) -> str | None:
    """
    Why menu items can't link to these pages, if so. The tools can't give a menu item
    path parameters, only the editor can, and the frontend hides a menu with an item
    that lacks them.

    :param builder_id: The application the pages must be in.
    :param page_ids: The pages the items link to.
    :return: The problem, or None when they can.
    """

    for page in Page.objects.filter(builder_id=builder_id, id__in=page_ids):
        if page.path_params:
            names = ", ".join(param["name"] for param in page.path_params)
            return (
                f"Page {page.id} has path parameters ({names}), which these tools "
                "can't give a menu item, so visitors wouldn't see the menu. Link to a "
                "page without path parameters, create a link element with "
                "link_page_parameters, or add the item in the editor and set its page "
                "parameters there."
            )
    return None


def check_open_page_parameters(
    action: BuilderWorkflowAction, item: ActionCreate | ActionUpdate
) -> None:
    """
    Check that the page parameters an open_page create or update leaves on the action
    are the ones the page it opens has. Only a call that gives the page or the
    parameters is checked. A page that isn't in the action's application is left to
    the writer, and so is an action that goes to a custom URL.

    :raises ToolInputError: When parameters are missing or unknown.
    """

    if item.type != "open_page" or (
        item.page_parameters is None and item.navigate_to_page_id is None
    ):
        return

    if item.navigate_to_page_id is None and (
        getattr(action, "navigation_type", None) == "custom"
    ):
        return

    page_id = item.navigate_to_page_id or getattr(action, "navigate_to_page_id", None)
    if item.page_parameters is not None:
        names = [param.name for param in item.page_parameters]
    else:
        names = [param["name"] for param in action.page_parameters or []]

    problem = page_parameters_problem(action.page.builder_id, page_id, names)
    if problem:
        raise ToolInputError(
            f"{problem} Give page_parameters with exactly those names, or an empty "
            "list if it takes none."
        )


def update_workflow_action(
    user: AbstractUser,
    workspace: Workspace,
    action: BuilderWorkflowAction,
    item: ActionUpdate,
) -> None:
    """
    Store the changes to an action that the formula step doesn't, in one transaction.

    :raises ToolInputError: When a value can't be used on this action.
    """

    from baserow.contrib.builder.workflow_actions.actions import (
        UpdateBuilderWorkflowActionActionType,
    )

    if item.data_source is not None:
        page = action.element.page if action.element_id else action.page
        check_data_source_on_page(page, item.data_source)
    check_open_page_parameters(action, item)

    with transaction.atomic():
        fresh = BuilderWorkflowActionHandler().get_workflow_action_for_update(action)
        values = item.update_values(fresh, user, workspace)
        if values:
            UpdateBuilderWorkflowActionActionType.do(user, fresh, **values)


def _mappable_service(action, action_id: int, field_id: int):
    """
    The service of a create_row or update_row action, after checking the field is
    one of its table's and can take a value.
    """

    action_type = action.get_type().type
    if action_type not in ("create_row", "update_row"):
        raise ToolInputError(
            f"Cannot add field mappings to '{action_type}'. "
            "Only create_row and update_row support field mappings."
        )

    service = action.service.specific
    if not service.table_id:
        raise ToolInputError(
            f"Action {action_id} has no table selected, so it has no fields to map. "
            "This tool cannot select a table. Until one is selected, the action will fail."
        )

    field = (
        Field.objects_and_trash.select_related("content_type")
        .filter(id=field_id, table_id=service.table_id)
        .first()
    )
    if field is None:
        raise ToolInputError(
            f"Field {field_id} is not in the table this action writes to. "
            "Use the IDs of that table's fields."
        )
    raise_if_read_only_field(field)
    return service


def add_field_mapping_to_action(
    user: AbstractUser,
    workspace: Workspace,
    action_id: int,
    field_id: int,
    value_formula: str,
) -> dict[str, Any]:
    """Add or update a field mapping on a create_row/update_row workflow action."""

    from baserow.contrib.builder.workflow_actions.actions import (
        UpdateBuilderWorkflowActionActionType,
    )
    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
    from baserow.core.tools.formula_utils import formula_object

    action = get_writable_action(user, workspace, action_id)
    value = formula_object(value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED)

    # The service replaces its whole list of mappings, so its lock makes a
    # concurrent addition wait for this one, and the transaction keeps the old list
    # if the replacement fails. The checks run on the action as loaded after the
    # lock, so an editor's change of its table or type is seen.
    with transaction.atomic():
        try:
            action = BuilderWorkflowActionHandler().get_workflow_action_for_update(
                action
            )
        except WorkflowActionDoesNotExist:
            raise ToolInputError(
                f"Action {action_id} was deleted or changed type while it was "
                "updated. List the element's actions again."
            )
        service = _mappable_service(action, action_id, field_id)
        status = (
            "updated"
            if LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
                service=service, field_id=field_id
            ).exists()
            else "created"
        )
        if status == "created" and not Field.objects.filter(id=field_id).exists():
            raise ToolInputError(
                f"Field {field_id} is in the trash, so it can't get a new value. "
                "Use another field of the table, or restore it first."
            )
        field_mappings = service.get_type().field_mappings_with(
            service, {field_id: value}, enable=True
        )
        action = UpdateBuilderWorkflowActionActionType.do(
            user, action, service={"field_mappings": field_mappings}
        )
    service = action.service.specific

    mappings = [
        {
            "field_id": m.field_id,
            "field_name": m.field.name,
            "value": str(m.value) if m.value else "",
        }
        for m in service.field_mappings.all()
    ]

    return {"status": status, "field_mappings": mappings}
