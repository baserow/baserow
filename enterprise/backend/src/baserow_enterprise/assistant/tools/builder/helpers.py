"""
Shared helpers for the builder assistant tools.

Contains permission-checked accessors, listing functions, and the element/data
source/action creation orchestrators used by ``tools.py`` and ``agents.py``.
"""

from collections import Counter
from typing import TYPE_CHECKING, Any, NamedTuple

from django.contrib.auth.models import AbstractUser
from django.db.models import Q

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    MoveElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element, TableElement
from baserow.contrib.builder.elements.operations import (
    ReadElementOperationType,
    UpdateElementOperationType,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.operations import ListPagesBuilderOperationType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    raise_if_permission_denied,
)

from .table_column_changes import merge_table_columns
from .types import (
    ActionCreate,
    ActionItem,
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
    RemovedTableColumn,
    TableColumnItem,
)
from .types.element import BUTTON_NAVIGATION_GUIDANCE, TABLE_COLUMN_PROPERTIES
from .types.table_columns import table_column_items

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_builder(
    user: AbstractUser, workspace: Workspace, application_id: int
) -> Builder:
    """
    Get a builder application scoped to the user's workspace.

    :param user: The acting user.
    :param workspace: The workspace the application must belong to.
    :param application_id: The ID of the application to fetch.
    :returns: The matching builder application.
    :raises ToolInputError: When the application is not visible in the
        workspace.
    """

    from baserow.core.service import CoreService

    try:
        return CoreService().get_application(
            user,
            application_id,
            base_queryset=Builder.objects.filter(workspace=workspace),
        )
    except Exception as exc:
        raise_if_permission_denied(exc)
        raise ToolInputError(
            f"Application with ID {application_id} not found in this workspace. "
            "Use list_builders to find valid application IDs."
        )


def get_page(user: AbstractUser, page_id: int) -> Page:
    """
    Get a page with permission check.

    :param user: The acting user.
    :param page_id: The ID of the page to fetch.
    :returns: The matching page.
    :raises ToolInputError: When the page is missing or not accessible.
    """

    try:
        return PageService().get_page(user, page_id)
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

    local_baserow_type = integration_type_registry.get("local_baserow")
    return IntegrationService().create_integration(
        user, local_baserow_type, builder, name="Local Baserow"
    )


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


def list_elements(user: AbstractUser, page: Page) -> list[ElementItem]:
    """List all elements on a page, including shared elements visible on it."""
    elements = list(ElementService().get_elements(user, page))

    # Also include shared elements (headers/footers) visible on this page
    if not page.shared:
        shared_page = page.builder.shared_page
        shared_elements = ElementService().get_elements(user, shared_page)
        elements = list(shared_elements) + elements

    return [ElementItem.from_orm(el) for el in elements]


def list_workflow_actions(user: AbstractUser, page: Page) -> list[ActionItem]:
    """List all workflow actions on a page."""
    return [
        ActionItem.from_orm(a)
        for a in BuilderWorkflowActionService().get_workflow_actions(user, page)
    ]


# ---------------------------------------------------------------------------
# Page creation
# ---------------------------------------------------------------------------


def create_page(user: AbstractUser, builder: Builder, page_create: PageCreate) -> Page:
    """Create a page in a builder application."""

    from baserow.contrib.builder.pages.service import PageService

    svc = PageService()
    page = svc.create_page(
        user,
        builder,
        page_create.name,
        page_create.path,
        path_params=[p.model_dump() for p in page_create.path_params],
        query_params=[p.model_dump() for p in page_create.query_params],
    )

    # PageService.create_page doesn't accept visibility/role kwargs,
    # so we update them separately if non-default.
    update_kwargs: dict = {}
    if page_create.visibility != "all":
        update_kwargs["visibility"] = page_create.visibility
    if page_create.role_type != "allow_all":
        update_kwargs["role_type"] = page_create.role_type
    if page_create.roles:
        update_kwargs["roles"] = page_create.roles
    if update_kwargs:
        page = svc.update_page(user, page, **update_kwargs)

    return page


# ---------------------------------------------------------------------------
# Page update
# ---------------------------------------------------------------------------


def update_page(
    user: AbstractUser,
    page_update: PageUpdate,
) -> Page:
    """
    Update an existing page by ID.

    Returns the updated page.
    """

    from baserow.contrib.builder.pages.service import PageService

    page = get_page(user, page_update.page_id)
    kwargs = page_update.to_update_kwargs()
    if kwargs:
        PageService().update_page(user, page, **kwargs)
        page.refresh_from_db()
    return page


