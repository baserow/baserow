from enum import StrEnum
from typing import Any

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools import fields, rows, tables, views
from baserow.core.chat_runs.tool_input import tool_input_preview
from baserow.core.tools import ToolContext

from .registries import AgentToolType, StepResources


class DatabaseToolResource(StrEnum):
    DATABASE = "database"
    TABLE = "table"
    FIELD = "field"
    VIEW = "view"


def _named_resources(kind: DatabaseToolResource, items: list[dict]) -> StepResources:
    return {(kind, item["id"]): item["name"] for item in items}


def _schema_resources(items: list[dict]) -> StepResources:
    resources = _named_resources(DatabaseToolResource.TABLE, items)
    for table in items:
        table_fields = table.get("fields", [])
        if table.get("primary_field"):
            table_fields = [table["primary_field"], *table_fields]
        resources.update(_named_resources(DatabaseToolResource.FIELD, table_fields))
        for field in table_fields:
            # The authorized schema call already disclosed linked-table names.
            if field.get("link_row_table_id") and field.get("link_row_table_name"):
                resources[(DatabaseToolResource.TABLE, field["link_row_table_id"])] = (
                    field["link_row_table_name"]
                )
    return resources


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
    step_target_resource: DatabaseToolResource | None = None
    step_target_argument: str | None = None
    step_target_item_key: str | None = None

    def get_step_target(
        self, arguments: dict[str, Any], resources: StepResources
    ) -> str | None:
        ids = arguments.get(self.step_target_argument)
        if self.step_target_item_key is not None:
            if not isinstance(ids, list) or any(not isinstance(i, dict) for i in ids):
                return None
            ids = [item.get(self.step_target_item_key) for item in ids]
        elif not isinstance(ids, list):
            ids = [ids]
        if not ids or any(type(item) is not int for item in ids):
            return None
        names = [resources.get((self.step_target_resource, item)) for item in ids]
        # A partially known batch must not appear to target only its known items.
        return ", ".join(dict.fromkeys(names)) if all(names) else None

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
    step_target_resource = DatabaseToolResource.DATABASE
    step_target_argument = "database_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return {
            **_named_resources(DatabaseToolResource.TABLE, result),
            **{
                (DatabaseToolResource.DATABASE, table["database_id"]): table[
                    "database_name"
                ]
                for table in result
            },
        }


class GetTableSchemaAgentToolType(DatabaseAgentToolType):
    type = "get_table_schema"
    function = tables.get_table_schema
    step_count_argument = "table_ids"
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_ids"

    def get_step_resources(self, result: Any) -> StepResources:
        return _schema_resources(result)

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        names = [table["name"] for table in result]
        return {"table": ", ".join(names)} if names else {}


class ListTableRowsAgentToolType(DatabaseAgentToolType):
    type = "list_table_rows"
    function = rows.list_table_rows
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(result["results"]))


class ListViewsAgentToolType(DatabaseAgentToolType):
    type = "list_views"
    function = views.list_views
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return _named_resources(DatabaseToolResource.VIEW, result["views"])

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
    step_target_resource = DatabaseToolResource.DATABASE
    step_target_argument = "database_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return _schema_resources([*result["created_tables"], *result["reused_tables"]])

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        names = [table["name"] for table in result["created_tables"]]
        existing = [table["name"] for table in result["reused_tables"]]
        facts: dict[str, Any] = {"count": len(names)}
        if names:
            facts["table"] = ", ".join(names)
        if existing:
            facts["existing_count"] = len(existing)
            facts["existing_table"] = ", ".join(existing)
        return facts


class CreateFieldsAgentToolType(DatabaseAgentToolType):
    type = "create_fields"
    function = fields.create_fields
    changes_data = True
    step_input_arguments = {"table_id": int, "fields": list}
    step_count_argument = "fields"
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return _named_resources(DatabaseToolResource.FIELD, result["created_fields"])

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
    step_target_resource = DatabaseToolResource.FIELD
    step_target_argument = "fields"
    step_target_item_key = "field_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return _named_resources(DatabaseToolResource.FIELD, result["updated_fields"])

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
    step_target_resource = DatabaseToolResource.FIELD
    step_target_argument = "field_ids"

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
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

    def get_step_resources(self, result: Any) -> StepResources:
        return _named_resources(DatabaseToolResource.VIEW, result["created_views"])

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        facts = _table_facts(ctx, arguments["table_id"], len(result["created_views"]))
        if existing := result.get("skipped_views"):
            facts["existing_count"] = len(set(existing))
        return facts


class CreateViewFiltersAgentToolType(DatabaseAgentToolType):
    type = "create_view_filters"
    function = views.create_view_filters
    changes_data = True
    step_input_arguments = {"view_filters": list}
    step_target_resource = DatabaseToolResource.VIEW
    step_target_argument = "view_filters"
    step_target_item_key = "view_id"

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
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

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
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

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
    step_target_resource = DatabaseToolResource.TABLE
    step_target_argument = "table_id"

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return _table_facts(ctx, arguments["table_id"], len(set(arguments["row_ids"])))
