from typing import Any

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools import fields, rows, tables, views
from baserow.core.chat_runs.tool_input import tool_input_preview
from baserow.core.tools import ToolContext

from .registries import AgentToolType


def _table_facts(
    ctx: ToolContext, table_id: int, count: int | None = None
) -> dict[str, Any]:
    """
    Name a table after the tool authorized its operation in this workspace.

    :param ctx: Who acted and where.
    :param table_id: The table the successful tool checked.
    :param count: The confirmed number of handled items, when available.
    :return: A count and the table name when it still exists.
    """

    facts = {} if count is None else {"count": count}
    name = (
        Table.objects.filter(id=table_id, database__workspace=ctx.workspace)
        .values_list("name", flat=True)
        .first()
    )
    if name is not None:
        facts["table"] = name
    return facts


class DatabaseAgentToolType(AgentToolType):
    group = "database"
    step_count_argument: str | None = None
    step_input_arguments: dict[str, type] = {}

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Count requested items and preview the explicitly approved input values.

        :param arguments: The tool's arguments.
        :return: A count and bounded values for tools that opt into input display.
        """

        items = arguments.get(self.step_count_argument)
        summary = {"requested_count": len(items)} if isinstance(items, list) else {}
        values = {
            key: arguments[key]
            for key, expected_type in self.step_input_arguments.items()
            if key in arguments and type(arguments[key]) is expected_type
        }
        if values:
            summary.update(tool_input_preview(values))
        return summary


class ListTablesAgentToolType(DatabaseAgentToolType):
    type = "list_tables"
    function = tables.list_tables


class GetTableSchemaAgentToolType(DatabaseAgentToolType):
    type = "get_table_schema"
    function = tables.get_table_schema
    step_count_argument = "table_ids"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        names = [table["name"] for table in result]
        return {"table": ", ".join(names)} if names else {}


class ListTableRowsAgentToolType(DatabaseAgentToolType):
    type = "list_table_rows"
    function = rows.list_table_rows

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result["results"]))


class ListViewsAgentToolType(DatabaseAgentToolType):
    type = "list_views"
    function = views.list_views

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"])


class CreateTablesAgentToolType(DatabaseAgentToolType):
    type = "create_tables"
    function = tables.create_tables
    changes_data = True
    step_input_arguments = {"database_id": int, "tables": list}
    step_count_argument = "tables"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        names = [table["name"] for table in result["created_tables"]]
        facts: dict[str, Any] = {"count": len(names)}
        if names:
            facts["table"] = ", ".join(names)
        return facts


class CreateFieldsAgentToolType(DatabaseAgentToolType):
    type = "create_fields"
    function = fields.create_fields
    changes_data = True
    step_input_arguments = {"table_id": int, "fields": list}
    step_count_argument = "fields"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result["created_fields"]))


class UpdateFieldsAgentToolType(DatabaseAgentToolType):
    type = "update_fields"
    function = fields.update_fields
    changes_data = True
    step_input_arguments = {"fields": list}
    step_count_argument = "fields"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["updated_fields"])}


class DeleteFieldsAgentToolType(DatabaseAgentToolType):
    type = "delete_fields"
    function = fields.delete_fields
    changes_data = True
    step_input_arguments = {"field_ids": list}
    step_count_argument = "field_ids"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["deleted_field_ids"])}


class CreateViewsAgentToolType(DatabaseAgentToolType):
    type = "create_views"
    function = views.create_views
    changes_data = True
    step_input_arguments = {"table_id": int, "views": list}
    step_count_argument = "views"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result["created_views"]))


class CreateViewFiltersAgentToolType(DatabaseAgentToolType):
    type = "create_view_filters"
    function = views.create_view_filters
    changes_data = True
    step_input_arguments = {"view_filters": list}

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        summary = super().get_step_input(arguments)
        items = arguments.get("view_filters")
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("view_id"), int)
            for item in items
        ):
            return summary
        summary["requested_count"] = len({item["view_id"] for item in items})
        return summary

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {
            "count": len(
                {
                    item["view_id"]
                    for item in result["created_view_filters"]
                    if item["filters"]
                }
            )
        }


class CreateRowsAgentToolType(DatabaseAgentToolType):
    type = "create_rows"
    function = rows.create_rows
    changes_data = True
    step_input_arguments = {"table_id": int, "rows": list}
    step_count_argument = "rows"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result))


class UpdateRowsAgentToolType(DatabaseAgentToolType):
    type = "update_rows"
    function = rows.update_rows
    changes_data = True
    step_input_arguments = {"table_id": int, "rows": list}
    step_count_argument = "rows"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result))


class DeleteRowsAgentToolType(DatabaseAgentToolType):
    type = "delete_rows"
    function = rows.delete_rows
    changes_data = True
    step_input_arguments = {"table_id": int, "row_ids": list}
    step_count_argument = "row_ids"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(set(arguments["row_ids"])))