# ---------------------------------------------------------------------------
# Data source creation
# ---------------------------------------------------------------------------


def create_data_source(
    user: AbstractUser,
    page: Page,
    ds_create: DataSourceCreate,
    integration: Integration,
) -> tuple[Any, int]:
    """Create a data source on a page."""

    service_type = service_type_registry.get(ds_create.get_service_type())
    service_kwargs = ds_create.to_service_kwargs(user, page.builder.workspace)
    service_kwargs["integration"] = integration

    data_source = DataSourceService().create_data_source(
        user=user,
        page=page,
        name=ds_create.name,
        service_type=service_type,
        **service_kwargs,
    )

    # Add sortings
    sortings = ds_create.get_sortings()
    if sortings:
        from baserow.contrib.integrations.local_baserow.models import (
            LocalBaserowTableServiceSort,
        )

        LocalBaserowTableServiceSort.objects.bulk_create(
            [
                LocalBaserowTableServiceSort(
                    service=data_source.service,
                    field_id=s["field_id"],
                    order_by=s["order_by"],
                    order=i,
                )
                for i, s in enumerate(sortings)
            ]
        )

    return data_source, data_source.id


# ---------------------------------------------------------------------------
# Data source update
# ---------------------------------------------------------------------------


def update_data_source(
    user: AbstractUser,
    ds_update: DataSourceUpdate,
    workspace: Any,
) -> tuple[Any, str]:
    """
    Update an existing data source by ID.

    :param user: The acting user.
    :param ds_update: The update definition.
    :param workspace: The workspace the referenced tables must belong to.
    :returns: ``(orm_data_source, service_type_str)``.
    :raises ToolInputError: When the data source does not exist.
    """

    from baserow.core.services.registries import service_type_registry

    try:
        ds = DataSourceHandler().get_data_source_for_update(ds_update.data_source_id)
    except Exception as exc:
        raise_if_permission_denied(exc)
        raise ToolInputError(
            f"Data source with ID {ds_update.data_source_id} not found. "
            "Use list_data_sources to find valid data source IDs."
        )

    service_type = (
        service_type_registry.get_by_model(ds.service.specific) if ds.service else None
    )
    kwargs = ds_update.to_update_kwargs(user, workspace)
    if kwargs:
        ds = (
            DataSourceService()
            .update_data_source(user, ds, service_type=service_type, **kwargs)
            .data_source
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
) -> tuple[Any, int, list]:
    """
    Create an element on a page, resolving refs to IDs.

    Returns ``(orm_element, element_id, action_pairs)`` where
    *action_pairs* is a list of ``(orm_action, action_create)`` tuples
    produced by post-create hooks (e.g. table button columns).
    """

    if shared_page_refs is None:
        shared_page_refs = set()

    element_type = element_type_registry.get(element_create.type)

    # Determine target page
    use_shared_page = element_create.use_shared_page
    parent = element_create.parent_element
    if isinstance(parent, str) and parent in shared_page_refs:
        use_shared_page = True
    elif isinstance(parent, int):
        # Check if the parent element lives on the shared page
        try:
            parent_el = ElementHandler().get_element(parent)
            if parent_el.page.shared:
                use_shared_page = True
        except Exception:
            pass

    target_page = page.builder.shared_page if use_shared_page else page
    if use_shared_page:
        shared_page_refs.add(element_create.ref)

    # Resolve data source ref to integer ID early so that to_orm_kwargs
    # (e.g. _convert_table_fields) can look up the data source's table fields.
    ds = element_create.data_source
    if isinstance(ds, str) and ds in data_source_ref_to_id_map:
        element_create.data_source = data_source_ref_to_id_map[ds]
    # An id sent as text, such as "12", still names an existing data source.
    elif isinstance(ds, str) and not ds.strip().isdecimal():
        raise ToolInputError(
            f"Data source ref '{ds}' not found. Create the data source with "
            "create_data_sources first, or use an id from list_data_sources. No "
            "changes were applied."
        )

    kwargs = element_create.to_orm_kwargs(user, target_page)

    # Resolve parent
    if isinstance(parent, int):
        kwargs["parent_element_id"] = parent
    elif isinstance(parent, str):
        if parent not in ref_to_id_map:
            raise ValueError(
                f"Parent ref '{parent}' not found. "
                "Define parent elements before children."
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
                parent = ElementHandler().get_element(kwargs["parent_element_id"])
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
            before = ElementService().get_element(user, before_id)
        except ElementDoesNotExist:
            pass

    parent_element_id = kwargs.pop("parent_element_id", None)
    if parent_element_id is not None:
        reference_element_id = parent_element_id
        position = "child"
    elif before is not None:
        reference_element_id = before.id
        position = "north"
    else:
        reference_element_id = None
        position = "south"

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

    action_pairs = element_create.post_create(user, element, target_page)
    return element, element.id, action_pairs


# ---------------------------------------------------------------------------
# Element update
# ---------------------------------------------------------------------------


def move_element(
    user: AbstractUser,
    element_move: ElementMove,
) -> Any:
    """
    Move an element to a new position/parent on its page.

    Returns the moved ORM element.
    """

    try:
        element = ElementHandler().get_element_for_update(element_move.element_id)
    except ElementDoesNotExist:
        raise ToolInputError(
            f"Element with ID {element_move.element_id} not found. "
            "Use list_elements to find valid element IDs."
        )

    parent = None
    if element_move.parent_element_id is not None:
        try:
            parent = ElementHandler().get_element(element_move.parent_element_id)
        except ElementDoesNotExist:
            raise ToolInputError(
                f"Parent element with ID {element_move.parent_element_id} not found."
            )

    before = None
    if element_move.before_id is not None:
        try:
            before = ElementHandler().get_element(element_move.before_id)
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

    if parent is not None:
        position = "child"
        reference_element_id = parent.id
    elif before is not None:
        position = "north"
        reference_element_id = before.id
    else:
        # before_id=None means "move to end" — append after the current last element.
        from baserow.core.cache import local_cache

        element.page.refresh_from_db()
        with local_cache.context():
            last_ref, _, _ = element.page.get_graph().get_last_position()

        if last_ref is not None and last_ref.id == element.id:
            # Already at the end — no-op.
            return element

        position = "south"
        reference_element_id = last_ref.id if last_ref is not None else None

    return MoveElementActionType.do(
        user, element, element.page, place, reference_element_id, position
    )


class ElementUpdateOutcome(NamedTuple):
    """An updated element, and for table column changes the columns afterwards."""

    element: Element
    element_type: str
    table_columns: list[TableColumnItem] | None
    removed_table_columns: list[RemovedTableColumn] | None


def update_element(
    user: AbstractUser,
    element_update: ElementUpdate,
) -> ElementUpdateOutcome:
    """
    Update an existing element by ID.

    If the element is a header/footer and ``menu_items`` are provided,
    automatically finds or creates a child menu element and sets the
    items on it (headers are containers, not menus themselves). Table column
    changes are merged into the stored columns, so the columns they don't name
    are saved unchanged.

    :param user: The user updating the element.
    :param element_update: The properties to change.
    :return: The updated element and its type, plus the table's columns after the
        write and the removed columns when the update changes table columns.
    :raises ToolInputError: When the element doesn't exist or a property can't be
        applied. Nothing is saved then.
    :raises PermissionDenied: When the user can't update the element.
    """

    try:
        element = ElementHandler().get_element_for_update(element_update.element_id)
    except ElementDoesNotExist:
        raise ToolInputError(
            f"Element with ID {element_update.element_id} not found. "
            "Use list_elements to find valid element IDs."
        )

    element_type = element.get_type().type
    kwargs = element_update.to_update_kwargs(element_type)
    changes_table_columns = (
        element_type == "table" and element_update.changes_table_columns()
    )
    removed_columns = None
    if changes_table_columns:
        CoreHandler().check_permissions(
            user,
            UpdateElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )
        change = merge_table_columns(
            element.specific,
            add=element_update.add_table_columns or [],
            update=element_update.update_table_columns or [],
            reorder=element_update.reorder_table_columns,
            remove=element_update.remove_table_columns or [],
        )
        kwargs["fields"] = change.fields
        removed_columns = change.removed
    allowed = set(ElementHandler.allowed_fields_update) | set(
        element.get_type().allowed_fields
    )
    # These relations are consumed by the element type's after_update hook,
    # rather than assigned as model fields by ElementHandler.
    allowed.update(
        {"table": {"fields"}, "menu": {"menu_items"}}.get(element_type, set())
    )
    kwargs = {name: value for name, value in kwargs.items() if name in allowed}
    unsupported = element_update.unsupported_fields(element_type, kwargs)
    if unsupported:
        if element_type == "button":
            guidance = BUTTON_NAVIGATION_GUIDANCE
        else:
            allowed = set(element.get_type().allowed_fields) & set(
                ElementUpdate.model_fields
            )
            allowed.update(("visibility", "role_type", "roles"))
            if element_type == "table":
                allowed.update(TABLE_COLUMN_PROPERTIES)
            guidance = f"Supported properties include: {', '.join(sorted(allowed))}."
        raise ToolInputError(
            f"Unsupported properties for {element_type}: {', '.join(unsupported)}. "
            f"No changes were applied. {guidance}"
        )
    # Save generated values and their source switches together after validation,
    # so failed generation preserves the existing link/image behavior.
    deferred_fields = set(
        element_update.get_formulas_to_update(element, None, element_type)
    ) | set(element_update.get_formula_dependent_fields(element_type))
    for field in deferred_fields:
        kwargs.pop(field, None)
    if kwargs:
        element = UpdateElementActionType.do(user, element, kwargs)

    # Headers/footers are containers — menu_items belong on a child menu.
    if element_type in ("header", "footer") and element_update.menu_items is not None:
        _ensure_child_menu(user, element, element_update)

    table_columns = (
        table_column_items(
            TableElement.objects.prefetch_related("fields").get(id=element.id)
        )
        if changes_table_columns
        else None
    )
    return ElementUpdateOutcome(element, element_type, table_columns, removed_columns)


def _ensure_child_menu(
    user: AbstractUser,
    header_element: Any,
    element_update: ElementUpdate,
) -> None:
    """Find or create a menu element inside a header/footer, then set its items."""

    import uuid

    handler = ElementHandler()
    children = handler.get_elements(header_element.page)
    menu_child = None
    for child in children:
        if (
            child.parent_element_id == header_element.id
            and child.get_type().type == "menu"
        ):
            menu_child = child
            break

    menu_items_orm = [
        {
            "uid": str(uuid.uuid4()),
            "type": "link",
            "variant": "link",
            "name": item.name,
            "navigation_type": "page",
            "navigate_to_page_id": item.page_id,
            "target": "self",
        }
        for item in element_update.menu_items
    ]

    if menu_child is not None:
        UpdateElementActionType.do(user, menu_child, {"menu_items": menu_items_orm})
    else:
        menu_type = element_type_registry.get("menu")
        CreateElementActionType.do(
            user,
            menu_type,
            header_element.page,
            {
                "reference_element_id": header_element.id,
                "position": "child",
                "menu_items": menu_items_orm,
            },
        )


# ---------------------------------------------------------------------------
# Element style update
# ---------------------------------------------------------------------------


def update_element_style(
    user: AbstractUser,
    style_update: ElementStyleUpdate,
) -> tuple[Any, str]:
    """
    Update an element's visual styles (box model + theme overrides).

    Returns ``(orm_element, element_type_str)``.
    """

    try:
        element = ElementHandler().get_element_for_update(style_update.element_id)
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
    return element, element_type


# ---------------------------------------------------------------------------
# Workflow action creation
# ---------------------------------------------------------------------------


def _resolve_event(user: AbstractUser, page: Page, element_id: int, event: str) -> str:
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
    """

    try:
        element = ElementHandler().get_element(
            element_id,
            base_queryset=Element.objects.filter(
                Q(page=page) | Q(page__builder=page.builder, page__shared=True)
            ),
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
        return event

    button_fields = list(element.fields.filter(type="button").order_by("order"))
    if not button_fields:
        return event

    if event in {f"{field.uid}_click" for field in button_fields}:
        return event

    if event == "click" and len(button_fields) == 1:
        return f"{button_fields[0].uid}_click"

    if event.endswith("_click"):
        name = event.removesuffix("_click").strip().casefold()
        matching_fields = [
            field for field in button_fields if field.name.strip().casefold() == name
        ]
        if len(matching_fields) == 1:
            return f"{matching_fields[0].uid}_click"

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
            raise ValueError(f"Element ref '{el}' not found.")
        element_id = element_ref_to_id_map[el]
    else:
        raise ValueError("element is required for workflow actions.")

    action_type = builder_workflow_action_type_registry.get(
        action_create.get_action_type()
    )

    # Resolve human-friendly event names (e.g. "click" → "{uid}_click"
    # for collection elements with button fields).
    event = _resolve_event(user, page, element_id, action_create.event)

    kwargs: dict[str, Any] = {
        "page": page,
        "element_id": element_id,
        "event": event,
    }
    kwargs.update(action_create.to_orm_kwargs())

    service_kwargs = action_create.to_service_kwargs(user, page.builder.workspace)
    if service_kwargs is not None:
        if integration:
            service_kwargs["integration"] = integration
        field_mappings = action_create.get_field_mappings()
        if field_mappings:
            service_kwargs["field_mappings"] = field_mappings
        kwargs["service"] = service_kwargs

    # Resolve data source for refresh_data_source
    ds = action_create.data_source
    if isinstance(ds, str) and ds in data_source_ref_to_id_map:
        kwargs["data_source_id"] = data_source_ref_to_id_map[ds]
    elif isinstance(ds, int):
        kwargs["data_source_id"] = ds

    action = BuilderWorkflowActionService().create_workflow_action(
        user, action_type, **kwargs
    )
    return action, action.id


def create_table_button_actions(
    user: AbstractUser,
    page: Page,
    orm_element: Any,
    element_create: ElementItemCreate,
    integration: Integration | None = None,
) -> list[tuple[Any, Any]]:
    """
    Create workflow actions for button columns in a table element.

    Maps button fields to their collection field UIDs and creates actions
    with ``event="{uid}_click"``.
    """

    if not element_create.fields:
        return []

    collection_fields = list(orm_element.fields.order_by("order"))
    created = []

    for i, field_cfg in enumerate(element_create.fields or []):
        if field_cfg.type != "button":
            continue
        if i >= len(collection_fields):
            continue

        # Button columns don't have inline workflow_actions in the flat model,
        # so this hook is a placeholder for future extension.
        # The ab-tools-no-loaders branch used discriminated union button configs
        # with embedded workflow_actions — we don't replicate that here since
        # workflow actions are created separately via create_actions tool.

    return created


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


def add_field_mapping_to_action(
    user: AbstractUser, action_id: int, field_id: int, value_formula: str
) -> dict[str, Any]:
    """Add or update a field mapping on a create_row/update_row workflow action."""

    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
    from baserow_enterprise.assistant.tools.shared.formula_utils import formula_object

    action = BuilderWorkflowActionService().get_workflow_action(user, action_id)
    action_type = action.get_type().type

    if action_type not in ("create_row", "update_row"):
        raise ValueError(
            f"Cannot add field mappings to '{action_type}'. "
            "Only create_row and update_row support field mappings."
        )

    service = action.service.specific

    existing = LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
        service=service, field_id=field_id
    ).first()

    if existing:
        existing.value = formula_object(
            value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
        )
        existing.enabled = True
        existing.save()
        status = "updated"
    else:
        LocalBaserowTableServiceFieldMapping.objects.create(
            service=service,
            field_id=field_id,
            value=formula_object(value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED),
            enabled=True,
        )
        status = "created"

    mappings = [
        {
            "field_id": m.field_id,
            "field_name": m.field.name,
            "value": str(m.value) if m.value else "",
        }
        for m in service.field_mappings.all()
    ]

    return {"status": status, "field_mappings": mappings}


# ---------------------------------------------------------------------------
# User source helpers
# ---------------------------------------------------------------------------


def create_users_table(
    user: AbstractUser,
    database_id: int,
    workspace: Workspace,
    roles: list[str],
):
    """
    Create a new users table with Name, Email, Password, and Role fields.

    :returns: (table, field_map) where field_map has keys
              "name", "email", "password", "role".
    """

    from baserow.contrib.database.fields.actions import CreateFieldActionType
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.models import Database
    from baserow.contrib.database.table.actions import CreateTableActionType

    database = (
        CoreService()
        .list_applications_in_workspace(
            user, workspace, base_queryset=Database.objects.filter(id=database_id)
        )
        .first()
    )
    if not database:
        raise ValueError(f"Database with ID {database_id} not found in this workspace.")
    table, _ = CreateTableActionType.do(user, database, "Users", fill_example=False)

    # The table comes with a primary "Name" text field already
    name_field = Field.objects.get(table=table, primary=True)

    email_field = CreateFieldActionType.do(user, table, "email", name="Email")
    password_field = CreateFieldActionType.do(user, table, "password", name="Password")
    role_field = CreateFieldActionType.do(
        user,
        table,
        "single_select",
        name="Role",
        select_options=[{"value": r, "color": "blue"} for r in roles],
    )

    # Add example users, one per role
    from baserow.contrib.database.rows.actions import CreateRowsActionType

    role_options = {opt.value: opt.id for opt in role_field.select_options.all()}
    example_rows = []
    for i, role_name in enumerate(roles, start=1):
        example_rows.append(
            {
                name_field.db_column: role_name,
                email_field.db_column: f"{role_name.lower()}@example.com",
                role_field.db_column: role_options.get(role_name),
            }
        )
    if example_rows:
        CreateRowsActionType.do(user, table, example_rows, model=table.get_model())

    return table, {
        "name": name_field,
        "email": email_field,
        "password": password_field,
        "role": role_field,
        "hint": "Remember to set a password for each user to enable login!",
    }


def resolve_existing_table(
    user: AbstractUser,
    workspace: Workspace,
    table_id: int,
):
    """
    Validate an existing table for use as a user source.

    Auto-detects email, name, password, and role fields by type and name.
    Creates a password field if one doesn't exist.

    :returns: (table, field_map) with keys "name", "email", "password",
              and optionally "role".
    :raises ValueError: If required fields can't be detected.
    """

    from baserow.contrib.database.fields.actions import CreateFieldActionType
    from baserow.contrib.database.fields.models import (
        EmailField,
        Field,
        LongTextField,
        PasswordField,
        SingleSelectField,
        TextField,
    )
    from baserow.core.db import specific_iterator
    from baserow_enterprise.assistant.tools.database.helpers import filter_tables

    table = filter_tables(user, workspace).get(id=table_id)

    fields_qs = Field.objects.filter(table=table).order_by("order", "id")
    fields = list(specific_iterator(fields_qs.select_related("content_type")))

    field_map: dict[str, Any] = {}

    for field in fields:
        name_lower = field.name.lower()

        if "email" not in field_map:
            if isinstance(field, EmailField):
                field_map["email"] = field
            elif (
                isinstance(field, (TextField, LongTextField)) and "email" in name_lower
            ):
                field_map["email"] = field

        if "name" not in field_map:
            if isinstance(field, TextField) and "name" in name_lower:
                field_map["name"] = field

        if "password" not in field_map:
            if isinstance(field, PasswordField):
                field_map["password"] = field

        if "role" not in field_map:
            if isinstance(field, SingleSelectField) and "role" in name_lower:
                field_map["role"] = field
            elif isinstance(field, TextField) and "role" in name_lower:
                field_map["role"] = field

    # Fall back to primary field for name
    if "name" not in field_map:
        for field in fields:
            if field.primary:
                field_map["name"] = field
                break

    missing = []
    if "email" not in field_map:
        missing.append("email (EmailField or TextField with 'email' in name)")
    if "name" not in field_map:
        missing.append("name (TextField with 'name' in name, or a primary field)")
    if missing:
        raise ValueError(
            f"Table '{table.name}' is missing required fields: {', '.join(missing)}"
        )

    # Create password field if missing
    if "password" not in field_map:
        field_map["password"] = CreateFieldActionType.do(
            user, table, "password", name="Password"
        )

    return table, field_map


def create_user_source(
    user: AbstractUser,
    application: Builder,
    name: str,
    table,
    field_map: dict,
    integration: Integration,
):
    """
    Create a Local Baserow user source with password authentication.

    :param field_map: Must have "name", "email", "password"; optionally "role".
    :returns: The created user source.
    """

    from baserow.core.user_sources.registries import user_source_type_registry
    from baserow.core.user_sources.service import UserSourceService

    us_type = user_source_type_registry.get("local_baserow")

    kwargs: dict[str, Any] = {
        "name": name,
        "table_id": table.id,
        "integration": integration,
        "email_field_id": field_map["email"].id,
        "name_field_id": field_map["name"].id,
        "auth_providers": [
            {
                "type": "local_baserow_password",
                "password_field_id": field_map["password"].id,
            }
        ],
    }

    if "role" in field_map:
        kwargs["role_field_id"] = field_map["role"].id

    return UserSourceService().create_user_source(user, us_type, application, **kwargs)


def create_login_page(
    user: AbstractUser, builder: Builder, user_source_id: int
) -> Page:
    """
    Create a login page with an auth_form element and set it as the
    builder's login page.
    """

    from baserow.contrib.builder.elements.registries import element_type_registry
    from baserow.contrib.builder.pages.service import PageService
    from baserow.core.handler import CoreHandler

    page = PageService().create_page(user, builder, "Login", "/login")

    auth_form_type = element_type_registry.get("auth_form")
    CreateElementActionType.do(
        user, auth_form_type, page, {"user_source_id": user_source_id}
    )

    CoreHandler().update_application(user, builder, login_page_id=page.id)
    builder.refresh_from_db()
    return page
