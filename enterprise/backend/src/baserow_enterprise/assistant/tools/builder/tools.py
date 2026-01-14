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

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


__all__ = [
    "PageToolFactoryToolType",
    "PageContentToolFactoryToolType",
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

    def load_page_content_tools():
        """
        TOOL LOADER: Loads tools to manage UI elements and actions on pages.

        Call this loader when you need to:
        - List or create UI elements (headings, buttons, forms, tables, etc.)
        - Add actions to elements (form submit, button click, navigation, etc.)
        - Build interactive page content

        After calling this loader, you will have access to:
        - list_elements: List existing elements on a page
        - create_elements: Create UI elements (headings, buttons, forms, tables, etc.)
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
                udspy.Tool(create_actions),
            ]
            observation.append(
                "- Use `list_elements` to list existing elements on a page."
            )
            observation.append(
                "- Use `create_elements` to create UI elements (headings, buttons, forms, tables, etc.)."
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
