"""
Shared helpers for the builder assistant tools.

Contains permission-checked accessors, listing functions, and the element/data
source/action creation orchestrators used by ``tools.py`` and ``agents.py``.
"""

from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.models import Workspace
from baserow.core.services.registries import service_type_registry

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
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_builder(
    user: AbstractUser, workspace: Workspace, application_id: int
) -> Builder:
    """Get a builder application scoped to the user's workspace."""

    from baserow.core.service import CoreService

    try:
        return CoreService().get_application(
            user,
            application_id,
            base_queryset=Builder.objects.filter(workspace=workspace),
        )
    except Exception:
        raise ToolInputError(
            f"Application with ID {application_id} not found in this workspace. "
            "Use list_builders to find valid application IDs."
        )


class ToolInputError(Exception):
    """Raised when tool input is invalid — returned to the model as an error message."""


def get_page(user: AbstractUser, page_id: int) -> Page:
    """Get a page with permission check."""

    try:
        page = PageHandler().get_page(page_id)
    except Exception:
        raise ToolInputError(
            f"Page with ID {page_id} not found. Use list_pages to find valid page IDs."
        )
    try:
        CoreHandler().check_permissions(
            user,
            "builder.page.read",
            workspace=page.builder.workspace,
            context=page,
        )
    except Exception:
        raise ToolInputError(
            f"No access to page {page_id}. "
            "Use list_pages to find pages in the current workspace."
        )
    return page


