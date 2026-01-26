from typing import TYPE_CHECKING, Any, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
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
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.models import Workspace
from baserow.core.services.registries import service_type_registry

from .types import (
    AnyDataSourceCreate,
    AnyElementCreate,
    AnyWorkflowActionCreate,
    ChoiceElementCreate,
    CreateRowActionCreate,
    DataSourceItem,
    DeleteRowActionCreate,
    ElementItem,
    FooterElementCreate,
    HeaderElementCreate,
    MenuElementCreate,
    PageCreate,
    PageItem,
    UpdateRowActionCreate,
    WorkflowActionItem,
)

if TYPE_CHECKING:
    pass


def get_builder(
    user: AbstractUser, workspace: Workspace, application_id: int
) -> Builder:
    """
    Get a builder application with permission check.

    :param user: The user making the request.
    :param workspace: The workspace to verify the application belongs to.
    :param application_id: The ID of the builder application.
    :return: The Builder instance.
    :raises: ApplicationDoesNotExist if not found or permission denied.
    """

    from baserow.core.service import CoreService

    builder = CoreService().get_application(
        user,
        application_id,
        base_queryset=Builder.objects.filter(workspace=workspace),
    )
    return builder


def get_page(user: AbstractUser, page_id: int) -> Page:
    """
    Get a page with permission check.

    :param user: The user making the request.
    :param page_id: The ID of the page.
    :return: The Page instance.
    """

    page = PageHandler().get_page(page_id)
    CoreHandler().check_permissions(
        user,
        "builder.page.read",
        workspace=page.builder.workspace,
        context=page,
    )
    return page


def get_local_baserow_integration(builder: Builder) -> Integration:
    """
    Get the LocalBaserow integration for a builder, or create one if it doesn't exist.

    :param builder: The builder application.
    :return: The LocalBaserow integration.
    """

    integrations = IntegrationHandler().get_integrations(builder)
    for integration in integrations:
        if integration.get_type().type == "local_baserow":
            return integration.specific

    # Create one if it doesn't exist (shouldn't happen normally)
    local_baserow_type = integration_type_registry.get("local_baserow")
    return IntegrationHandler().create_integration(
        local_baserow_type, builder, name="Local Baserow"
    )


def create_page(user: AbstractUser, builder: Builder, page_create: PageCreate) -> Page:
    """
    Create a page in a builder application.

    :param user: The user creating the page.
    :param builder: The builder application.
    :param page_create: The page creation data.
    :return: The created Page instance.
    """

    from baserow.contrib.builder.pages.service import PageService

    page = PageService().create_page(
        user,
        builder,
        page_create.name,
        page_create.path,
        path_params=[p.model_dump() for p in page_create.path_params],
        query_params=[p.model_dump() for p in page_create.query_params],
    )
    return page


