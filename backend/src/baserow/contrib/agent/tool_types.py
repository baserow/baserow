from typing import Any

from baserow.contrib.database.tools import databases, fields, rows, tables, views
from baserow.contrib.database.tools.views import get_view
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.core.tools import ToolContext

from .database_previews import (
    database_reference,
    named_fields,
    readable_names,
    row_names,
    table_field_names,
    table_names,
    table_reference,
)
from .previews import StepPreview, mask, name_field_references
from .registries import AgentToolType


def _without(values: dict[str, Any], key: str) -> dict[str, Any]:
    """
    :param values: A requested item.
    :param key: The key the preview shows elsewhere.
    :return: The item without that key.
    """

    return {name: value for name, value in values.items() if name != key}


def _field_reference(
    field_id: int, names: dict[int, tuple[str, str]]
) -> dict[str, Any]:
    """
    :param field_id: A field the call names.
    :param names: The field and table names the identity can see, by field ID.
    :return: The field's and its table's names, or its ID as written.
    """

    if field_id not in names:
        return {"field_id": field_id}
    field_name, table_name = names[field_id]
    return {"field": field_name, "table": table_name}


def _row_reference(row_id: int, names: dict[int, str]) -> dict[str, Any]:
    """
    :param row_id: A row the call names.
    :param names: The row names the identity can see, by row ID.
    :return: The row's name, or its ID as written.
    """

    return {"row": names[row_id]} if row_id in names else {"row_id": row_id}


def _named_link(request: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    """
    :param request: A requested field.
    :param names: The names of the tables the identity can see, by ID.
    :return: The field, with an integer ``linked_table`` the identity can see named.
    """

    linked = request.get("linked_table")
    if isinstance(linked, int) and linked in names:
        return {**request, "linked_table": names[linked]}
    return request


class DatabaseAgentToolType(AgentToolType):
    group = "database"
    step_count_argument: str | None = None

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Count the requested items, known as soon as the call starts.

        :param arguments: The tool's arguments.
        :return: The requested count, for tools that have one.
        """

        items = arguments.get(self.step_count_argument)
        return {"requested_count": len(items)} if isinstance(items, list) else {}


class TableReadAgentToolType(DatabaseAgentToolType):
    """A read of one table, titled with the table's name."""

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        return StepPreview(table_reference(ctx, arguments["table_id"])[1])


class ListDatabasesAgentToolType(DatabaseAgentToolType):
    type = "list_databases"
    function = databases.list_databases


class CreateDatabaseAgentToolType(DatabaseAgentToolType):
    type = "create_database"
    function = databases.create_database
    changes_data = True

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        return StepPreview({"name": arguments["name"]})

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"database": result["created_database"]["name"]}


class UpdateDatabaseAgentToolType(DatabaseAgentToolType):
    type = "update_database"
    function = databases.update_database
    changes_data = True

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        return StepPreview(
            {
                **database_reference(ctx, arguments["database_id"]),
                "name": arguments["name"],
            }
        )

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {
            "database": result["updated_database"]["name"],
            "changed": result["changed"],
        }


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


class ListTableRowsAgentToolType(TableReadAgentToolType):
    type = "list_table_rows"
    function = rows.list_table_rows

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["results"])}


class ListViewsAgentToolType(TableReadAgentToolType):
    type = "list_views"
    function = views.list_views


class CreateTablesAgentToolType(DatabaseAgentToolType):
    type = "create_tables"
    function = tables.create_tables
    changes_data = True
    step_count_argument = "tables"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        return StepPreview(
            database_reference(ctx, arguments["database_id"]),
            "tables",
            arguments["tables"],
        )

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        names = [table["name"] for table in result["created_tables"]]
        return {"count": len(names), **({"table": ", ".join(names)} if names else {})}


class CreateFieldsAgentToolType(DatabaseAgentToolType):
    type = "create_fields"
    function = fields.create_fields
    changes_data = True
    step_count_argument = "fields"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        _, reference = table_reference(ctx, arguments["table_id"])
        preview = StepPreview(reference, "fields")
        requests = preview.cut_items(arguments["fields"])
        linked_ids = [
            request["linked_table"]
            for request in requests
            if isinstance(request.get("linked_table"), int)
        ]
        linked = table_names(ctx, linked_ids) if linked_ids else {}
        preview.items = [_named_link(request, linked) for request in requests]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["created_fields"])}


class UpdateFieldsAgentToolType(DatabaseAgentToolType):
    type = "update_fields"
    function = fields.update_fields
    changes_data = True
    step_count_argument = "fields"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        preview = StepPreview({}, "fields")
        updates = preview.cut_items(arguments["fields"])
        names = named_fields(ctx, [update["field_id"] for update in updates])
        preview.items = [
            {
                **_field_reference(update["field_id"], names),
                "changes": _without(update, "field_id"),
            }
            for update in updates
        ]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["updated_fields"])}


class DeleteFieldsAgentToolType(DatabaseAgentToolType):
    type = "delete_fields"
    function = fields.delete_fields
    changes_data = True
    step_count_argument = "field_ids"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        preview = StepPreview({}, "fields")
        field_ids = preview.cut_items(arguments["field_ids"])
        names = named_fields(ctx, field_ids)
        preview.items = [_field_reference(field_id, names) for field_id in field_ids]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["deleted_field_ids"])}


class CreateViewsAgentToolType(DatabaseAgentToolType):
    type = "create_views"
    function = views.create_views
    changes_data = True
    step_count_argument = "views"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        names = table_field_names(ctx, table) if table else {}
        return StepPreview(
            reference, "views", name_field_references(arguments["views"], names)
        )

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["created_views"])}


class CreateViewFiltersAgentToolType(DatabaseAgentToolType):
    type = "create_view_filters"
    function = views.create_view_filters
    changes_data = True

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        items = arguments.get("view_filters")
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("view_id"), int)
            for item in items
        ):
            return {}
        return {"requested_count": len({item["view_id"] for item in items})}

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        preview = StepPreview({}, "views")
        for group in preview.cut_items(arguments["view_filters"]):
            try:
                view = get_view(ctx, group["view_id"])
            except ViewDoesNotExist:
                preview.items.append(group)
                continue
            names = table_field_names(ctx, view.table)
            preview.items.append(
                {
                    "view": view.name,
                    "table": view.table.name,
                    "filters": name_field_references(group["filters"], names),
                }
            )
        return preview

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
    step_count_argument = "rows"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        readable = readable_names(table) if table else set()
        return StepPreview(
            reference, "rows", [mask(row, readable) for row in arguments["rows"]]
        )

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result)}


class UpdateRowsAgentToolType(DatabaseAgentToolType):
    type = "update_rows"
    function = rows.update_rows
    changes_data = True
    step_count_argument = "rows"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        preview = StepPreview(reference, "rows")
        updates = preview.cut_items(arguments["rows"])
        names = (
            row_names(ctx, table, [update["id"] for update in updates]) if table else {}
        )
        readable = readable_names(table) if table else set()
        preview.items = [
            {
                **_row_reference(update["id"], names),
                "values": mask(_without(update, "id"), readable),
            }
            for update in updates
        ]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result)}


class DeleteRowsAgentToolType(DatabaseAgentToolType):
    type = "delete_rows"
    function = rows.delete_rows
    changes_data = True
    step_count_argument = "row_ids"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        preview = StepPreview(reference, "rows")
        row_ids = preview.cut_items(arguments["row_ids"])
        names = row_names(ctx, table, row_ids) if table else {}
        preview.items = [names.get(row_id, {"row_id": row_id}) for row_id in row_ids]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(arguments["row_ids"])}