def get_local_baserow_integration(builder: Builder) -> Integration:
    """Get or create the LocalBaserow integration for a builder."""

    integrations = IntegrationHandler().get_integrations(builder)
    for integration in integrations:
        if integration.get_type().type == "local_baserow":
            return integration.specific

    local_baserow_type = integration_type_registry.get("local_baserow")
    return IntegrationHandler().create_integration(
        local_baserow_type, builder, name="Local Baserow"
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def list_pages(builder: Builder) -> list[PageItem]:
    """List all non-shared pages in a builder."""
    pages = PageHandler().get_pages(builder).filter(shared=False)
    return [PageItem.from_orm(p) for p in pages]


def list_data_sources(page: Page) -> list[DataSourceItem]:
    """List all data sources on a page."""
    return [
        DataSourceItem.from_orm(ds) for ds in DataSourceHandler().get_data_sources(page)
    ]


def list_elements(page: Page) -> list[ElementItem]:
    """List all elements on a page, including shared elements visible on it."""
    elements = list(ElementHandler().get_elements(page))

    # Also include shared elements (headers/footers) visible on this page
    if not page.shared:
        shared_page = page.builder.shared_page
        shared_elements = ElementHandler().get_elements(shared_page)
        elements = list(shared_elements) + elements

    return [ElementItem.from_orm(el) for el in elements]


def list_workflow_actions(page: Page) -> list[ActionItem]:
    """List all workflow actions on a page."""
    return [
        ActionItem.from_orm(a)
        for a in BuilderWorkflowActionHandler().get_workflow_actions(page)
    ]


# ---------------------------------------------------------------------------
# Page creation
# ---------------------------------------------------------------------------


def create_page(user: AbstractUser, builder: Builder, page_create: PageCreate) -> Page:
    """Create a page in a builder application."""

    from baserow.contrib.builder.pages.service import PageService

    return PageService().create_page(
        user,
        builder,
        page_create.name,
        page_create.path,
        path_params=[p.model_dump() for p in page_create.path_params],
        query_params=[p.model_dump() for p in page_create.query_params],
    )


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

    Returns ``(orm_data_source, service_type_str)``.
    """

    from baserow.contrib.builder.data_sources.handler import DataSourceHandler
    from baserow.core.services.registries import service_type_registry

    try:
        ds = DataSourceHandler().get_data_source_for_update(ds_update.data_source_id)
    except Exception:
        raise ToolInputError(
            f"Data source with ID {ds_update.data_source_id} not found. "
            "Use list_data_sources to find valid data source IDs."
        )

    service_type = (
        service_type_registry.get_by_model(ds.service.specific) if ds.service else None
    )
    kwargs = ds_update.to_update_kwargs(user, workspace)
    if kwargs:
        ds = DataSourceService().update_data_source(
            user, ds, service_type=service_type, **kwargs
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
) -> tuple[Any, int]:
    """
    Create an element on a page, resolving refs to IDs.

    Returns ``(orm_element, element_id)``.
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

    if element_create.place_in_container:
        kwargs["place_in_container"] = element_create.place_in_container
    elif "parent_element_id" in kwargs:
        try:
            parent = ElementHandler().get_element(kwargs["parent_element_id"])
            if parent.get_type().type == "column":
                kwargs["place_in_container"] = "0"
        except Exception:
            pass

    # Set data_source_id in kwargs (may already be set by to_orm_kwargs)
    if isinstance(element_create.data_source, int):
        kwargs["data_source_id"] = element_create.data_source

    before = None
    if before_id is not None:
        try:
            before = ElementService().get_element(user, before_id)
        except ElementDoesNotExist:
            pass

    element = ElementService().create_element(
        user, element_type, target_page, before=before, **kwargs
    )

    element_create.post_create(user, element, target_page)
    return element, element.id


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

    place = element_move.place_in_container or ""

    return ElementService().move_element(user, element, parent, place, before=before)


def update_element(
    user: AbstractUser,
    element_update: ElementUpdate,
) -> tuple[Any, str]:
    """
    Update an existing element by ID.

    Returns ``(orm_element, element_type_str)``.
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
    if kwargs:
        element = ElementService().update_element(user, element, **kwargs)
    return element, element_type


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
        element = ElementService().update_element(user, element, **kwargs)
    return element, element_type


# ---------------------------------------------------------------------------
# Workflow action creation
# ---------------------------------------------------------------------------


def _resolve_event(element_id: int, event: str) -> str:
    """
    Resolve a human-friendly event name to the actual event string for
    any element type.

    For elements with button collection fields (e.g. ``TableElement``),
    the LLM typically sends ``"click"`` or ``"<button_name>_click"``
    which must be resolved to ``"{uid}_click"`` where ``uid`` is the
    ``CollectionField.uid``.

    For all other elements (``ButtonElement``, ``FormContainerElement``,
    etc.) the event is returned unchanged since they use static event
    names (``"click"``, ``"submit"``, ``"after_login"``).
    """

    try:
        element = ElementHandler().get_element(element_id).specific
    except Exception:
        return event

    # Check if the element has a `fields` relation to CollectionField
    # (currently TableElement; works for any future collection element).
    if not hasattr(element, "fields"):
        return event

    button_fields = list(element.fields.filter(type="button").order_by("order"))
    if not button_fields:
        return event

    # Already a UUID-prefixed event — no resolution needed
    if "_" in event:
        prefix = event.rsplit("_", 1)[0]
        button_uids = {str(bf.uid) for bf in button_fields}
        if prefix in button_uids:
            return event

    # "click" → match to the first (or only) button column
    if event == "click":
        return f"{button_fields[0].uid}_click"

    # "<button_name>_click" → match by name (case-insensitive)
    if event.endswith("_click"):
        name = event[: -len("_click")].strip().lower()
        for bf in button_fields:
            if bf.name.strip().lower() == name:
                return f"{bf.uid}_click"

    # Fallback: first button column
    return f"{button_fields[0].uid}_click"


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
    event = _resolve_event(element_id, action_create.event)

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
    action_id: int, field_id: int, value_formula: str
) -> dict[str, Any]:
    """Add or update a field mapping on a create_row/update_row workflow action."""

    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import (
        BASEROW_FORMULA_MODE_ADVANCED,
        BaserowFormulaObject,
    )

    action = BuilderWorkflowActionHandler().get_workflow_action(action_id)
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
        existing.value = BaserowFormulaObject.create(
            value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
        )
        existing.enabled = True
        existing.save()
        status = "updated"
    else:
        LocalBaserowTableServiceFieldMapping.objects.create(
            service=service,
            field_id=field_id,
            value=BaserowFormulaObject.create(
                value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
            ),
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
