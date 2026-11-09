from dataclasses import dataclass

from django.db import transaction

from asgiref.sync import async_to_sync
from loguru import logger

from .client import MCPServerConnection, MCPToolDefinition, fetch_tools
from .exceptions import MCPServerUnreachable
from .models import MCPServerIntegration, MCPServerTool


@dataclass(frozen=True)
class MCPToolSettings:
    name: str
    enabled: bool | None = None
    changes_data: bool | None = None


class MCPServerHandler:
    def fetch_remote_tools(
        self, integration: MCPServerIntegration
    ) -> list[MCPToolDefinition]:
        """
        Ask the server for its tools. Never call this inside a transaction: the
        server may take a while to answer.

        :param integration: The server.
        :raises MCPServerUnreachable: When the server can't be reached or fails.
        :return: The tools the server lists.
        """

        try:
            return async_to_sync(fetch_tools)(
                MCPServerConnection.from_integration(integration)
            )
        except Exception as exc:
            logger.info(
                "MCP server {} tools could not be listed ({})",
                integration.id,
                type(exc).__name__,
            )
            raise MCPServerUnreachable() from exc

    def store_tools(
        self,
        integration: MCPServerIntegration,
        definitions: list[MCPToolDefinition],
    ) -> list[MCPServerTool]:
        """
        Replace the stored snapshot with the server's current tools. New tools
        start off. A tool that is on and changed is turned off and flagged, so an
        editor reviews it before the Agent can call it again. A tool the server no
        longer lists is kept, marked removed and off, so turning it back on later
        is a deliberate choice.

        :param integration: The server.
        :param definitions: Its tools, as just listed.
        :return: The stored tools, in the server's order.
        """

        with transaction.atomic():
            existing = {
                tool.name: tool
                for tool in MCPServerTool.objects.select_for_update().filter(
                    integration=integration
                )
            }
            listed = set()
            to_create, to_update = [], []
            for order, definition in enumerate(definitions):
                listed.add(definition.name)
                values = {
                    "title": definition.title[:255],
                    "description": definition.description,
                    "input_schema": definition.input_schema,
                    "annotations": definition.annotations,
                    "definition_hash": definition.definition_hash,
                    "order": order,
                    "removed": False,
                }
                tool = existing.get(definition.name)
                if tool is None:
                    to_create.append(
                        MCPServerTool(
                            integration=integration, name=definition.name, **values
                        )
                    )
                    continue
                if tool.definition_hash != definition.definition_hash and tool.enabled:
                    tool.enabled = False
                    tool.changed_since_review = True
                for key, value in values.items():
                    setattr(tool, key, value)
                to_update.append(tool)
            for name, tool in existing.items():
                if name not in listed:
                    tool.removed = True
                    tool.enabled = False
                    to_update.append(tool)

            MCPServerTool.objects.bulk_create(to_create)
            MCPServerTool.objects.bulk_update(
                to_update,
                [
                    "title",
                    "description",
                    "input_schema",
                    "annotations",
                    "definition_hash",
                    "order",
                    "removed",
                    "enabled",
                    "changed_since_review",
                ],
            )
        return list(integration.tools.all())

    def refresh_tools(self, integration: MCPServerIntegration) -> list[MCPServerTool]:
        return self.store_tools(integration, self.fetch_remote_tools(integration))

    def update_tools(
        self, integration: MCPServerIntegration, settings: list[MCPToolSettings]
    ) -> list[MCPServerTool]:
        """
        Turn tools on or off and say whether they change data. Saving a tool
        marks its current definition as reviewed.

        :param integration: The server.
        :param settings: Per tool, the values to change. Unknown names are
            ignored, and a removed tool can't be turned on.
        :return: The stored tools.
        """

        by_name = {setting.name: setting for setting in settings}
        with transaction.atomic():
            tools = list(
                MCPServerTool.objects.select_for_update().filter(
                    integration=integration, name__in=by_name.keys()
                )
            )
            for tool in tools:
                setting = by_name[tool.name]
                if setting.enabled is not None:
                    tool.enabled = setting.enabled and not tool.removed
                if setting.changes_data is not None:
                    tool.changes_data = setting.changes_data
                tool.changed_since_review = False
            MCPServerTool.objects.bulk_update(
                tools, ["enabled", "changes_data", "changed_since_review"]
            )
        return list(integration.tools.all())

    def get_enabled_tools(
        self, integration: MCPServerIntegration
    ) -> list[MCPServerTool]:
        return list(integration.tools.filter(enabled=True, removed=False))