def create_element(
    user: AbstractUser,
    page: Page,
    element_create: AnyElementCreate,
    ref_to_id_map: dict[str, int],
    data_source_ref_to_id_map: dict[str, int],
    shared_page_refs: set[str] | None = None,
) -> tuple[Any, int]:
    """
    Create an element on a page, resolving refs to IDs.

    :param user: The user creating the element.
    :param page: The page to add the element to.
    :param element_create: The element creation data.
    :param ref_to_id_map: Mapping of element refs to their IDs.
    :param data_source_ref_to_id_map: Mapping of data source refs to their IDs.
    :param shared_page_refs: Set of refs that are on the shared page (for tracking).
    :return: Tuple of (created element, element ID).
    """

    if shared_page_refs is None:
        shared_page_refs = set()

    element_type = element_type_registry.get(element_create.type)

    # Determine if this element should be created on the shared page
    # Header/footer elements must be created on the shared page
    # Child elements of shared page elements must also be on the shared page
    use_shared_page = False
    if isinstance(element_create, (HeaderElementCreate, FooterElementCreate)):
        use_shared_page = True
    elif (
        element_create.parent_element_ref
        and element_create.parent_element_ref in shared_page_refs
    ):
        use_shared_page = True

    # Get the target page (shared page for multi-page elements)
    target_page = page
    if use_shared_page:
        target_page = page.builder.shared_page
        shared_page_refs.add(element_create.ref)

    kwargs = element_create.to_orm_kwargs(user, target_page)

    # Resolve parent element - prefer direct ID, fall back to ref resolution
    if element_create.parent_element_id:
        # Direct ID reference to an existing element
        kwargs["parent_element_id"] = element_create.parent_element_id
    elif element_create.parent_element_ref:
        # Ref-based reference to element created in same batch
        if element_create.parent_element_ref not in ref_to_id_map:
            raise ValueError(
                f"Parent element ref '{element_create.parent_element_ref}' not found. "
                "Make sure parent elements are defined before their children, "
                "or use parent_element_id to reference an existing element."
            )
        kwargs["parent_element_id"] = ref_to_id_map[element_create.parent_element_ref]

    if element_create.place_in_container:
        kwargs["place_in_container"] = element_create.place_in_container

    # Resolve data source ref to ID for collection elements
    if (
        hasattr(element_create, "data_source_id")
        and element_create.data_source_id is None
    ):
        # Check if there's a data_source_ref attribute
        data_source_ref = getattr(element_create, "data_source_ref", None)
        if data_source_ref and data_source_ref in data_source_ref_to_id_map:
            kwargs["data_source_id"] = data_source_ref_to_id_map[data_source_ref]

    # Handle menu items for MenuElementCreate - pass to kwargs for after_create hook
    if isinstance(element_create, MenuElementCreate) and element_create.menu_items:
        kwargs["menu_items"] = element_create.get_menu_items()

    element = ElementService().create_element(user, element_type, target_page, **kwargs)

    # Handle choice options separately
    if isinstance(element_create, ChoiceElementCreate) and element_create.options:
        from baserow.contrib.builder.elements.models import ChoiceElementOption

        ChoiceElementOption.objects.bulk_create(
            [
                ChoiceElementOption(
                    choice=element,
                    name=opt.name,
                    value=opt.value,
                )
                for opt in element_create.options
            ]
        )

    # Handle multi-page elements (header/footer) - set page associations
    if isinstance(element_create, (HeaderElementCreate, FooterElementCreate)):
        page_ids = element_create.get_page_ids()
        if page_ids:
            element.pages.set(page_ids)

    return element, element.id


def create_data_source(
    user: AbstractUser,
    page: Page,
    ds_create: AnyDataSourceCreate,
    integration: Integration,
) -> tuple[Any, int]:
    """
    Create a data source for a page.

    :param user: The user creating the data source.
    :param page: The page to add the data source to.
    :param ds_create: The data source creation data.
    :param integration: The LocalBaserow integration.
    :return: Tuple of (created data source, data source ID).
    """

    service_type = service_type_registry.get(ds_create.get_service_type())
    workspace = page.builder.workspace
    service_kwargs = ds_create.to_service_kwargs(user, workspace)
    service_kwargs["integration"] = integration

    data_source = DataSourceService().create_data_source(
        user=user,
        page=page,
        name=ds_create.name,
        service_type=service_type,
        **service_kwargs,
    )

    # Add filters if applicable
    if hasattr(ds_create, "get_filters"):
        filters = ds_create.get_filters()
        if filters:
            from baserow.contrib.integrations.local_baserow.models import (
                LocalBaserowTableServiceFilter,
            )

            LocalBaserowTableServiceFilter.objects.bulk_create(
                [
                    LocalBaserowTableServiceFilter(
                        service=data_source.service,
                        field_id=f["field_id"],
                        type=f["type"],
                        value=f["value"],
                        order=i,
                    )
                    for i, f in enumerate(filters)
                ]
            )

    # Add sortings if applicable
    if hasattr(ds_create, "get_sortings"):
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


