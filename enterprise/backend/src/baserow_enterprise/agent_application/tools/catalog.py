"""
The catalog of workspace tools a user can grant to an agent, with the human
readable labels the tool permissions UI shows. Row create/update/delete are
dynamic per-table tools at run time (unlocked by `load_row_tools`), so they
are exposed here as synthetic catalog entries that the runtime names map back
onto.
"""

import re
from functools import lru_cache

from baserow_enterprise.assistant.tools.registries import assistant_tool_registry

from .classification import is_write_tool

# Tool groups that only make sense in the interactive assistant.
EXCLUDED_GROUPS = {"navigation"}
# Mode switching only exists for the assistant's mode-filtered toolset.
EXCLUDED_TOOLS = {"switch_mode"}

ROW_TOOL_LOADER = "load_row_tools"
SYNTHETIC_ROW_TOOLS = ("create_rows", "update_rows", "delete_rows")
ROW_TOOL_OPERATIONS = {
    "create_rows": "create",
    "update_rows": "update",
    "delete_rows": "delete",
}

GROUP_LABELS = {
    "core": "Workspace",
    "database": "Databases",
    "automation": "Automations",
    "builder": "Applications",
    "search_user_docs": "Search",
}

TOOL_METADATA: dict[str, tuple[str, str]] = {
    # core
    "list_builders": (
        "List applications",
        "See the databases, applications, automations and dashboards",
    ),
    "create_builders": (
        "Create applications",
        "Add a new database, application or automation",
    ),
    "update_builder": (
        "Edit application settings",
        "Rename an application or change its settings",
    ),
    # database
    "list_tables": ("List tables", "See the tables inside a database"),
    "get_tables_schema": ("Read table structure", "Field names, types and options"),
    "list_rows": ("Read rows", "Read row data, with filters and search"),
    "list_views": ("List views", "See the views of a table"),
    "generate_formula": ("Write formulas", "Draft a formula for a formula field"),
    "create_rows": ("Create rows", "Add new rows to a table"),
    "update_rows": ("Update rows", "Change values in existing rows"),
    "delete_rows": ("Delete rows", "Move rows to the trash"),
    "create_tables": ("Create tables", "Add tables to a database"),
    "create_fields": ("Add fields", "Add fields to a table"),
    "update_fields": ("Edit fields", "Rename fields or change their type"),
    "delete_fields": ("Delete fields", "Remove fields and their data"),
    "create_views": ("Create views", "Add grid, gallery or form views"),
    "create_view_filters": ("Add view filters", "Filter and sort views"),
    # automation
    "list_workflows": ("List automations", "See existing workflows"),
    "list_nodes": ("Read workflow steps", "Triggers and actions inside a workflow"),
    "create_workflows": ("Create automations", "Add a new workflow"),
    "add_nodes": ("Add steps", "Add triggers or actions to a workflow"),
    "update_nodes": ("Edit steps", "Change the settings of a step"),
    "delete_nodes": ("Delete steps", "Remove steps from a workflow"),
    # builder
    "list_pages": ("List pages", "See the pages of an application"),
    "create_pages": ("Create pages", "Add pages to an application"),
    "update_page": ("Edit pages", "Rename pages or change their path"),
    "list_data_sources": ("List data sources", "Data connected to a page"),
    "create_data_sources": ("Add data sources", "Connect tables to a page"),
    "update_data_source": ("Edit data sources", "Change what a data source loads"),
    "list_elements": ("Read page elements", "Elements and their settings"),
    "create_display_elements": (
        "Add display elements",
        "Headings, text, buttons, links and images",
    ),
    "create_layout_elements": (
        "Add layout elements",
        "Columns, containers, headers, footers and menus",
    ),
    "create_form_elements": ("Add form elements", "Forms and their input fields"),
    "create_collection_elements": (
        "Add collection elements",
        "Tables and repeat elements",
    ),
    "update_element": ("Edit elements", "Change content or settings"),
    "update_element_style": (
        "Style elements",
        "Change spacing, colors and theme overrides",
    ),
    "move_elements": ("Move elements", "Reorder elements on a page"),
    "list_actions": ("List actions", "See the workflow actions on a page"),
    "create_actions": ("Add actions", "Attach actions to buttons and forms"),
    "add_action_field_mapping": (
        "Map action fields",
        "Connect form values to row fields",
    ),
    "setup_page": (
        "Set up pages",
        "Create data sources, elements and actions in one go",
    ),
    "setup_user_source": (
        "Set up user sources",
        "Let the application have logged-in users",
    ),
    "set_theme": ("Change the theme", "Update colors and fonts of an application"),
    # docs
    "search_user_docs": ("Search Baserow docs", "Look up feature guides"),
}

_DYNAMIC_ROW_TOOL_RE = re.compile(r"^(create|update|delete)_rows_in_table_\d+$")


def humanize_tool_name(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


@lru_cache(maxsize=1024)
def to_catalog_name(tool_name: str) -> str:
    """
    Maps a runtime tool name onto its catalog entry: the dynamic per-table
    row tools (`create_rows_in_table_12`) belong to the synthetic
    `create_rows` entry; every other tool is its own entry.
    """

    match = _DYNAMIC_ROW_TOOL_RE.match(tool_name)
    if match:
        return f"{match.group(1)}_rows"
    return tool_name


def _entry(name: str, group: str) -> dict:
    label, description = TOOL_METADATA.get(name, (humanize_tool_name(name), ""))
    return {
        "name": name,
        "group": group,
        "group_label": GROUP_LABELS.get(group, humanize_tool_name(group)),
        "label": label,
        "description": description,
        "is_write": is_write_tool(name),
    }


def list_workspace_tools() -> list[dict]:
    """
    The universe of workspace tools a user can individually grant to an
    agent. The row loader itself is not listed because it is derived from
    the three synthetic row entries. Copies are returned so callers can't
    mutate the cached catalog.
    """

    return [dict(tool) for tool in _catalog()]


@lru_cache(maxsize=1)
def _catalog() -> tuple[dict, ...]:
    # The registry is static once the apps are ready, and this runs on every
    # agent run and permissions request.
    tools = []
    for tool_type in assistant_tool_registry.get_all():
        if tool_type.type in EXCLUDED_GROUPS:
            continue
        for func in tool_type.get_tool_functions():
            name = func.__name__
            if name in EXCLUDED_TOOLS or name == ROW_TOOL_LOADER:
                continue
            tools.append(_entry(name, tool_type.type))
            if name == "list_rows":
                tools.extend(
                    _entry(row_tool, "database") for row_tool in SYNTHETIC_ROW_TOOLS
                )
    return tuple(tools)


@lru_cache(maxsize=1)
def catalog_tool_names() -> frozenset[str]:
    return frozenset(tool["name"] for tool in list_workspace_tools())
