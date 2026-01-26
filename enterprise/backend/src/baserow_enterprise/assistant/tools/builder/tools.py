from typing import TYPE_CHECKING, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

import udspy

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType
from baserow_enterprise.assistant.types import BuilderPageNavigationType

from . import utils
from .types import (
    AnyDataSourceCreate,
    AnyElementCreate,
    AnyWorkflowActionCreate,
    PageCreate,
    PageItem,
)
from .types.style import ElementUpdate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


__all__ = [
    "PageToolFactoryToolType",
    "PageContentToolFactoryToolType",
    "ThemeToolFactoryToolType",
    # Backward compatibility wrappers for tests
    "get_element_tool_factory",
    "get_list_pages_tool",
    "get_data_source_tool_factory",
    "get_workflow_action_tool_factory",
]


# =============================================================================
# Page Tool Factory
# =============================================================================


def get_page_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    Returns a tool factory that provides page and data source tools.
    """

    def list_pages(application_id: int) -> dict[str, Any]:
        """
        List all pages in an application builder.

        - Use this to discover existing pages before creating new ones.
        - Returns page IDs, names, and paths.
        """

        nonlocal user, workspace, tool_helpers

        builder = utils.get_builder(user, workspace, application_id)

        tool_helpers.update_status(
            _("Listing pages in %(app_name)s...") % {"app_name": builder.name}
        )

        pages = utils.list_pages(builder)
        return {"pages": [p.model_dump() for p in pages]}

    def create_pages(application_id: int, pages: list[PageCreate]) -> dict[str, Any]:
        """
        Create pages in an application builder.

        - Each page needs a unique name and path.
        - Use path parameters like :id for dynamic routes (e.g., '/products/:id').
        - Path params must be defined in path_params array.
        """

        nonlocal user, workspace, tool_helpers

        if not pages:
            return {"created_pages": []}

        builder = utils.get_builder(user, workspace, application_id)

        created_pages = []
        with transaction.atomic():
            for page_create in pages:
                tool_helpers.update_status(
                    _("Creating page %(page_name)s...")
                    % {"page_name": page_create.name}
                )

                page = utils.create_page(user, builder, page_create)
                created_pages.append(PageItem.from_orm(page))

        # Navigate to the last created page
        if created_pages:
            last_page = created_pages[-1]
            tool_helpers.navigate_to(
                BuilderPageNavigationType(
                    type="builder-page",
                    application_id=application_id,
                    page_id=last_page.id,
                    page_name=last_page.name,
                )
            )

        return {"created_pages": [p.model_dump() for p in created_pages]}

    def list_data_sources(page_id: int) -> dict[str, Any]:
        """
        List all data sources on a page.

        - Use this to discover existing data sources before creating new ones.
        - Returns data source IDs, names, types, and table IDs.
        """

        nonlocal user, workspace, tool_helpers

        page = utils.get_page(user, page_id)

        tool_helpers.update_status(
            _("Listing data sources on %(page_name)s...") % {"page_name": page.name}
        )

        data_sources = utils.list_data_sources(page)
        return {"data_sources": [ds.model_dump() for ds in data_sources]}

    def create_data_sources(
        page_id: int, data_sources: list[AnyDataSourceCreate]
    ) -> dict[str, Any]:
        """
        Create data sources for a page. Data sources connect to Baserow tables.

        - list_rows: Fetches multiple rows from a table (with optional filters/sorting).
        - get_row: Fetches a single row by ID (use formula like "get('page_parameter.id')").
        - Use `ref` field to reference data sources in elements' data_source_id.

        Returns the mapping of refs to IDs for use in element creation.
        """

        nonlocal user, workspace, tool_helpers

        if not data_sources:
            return {"created_data_sources": [], "ref_to_id_map": {}}

        page = utils.get_page(user, page_id)
        integration = utils.get_local_baserow_integration(page.builder)

        tool_helpers.update_status(
            _("Creating %(count)d data sources on %(page_name)s...")
            % {"count": len(data_sources), "page_name": page.name}
        )

        ref_to_id_map: dict[str, int] = {}
        created_data_sources = []

        with transaction.atomic():
            for ds_create in data_sources:
                _data_source, ds_id = utils.create_data_source(
                    user, page, ds_create, integration
                )

                ref_to_id_map[ds_create.ref] = ds_id

                created_data_sources.append(
                    {
                        "id": ds_id,
                        "ref": ds_create.ref,
                        "name": ds_create.name,
                        "type": ds_create.type,
                    }
                )

        return {
            "created_data_sources": created_data_sources,
            "ref_to_id_map": ref_to_id_map,
        }

    def load_page_tools():
        """
        TOOL LOADER: Loads tools to manage pages and data sources in an application.

        Call this loader when you need to:
        - List or create pages in an application builder
        - List or create data sources that connect pages to Baserow tables
        - Set up data fetching for tables, repeaters, or record selectors

        After calling this loader, you will have access to:
        - list_pages: List existing pages in an application
        - create_pages: Create new pages with paths and parameters
        - list_data_sources: List existing data sources on a page
        - create_data_sources: Create data sources connecting to Baserow tables

        Data source types:
        - list_rows: Fetch multiple rows (with filters, sorting)
        - get_row: Fetch a single row by ID
        """

        @udspy.module_callback
        def _load_page_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            new_tools = [
                udspy.Tool(list_pages),
                udspy.Tool(create_pages),
                udspy.Tool(list_data_sources),
                udspy.Tool(create_data_sources),
            ]
            observation.append(
                "- Use `list_pages` to list existing pages in an application."
            )
            observation.append(
                "- Use `create_pages` to create pages in an application."
            )
            observation.append(
                "- Use `list_data_sources` to list existing data sources on a page."
            )
            observation.append(
                "- Use `create_data_sources` to create data sources connecting to tables."
            )

            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_page_tools

    return load_page_tools


class PageToolFactoryToolType(AssistantToolType):
    type = "page_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_page_tool_factory(user, workspace, tool_helpers)


# =============================================================================
# Page Content Tool Factory
# =============================================================================


def get_page_content_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    Returns a tool factory that provides element and action tools.
    """

    def list_elements(page_id: int) -> dict[str, Any]:
        """
        List all elements on a page.

        - Use this to discover existing elements before creating new ones.
        - Returns element IDs, types, order, and parent relationships.
        """

        nonlocal user, workspace, tool_helpers

        page = utils.get_page(user, page_id)

        tool_helpers.update_status(
            _("Listing elements on %(page_name)s...") % {"page_name": page.name}
        )

        elements = utils.list_elements(page)
        return {"elements": [el.model_dump() for el in elements]}

    def create_elements(
        page_id: int,
        elements: list[AnyElementCreate],
        data_source_refs: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """
        Create UI elements on a page. Elements can be nested using parent_element_ref.

        - Use `ref` field to identify elements for linking.
        - Use `parent_element_ref` to nest elements inside containers.
        - For columns, `place_in_container` is the 0-indexed column number ("0", "1", etc.).
        - Form inputs should be placed inside form_container elements.
        - Tables and repeaters need a data_source_id or use data_source_refs mapping.

        Available element types:
        - Layout: column, form_container, simple_container
        - Display: heading, text, button, link, image
        - Form inputs: input_text, choice, checkbox, datetime_picker, record_selector
        - Collections: table, repeat

        Returns the mapping of refs to IDs for use in action creation.
        """

        nonlocal user, workspace, tool_helpers

        if not elements:
            return {"created_elements": []}

        page = utils.get_page(user, page_id)

        tool_helpers.update_status(
            _("Creating %(count)d elements on %(page_name)s...")
            % {"count": len(elements), "page_name": page.name}
        )

        ref_to_id_map: dict[str, int] = {}
        data_source_ref_to_id_map = data_source_refs or {}
        created_elements = []

        with transaction.atomic():
            for element_create in elements:
                element, element_id = utils.create_element(
                    user, page, element_create, ref_to_id_map, data_source_ref_to_id_map
                )

                # Track the ref for parent linking
                ref_to_id_map[element_create.ref] = element_id

                created_elements.append(
                    {
                        "id": element_id,
                        "ref": element_create.ref,
                        "type": element_create.type,
                    }
                )

        return {
            "created_elements": created_elements,
            "ref_to_id_map": ref_to_id_map,
        }

    def create_actions(
        page_id: int,
        actions: list[AnyWorkflowActionCreate],
        element_refs: dict[str, int] | None = None,
        data_source_refs: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """
        Create actions attached to elements.

        - Actions are triggered by events (click, submit).
        - Use `element_ref` to attach to a newly created element (pass ref_to_id_map from create_elements).
        - Use `element_id` to attach to an existing element (use list_elements to find IDs).
        - For forms, use event='submit' on the form_container.
        - Multiple actions can be attached to the same element/event.

        Available action types:
        - notification: Show a message to the user.
        - open_page: Navigate to another page.
        - create_row: Insert a new row in a table.
        - update_row: Update an existing row.
        - delete_row: Remove a row.
        - refresh_data_source: Reload data from a data source.
        - logout: Log out the current user.
        """

        nonlocal user, workspace, tool_helpers

        if not actions:
            return {"created_actions": []}

        page = utils.get_page(user, page_id)
        integration = utils.get_local_baserow_integration(page.builder)

        tool_helpers.update_status(
            _("Creating %(count)d actions...") % {"count": len(actions)}
        )

        element_ref_to_id_map = element_refs or {}
        data_source_ref_to_id_map = data_source_refs or {}
        created_actions = []

        with transaction.atomic():
            for action_create in actions:
                _action, action_id = utils.create_workflow_action(
                    user,
                    page,
                    action_create,
                    element_ref_to_id_map,
                    data_source_ref_to_id_map,
                    integration,
                )

                created_actions.append(
                    {
                        "id": action_id,
                        "type": action_create.type,
                        "element_ref": action_create.element_ref,
                        "event": action_create.event,
                    }
                )

        return {"created_actions": created_actions}

    def update_elements(
        page_id: int,
        element_updates: list[ElementUpdate],
    ) -> dict[str, Any]:
        """
        Update existing elements on a page.

        - Use list_elements first to get element IDs.
        - Each update specifies element_id and properties to change.
        - Only provided properties are updated; others remain unchanged.

        Updatable properties:
        - style: Border, padding, margin, background settings
        - styles: Theme property overrides for the element
        - css_classes: Space-separated CSS class names
        - visibility: 'all', 'logged-in', or 'not-logged'
        """

        nonlocal user, workspace, tool_helpers

        if not element_updates:
            return {"updated_elements": []}

        # Verify access to page
        page = utils.get_page(user, page_id)

        tool_helpers.update_status(
            _("Updating %(count)d elements on %(page_name)s...")
            % {"count": len(element_updates), "page_name": page.name}
        )

        updated_elements = []

        with transaction.atomic():
            for update in element_updates:
                element = utils.update_element_by_id(
                    user,
                    update.element_id,
                    style=update.style,
                    styles=update.styles,
                    css_classes=update.css_classes,
                    visibility=update.visibility,
                )
                updated_elements.append(
                    {
                        "id": element.id,
                        "type": element.get_type().type,
                    }
                )

        return {"updated_elements": updated_elements}

    def delete_element(page_id: int, element_id: int) -> dict[str, Any]:
        """
        Delete an element from a page.

        - Use list_elements first to get element IDs.
        - Deleting a container element will also delete its children.
        - This action cannot be undone.
        """

        nonlocal user, workspace, tool_helpers

        # Verify access to page
        page = utils.get_page(user, page_id)

        tool_helpers.update_status(
            _("Deleting element %(element_id)d from %(page_name)s...")
            % {"element_id": element_id, "page_name": page.name}
        )

        utils.delete_element_by_id(user, element_id)

        return {"deleted": True, "element_id": element_id}

    def load_page_content_tools():
        """
        TOOL LOADER: Loads tools to manage UI elements and actions on pages.

        Call this loader when you need to:
        - List, create, update, or delete UI elements
        - Add actions to elements (form submit, button click, navigation, etc.)
        - Build interactive page content
        - Style elements (border, padding, margin, background, CSS classes)

        After calling this loader, you will have access to:
        - list_elements: List existing elements on a page
        - create_elements: Create UI elements with optional styling
        - update_elements: Update element styles, visibility, CSS classes
        - delete_element: Remove an element from a page
        - create_actions: Add actions to elements (CRUD, notifications, navigation)

        Element types available:
        - Layout: column (multi-column), form_container (for forms), simple_container
        - Display: heading, text, button, link, image
        - Form inputs: input_text, choice, checkbox, datetime_picker, record_selector
        - Collections: table (data table), repeat (card/list repeater)

        Action types available:
        - notification: Show a toast notification
        - open_page: Navigate to another page
        - create_row, update_row, delete_row: CRUD operations
        - refresh_data_source: Reload data
        - logout: Log out user
        """

        @udspy.module_callback
        def _load_page_content_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            new_tools = [
                udspy.Tool(list_elements),
                udspy.Tool(create_elements),
                udspy.Tool(update_elements),
                udspy.Tool(delete_element),
                udspy.Tool(create_actions),
            ]
            observation.append(
                "- Use `list_elements` to list existing elements on a page."
            )
            observation.append(
                "- Use `create_elements` to create UI elements with optional styling."
            )
            observation.append(
                "- Use `update_elements` to update element styles, visibility, or CSS classes."
            )
            observation.append(
                "- Use `delete_element` to remove an element from a page."
            )
            observation.append(
                "- Use `create_actions` to add actions to elements "
                "(create/update/delete rows in tables, notifications, navigation)."
            )

            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_page_content_tools

    return load_page_content_tools


class PageContentToolFactoryToolType(AssistantToolType):
    type = "page_content_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_page_content_tool_factory(user, workspace, tool_helpers)


# =============================================================================
# Theme Tool Factory
# =============================================================================


def get_theme_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    Returns a tool factory that provides theme customization tools.
    """

    from .types.theme import (
        ButtonThemeUpdate,
        ColorThemeUpdate,
        ImageThemeUpdate,
        InputThemeUpdate,
        LinkThemeUpdate,
        PageThemeUpdate,
        TableThemeUpdate,
        TypographyThemeUpdate,
    )

    def get_theme(application_id: int) -> dict[str, Any]:
        """
        Get the current theme settings for an application builder.

        - Returns all theme properties grouped by category.
        - Categories: colors, typography, buttons, links, images, page, inputs, tables.
        - Use this to understand current theme before making updates.
        """

        nonlocal user, workspace, tool_helpers

        builder = utils.get_builder(user, workspace, application_id)

        tool_helpers.update_status(
            _("Getting theme for %(app_name)s...") % {"app_name": builder.name}
        )

        theme = utils.get_builder_theme(builder)
        return {"theme": theme}

    def update_theme(
        application_id: int,
        colors: ColorThemeUpdate | None = None,
        typography: TypographyThemeUpdate | None = None,
        buttons: ButtonThemeUpdate | None = None,
        links: LinkThemeUpdate | None = None,
        images: ImageThemeUpdate | None = None,
        page: PageThemeUpdate | None = None,
        inputs: InputThemeUpdate | None = None,
        tables: TableThemeUpdate | None = None,
    ) -> dict[str, Any]:
        """
        Update theme settings for an application builder.

        - Only provide the categories you want to update.
        - Each category accepts partial updates (only set fields are updated).
        - Colors use hex format with alpha (e.g., '#5190efff').
        - Use 'primary', 'secondary', 'border' to reference theme colors.
        - Font weights: 'regular', 'medium', 'semi_bold', 'bold'.
        - Alignments: 'left', 'center', 'right'.

        IMPORTANT - Color Contrast:
        When updating colors (especially primary_color, secondary_color, or page background),
        ensure proper contrast with text and UI elements. Consider updating these together:
        - typography: body_text_color and heading text colors
        - buttons: text_color, background_color, hover/active states
        - inputs: label_text_color, input_text_color, input_background_color
        - tables: header_text_color, header_background_color, cell_background_color
        - links: text_color, hover_text_color

        Categories:
        - colors: primary_color, secondary_color, border_color, success/warning/error colors
        - typography: body_* props, heading_1 through heading_6 (including colors, fonts, sizes)
        - buttons: font, colors, border, padding, hover/active states
        - links: font, colors, hover/active states
        - images: alignment, max_width, max_height, border_radius, constraint
        - page: background_color, background_mode
        - inputs: label_* and input_* properties
        - tables: border, header, cell, separator styling
        """

        nonlocal user, workspace, tool_helpers

        builder = utils.get_builder(user, workspace, application_id)

        tool_helpers.update_status(
            _("Updating theme for %(app_name)s...") % {"app_name": builder.name}
        )

        # Flatten the grouped updates to individual theme properties
        flat_kwargs = utils.flatten_theme_update(
            colors=colors,
            typography=typography,
            buttons=buttons,
            links=links,
            images=images,
            page=page,
            inputs=inputs,
            tables=tables,
        )

        if flat_kwargs:
            from baserow.contrib.builder.theme.service import ThemeService

            ThemeService().update_theme(user, builder, **flat_kwargs)

        # Return the updated theme
        theme = utils.get_builder_theme(builder)
        return {"updated": True, "theme": theme}

    def load_theme_tools():
        """
        TOOL LOADER: Loads tools to customize the application theme.

        Call this loader when you need to:
        - View current theme settings (colors, typography, buttons, etc.)
        - Update application-wide styling (colors, fonts, spacing, etc.)
        - Customize the look and feel of the entire application

        After calling this loader, you will have access to:
        - get_theme: Get current theme settings grouped by category
        - update_theme: Update theme settings by category

        Theme categories:
        - colors: Primary, secondary, border, success/warning/error colors
        - typography: Body text and headings (1-6) font settings
        - buttons: Button styling including hover and active states
        - links: Link styling including hover and active states
        - images: Default image alignment, sizing, and border radius
        - page: Page background color and image mode
        - inputs: Form input and label styling
        - tables: Table border, header, cell, and separator styling
        """

        @udspy.module_callback
        def _load_theme_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            new_tools = [
                udspy.Tool(get_theme),
                udspy.Tool(update_theme),
            ]
            observation.append(
                "- Use `get_theme` to view current theme settings grouped by category."
            )
            observation.append(
                "- Use `update_theme` to update theme settings (colors, typography, buttons, etc.)."
            )

            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_theme_tools

    return load_theme_tools


class ThemeToolFactoryToolType(AssistantToolType):
    type = "theme_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_theme_tool_factory(user, workspace, tool_helpers)


# =============================================================================
# Backward Compatibility Wrappers (DEPRECATED - for tests only)
# =============================================================================


def get_list_pages_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable:
    """
    DEPRECATED: Use PageToolFactoryToolType instead.

    Returns a standalone list_pages function for backward compatibility with tests.
    """

    def list_pages(application_id: int) -> dict[str, Any]:
        """List all pages in an application builder."""

        builder = utils.get_builder(user, workspace, application_id)

        tool_helpers.update_status(
            _("Listing pages in %(app_name)s...") % {"app_name": builder.name}
        )

        pages = utils.list_pages(builder)
        return {"pages": [p.model_dump() for p in pages]}

    return list_pages


def get_element_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    DEPRECATED: Use PageContentToolFactoryToolType instead.

    Returns a tool factory that provides element tools for backward compatibility.
    """

    return get_page_content_tool_factory(user, workspace, tool_helpers)


def get_data_source_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    DEPRECATED: Use PageToolFactoryToolType instead.

    Returns a tool factory that provides data source tools for backward compatibility.
    """

    return get_page_tool_factory(user, workspace, tool_helpers)


def get_workflow_action_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], Any]:
    """
    DEPRECATED: Use PageContentToolFactoryToolType instead.

    Returns a tool factory that provides workflow action tools for backward compatibility.
    This is an alias for get_page_content_tool_factory but the tests expect
    create_workflow_actions instead of create_actions.
    """

    def load_workflow_action_tools():
        """
        TOOL LOADER: Loads tools to manage workflow actions on pages.
        """

        @udspy.module_callback
        def _load_workflow_action_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            def create_workflow_actions(
                page_id: int,
                workflow_actions: list[AnyWorkflowActionCreate],
                element_refs: dict[str, int] | None = None,
                data_source_refs: dict[str, int] | None = None,
            ) -> dict[str, Any]:
                """Create workflow actions attached to elements."""

                if not workflow_actions:
                    return {"created_workflow_actions": []}

                page = utils.get_page(user, page_id)
                integration = utils.get_local_baserow_integration(page.builder)

                tool_helpers.update_status(
                    _("Creating %(count)d actions...")
                    % {"count": len(workflow_actions)}
                )

                element_ref_to_id_map = element_refs or {}
                data_source_ref_to_id_map = data_source_refs or {}
                created_actions = []

                with transaction.atomic():
                    for action_create in workflow_actions:
                        _action, action_id = utils.create_workflow_action(
                            user,
                            page,
                            action_create,
                            element_ref_to_id_map,
                            data_source_ref_to_id_map,
                            integration,
                        )

                        created_actions.append(
                            {
                                "id": action_id,
                                "type": action_create.type,
                                "element_ref": action_create.element_ref,
                                "event": action_create.event,
                            }
                        )

                return {"created_workflow_actions": created_actions}

            new_tools = [
                udspy.Tool(create_workflow_actions),
            ]
            observation.append(
                "- Use `create_workflow_actions` to add actions to elements."
            )

            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_workflow_action_tools

    return load_workflow_action_tools