def create_workflow_action(
    user: AbstractUser,
    page: Page,
    action_create: AnyWorkflowActionCreate,
    element_ref_to_id_map: dict[str, int],
    data_source_ref_to_id_map: dict[str, int],
    integration: Optional[Integration] = None,
) -> tuple[Any, int]:
    """
    Create a workflow action attached to an element.

    :param user: The user creating the action.
    :param page: The page the action belongs to.
    :param action_create: The action creation data.
    :param element_ref_to_id_map: Mapping of element refs to their IDs.
    :param data_source_ref_to_id_map: Mapping of data source refs to their IDs.
    :param integration: The LocalBaserow integration (for service-based actions).
    :return: Tuple of (created action, action ID).
    """

    # Resolve element ref to ID, or use element_id directly
    if action_create.element_id:
        element_id = action_create.element_id
    elif action_create.element_ref:
        if action_create.element_ref not in element_ref_to_id_map:
            raise ValueError(
                f"Element ref '{action_create.element_ref}' not found. "
                "Make sure elements are created before attaching actions to them, "
                "or use element_id for existing elements."
            )
        element_id = element_ref_to_id_map[action_create.element_ref]
    else:
        raise ValueError(
            "Either element_ref or element_id must be provided for workflow actions."
        )

    action_type = builder_workflow_action_type_registry.get(
        action_create.get_action_type()
    )

    kwargs = {
        "page": page,
        "element_id": element_id,
        "event": action_create.event,
    }

    # Add action-specific kwargs
    if hasattr(action_create, "to_orm_kwargs"):
        kwargs.update(action_create.to_orm_kwargs())

    # Handle service-based actions (create_row, update_row, delete_row)
    if hasattr(action_create, "get_service_type"):
        service_type = service_type_registry.get(action_create.get_service_type())
        workspace = page.builder.workspace
        service_kwargs = action_create.to_service_kwargs(user, workspace)
        if integration:
            service_kwargs["integration"] = integration
        kwargs["service_type"] = service_type

        # For upsert actions, we need to handle field mappings
        if isinstance(action_create, (CreateRowActionCreate, UpdateRowActionCreate)):
            from baserow.core.services.handler import ServiceHandler

            # Create the service first, then add field mappings
            service = ServiceHandler().create_service(service_type, **service_kwargs)
            kwargs["service"] = service

            # Remove service_type since we're passing the service directly
            del kwargs["service_type"]

            # Add field mappings
            if hasattr(action_create, "get_field_mappings"):
                from baserow.contrib.integrations.local_baserow.models import (
                    LocalBaserowTableServiceFieldMapping,
                )

                field_mappings = action_create.get_field_mappings()
                if field_mappings:
                    LocalBaserowTableServiceFieldMapping.objects.bulk_create(
                        [
                            LocalBaserowTableServiceFieldMapping(
                                service=service,
                                field_id=fm["field_id"],
                                value=fm["value"],
                                enabled=True,
                            )
                            for fm in field_mappings
                        ]
                    )
        elif isinstance(action_create, DeleteRowActionCreate):
            from baserow.core.services.handler import ServiceHandler

            service = ServiceHandler().create_service(service_type, **service_kwargs)
            kwargs["service"] = service
            del kwargs["service_type"]

    # Resolve data source ref for refresh_data_source action
    if hasattr(action_create, "data_source_id"):
        data_source_ref = getattr(action_create, "data_source_ref", None)
        if data_source_ref and data_source_ref in data_source_ref_to_id_map:
            kwargs["data_source_id"] = data_source_ref_to_id_map[data_source_ref]
        elif action_create.data_source_id:
            kwargs["data_source_id"] = action_create.data_source_id

    action = BuilderWorkflowActionHandler().create_workflow_action(
        action_type, **kwargs
    )

    return action, action.id


def list_pages(builder: Builder) -> list[PageItem]:
    """
    List all non-shared pages in a builder.

    :param builder: The builder application.
    :return: List of PageItem instances.
    """

    pages = PageHandler().get_pages(builder).filter(shared=False)
    return [PageItem.from_orm(page) for page in pages]


def list_data_sources(page: Page) -> list[DataSourceItem]:
    """
    List all data sources on a page.

    :param page: The page.
    :return: List of DataSourceItem instances.
    """

    data_sources = DataSourceHandler().get_data_sources(page)
    return [DataSourceItem.from_orm(ds) for ds in data_sources]


def list_elements(page: Page) -> list[ElementItem]:
    """
    List all elements on a page.

    :param page: The page.
    :return: List of ElementItem instances.
    """

    from baserow.contrib.builder.elements.handler import ElementHandler

    elements = ElementHandler().get_elements(page)
    return [ElementItem.from_orm(el) for el in elements]


# =============================================================================
# Theme Utilities
# =============================================================================


