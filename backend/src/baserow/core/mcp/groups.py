from typing import List

from baserow.core.registry import Instance, Registry

GROUP_DATABASE_READ = "database_read"
GROUP_DATABASE_EDIT = "database_edit"
GROUP_DATABASE_DELETE = "database_delete"
GROUP_AUTOMATION_READ = "automation_read"
GROUP_AUTOMATION_EDIT = "automation_edit"
GROUP_AUTOMATION_DELETE = "automation_delete"

AREA_DATABASE = "database"
AREA_AUTOMATION = "automation"


class MCPToolGroup(Instance):
    """
    A set of MCP tools the user turns on or off together when connecting an app.
    Groups only exist in the UI: an endpoint stores tool names, so a tool added to
    a group later stays off for existing endpoints.
    """

    title: str
    """English name, shown when the frontend has no translation for the group."""

    area: str
    """The part of Baserow the tools work on, one of the ``AREA_*`` constants."""

    read_only_preset: bool = False
    """Whether the "Read only" preset turns this group on."""

    order: int
    """Position of the group in the consent page and Settings."""


class MCPToolGroupRegistry(Registry[MCPToolGroup]):
    name = "mcp_tool_groups"

    def get_ordered(self) -> List[MCPToolGroup]:
        return sorted(self.registry.values(), key=lambda group: group.order)


class DatabaseReadMCPToolGroup(MCPToolGroup):
    type = GROUP_DATABASE_READ
    title = "Read databases"
    area = AREA_DATABASE
    read_only_preset = True
    order = 10


class DatabaseEditMCPToolGroup(MCPToolGroup):
    type = GROUP_DATABASE_EDIT
    title = "Edit databases"
    area = AREA_DATABASE
    order = 20


class DatabaseDeleteMCPToolGroup(MCPToolGroup):
    type = GROUP_DATABASE_DELETE
    title = "Delete in databases"
    area = AREA_DATABASE
    order = 30


class AutomationReadMCPToolGroup(MCPToolGroup):
    type = GROUP_AUTOMATION_READ
    title = "Read automations"
    area = AREA_AUTOMATION
    order = 40


class AutomationEditMCPToolGroup(MCPToolGroup):
    type = GROUP_AUTOMATION_EDIT
    title = "Edit automations"
    area = AREA_AUTOMATION
    order = 50


class AutomationDeleteMCPToolGroup(MCPToolGroup):
    type = GROUP_AUTOMATION_DELETE
    title = "Delete in automations"
    area = AREA_AUTOMATION
    order = 60


mcp_tool_group_registry = MCPToolGroupRegistry()