def get_builder_theme(builder: Builder) -> dict[str, Any]:
    """
    Serialize the builder's theme settings grouped by category for LLM readability.

    :param builder: The builder application.
    :return: Dict of theme settings grouped by category.
    """

    from baserow.contrib.builder.api.theme.serializers import serialize_builder_theme

    theme_data = serialize_builder_theme(builder)

    # Group by category for easier understanding
    grouped = {
        "colors": {},
        "typography": {"body": {}, "headings": {}},
        "buttons": {},
        "links": {},
        "images": {},
        "page": {},
        "inputs": {"label": {}, "input": {}},
        "tables": {"border": {}, "header": {}, "cell": {}, "separator": {}},
    }

    for key, value in theme_data.items():
        # Colors
        if key in (
            "primary_color",
            "secondary_color",
            "border_color",
            "main_success_color",
            "main_warning_color",
            "main_error_color",
        ):
            grouped["colors"][key] = value
        # Typography - body
        elif key.startswith("body_"):
            grouped["typography"]["body"][key.replace("body_", "")] = value
        # Typography - headings
        elif key.startswith("heading_"):
            grouped["typography"]["headings"][key] = value
        # Buttons
        elif key.startswith("button_"):
            grouped["buttons"][key.replace("button_", "")] = value
        # Links
        elif key.startswith("link_"):
            grouped["links"][key.replace("link_", "")] = value
        # Images
        elif key.startswith("image_"):
            grouped["images"][key.replace("image_", "")] = value
        # Page
        elif key.startswith("page_"):
            grouped["page"][key.replace("page_", "")] = value
        # Inputs - label
        elif key.startswith("label_"):
            grouped["inputs"]["label"][key.replace("label_", "")] = value
        # Inputs - input
        elif key.startswith("input_"):
            grouped["inputs"]["input"][key.replace("input_", "")] = value
        # Tables
        elif key.startswith("table_header_"):
            grouped["tables"]["header"][key.replace("table_header_", "")] = value
        elif key.startswith("table_cell_"):
            grouped["tables"]["cell"][key.replace("table_cell_", "")] = value
        elif key.startswith("table_vertical_separator_") or key.startswith(
            "table_horizontal_separator_"
        ):
            sep_key = key.replace("table_", "")
            grouped["tables"]["separator"][sep_key] = value
        elif key.startswith("table_"):
            grouped["tables"]["border"][key.replace("table_", "")] = value

    return grouped


def flatten_theme_update(
    colors=None,
    typography=None,
    buttons=None,
    links=None,
    images=None,
    page=None,
    inputs=None,
    tables=None,
) -> dict[str, Any]:
    """
    Convert grouped theme updates to flat kwargs for ThemeService.

    :param colors: ColorThemeUpdate instance
    :param typography: TypographyThemeUpdate instance
    :param buttons: ButtonThemeUpdate instance
    :param links: LinkThemeUpdate instance
    :param images: ImageThemeUpdate instance
    :param page: PageThemeUpdate instance
    :param inputs: InputThemeUpdate instance
    :param tables: TableThemeUpdate instance
    :return: Flat dict of theme properties for ThemeService.update_theme()
    """

    flat = {}

    # Colors (no prefix)
    if colors:
        for key, value in colors.model_dump(exclude_none=True).items():
            flat[key] = value

    # Typography - all keys are already flat
    if typography:
        for key, value in typography.model_dump(exclude_none=True).items():
            flat[key] = value

    # Buttons (add button_ prefix)
    if buttons:
        for key, value in buttons.model_dump(exclude_none=True).items():
            flat[f"button_{key}"] = value

    # Links - all keys are already flat, just add link_ prefix
    if links:
        for key, value in links.model_dump(exclude_none=True).items():
            flat[f"link_{key}"] = value

    # Images (add image_ prefix)
    if images:
        for key, value in images.model_dump(exclude_none=True).items():
            flat[f"image_{key}"] = value

    # Page (add page_ prefix)
    if page:
        for key, value in page.model_dump(exclude_none=True).items():
            flat[f"page_{key}"] = value

    # Inputs (mixed prefix - already has label_ or input_)
    if inputs:
        for key, value in inputs.model_dump(exclude_none=True).items():
            flat[key] = value

    # Tables (add table_ prefix)
    if tables:
        for key, value in tables.model_dump(exclude_none=True).items():
            flat[f"table_{key}"] = value

    return flat


# =============================================================================
# Element Update/Delete Utilities
# =============================================================================


def update_element_by_id(
    user: AbstractUser,
    element_id: int,
    style=None,
    styles=None,
    css_classes=None,
    visibility=None,
) -> Any:
    """
    Update an element's style properties.

    :param user: The user making the update.
    :param element_id: The ID of the element to update.
    :param style: ElementStyleConfig instance with style properties.
    :param styles: ElementThemeOverrides instance with theme overrides.
    :param css_classes: CSS class string.
    :param visibility: Visibility setting.
    :return: The updated element.
    """

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element_for_update(element_id)

    kwargs = {}

    # Add style properties with style_ prefix
    if style:
        kwargs.update(style.to_orm_kwargs())

    # Add styles (theme overrides)
    if styles is not None:
        kwargs["styles"] = styles.model_dump(exclude_none=True)

    # Add css_classes
    if css_classes is not None:
        kwargs["css_classes"] = css_classes

    # Add visibility
    if visibility is not None:
        kwargs["visibility"] = visibility

    if kwargs:
        return ElementService().update_element(user, element, **kwargs)
    return element


def delete_element_by_id(user: AbstractUser, element_id: int) -> None:
    """
    Delete an element by ID.

    :param user: The user making the deletion.
    :param element_id: The ID of the element to delete.
    """

    from baserow.contrib.builder.elements.handler import ElementHandler

    element = ElementHandler().get_element_for_update(element_id)
    ElementService().delete_element(user, element)


def verify_theme_properties_applied(
    requested: dict[str, Any], actual_flat: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """
    Compare requested theme properties with actual applied values.

    :param requested: Flat dict of requested theme properties (from flatten_theme_update).
    :param actual_flat: Flat dict of actual theme properties (from serialize_builder_theme).
    :return: Dict with 'mismatched' and 'not_found' lists of property issues.
    """

    def _normalize_value(value: Any) -> Any:
        """Normalize value for comparison."""
        if isinstance(value, str):
            return value.lower().strip()
        if isinstance(value, list):
            return [_normalize_value(v) for v in value]
        return value

    mismatched = []
    not_found = []

    for key, requested_value in requested.items():
        if key not in actual_flat:
            not_found.append(
                {
                    "property": key,
                    "requested_value": requested_value,
                    "reason": "Property not recognized by the theme system",
                }
            )
        else:
            actual_value = actual_flat[key]
            # Normalize for comparison (colors may be case-insensitive)
            if _normalize_value(requested_value) != _normalize_value(actual_value):
                mismatched.append(
                    {
                        "property": key,
                        "requested_value": requested_value,
                        "actual_value": actual_value,
                    }
                )

    return {"mismatched": mismatched, "not_found": not_found}


# =============================================================================
# Workflow Action Utilities
# =============================================================================


def list_workflow_actions(page: Page) -> list[WorkflowActionItem]:
    """
    List all workflow actions on a page.

    :param page: The page.
    :return: List of WorkflowActionItem instances with field mapping details.
    """

    actions = BuilderWorkflowActionHandler().get_workflow_actions(page)
    return [WorkflowActionItem.from_orm(action) for action in actions]


def add_field_mapping_to_action(
    action_id: int, field_id: int, value_formula: str
) -> dict[str, Any]:
    """
    Add or update a field mapping on a create_row/update_row workflow action.

    :param action_id: The ID of the workflow action.
    :param field_id: The ID of the table field to map to.
    :param value_formula: The formula for the value (e.g., "get('form_data.123')").
    :return: Dict with status and updated mappings.
    """

    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableServiceFieldMapping,
    )
    from baserow.core.formula.types import BaserowFormulaObject

    action = BuilderWorkflowActionHandler().get_workflow_action(action_id)
    action_type = action.get_type().type

    if action_type not in ("create_row", "update_row"):
        raise ValueError(
            f"Cannot add field mappings to action type '{action_type}'. "
            "Only create_row and update_row actions support field mappings."
        )

    service = action.service.specific

    # Check if mapping for this field already exists
    existing_mapping = LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
        service=service, field_id=field_id
    ).first()

    if existing_mapping:
        # Update existing mapping
        existing_mapping.value = BaserowFormulaObject.create(value_formula)
        existing_mapping.enabled = True
        existing_mapping.save()
        status = "updated"
    else:
        # Create new mapping
        LocalBaserowTableServiceFieldMapping.objects.create(
            service=service,
            field_id=field_id,
            value=BaserowFormulaObject.create(value_formula),
            enabled=True,
        )
        status = "created"

    # Return updated list of mappings
    mappings = []
    for mapping in service.field_mappings.all():
        mappings.append(
            {
                "field_id": mapping.field_id,
                "field_name": mapping.field.name,
                "value": str(mapping.value) if mapping.value else "",
            }
        )

    return {"status": status, "field_mappings": mappings}
