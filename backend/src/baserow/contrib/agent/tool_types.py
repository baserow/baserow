from baserow.contrib.database.tools import fields, rows, tables, views

from .registries import AgentToolType


class DatabaseAgentToolType(AgentToolType):
    group = "database"


class ListTablesAgentToolType(DatabaseAgentToolType):
    type = "list_tables"
    function = tables.list_tables


class GetTableSchemaAgentToolType(DatabaseAgentToolType):
    type = "get_table_schema"
    function = tables.get_table_schema


class ListTableRowsAgentToolType(DatabaseAgentToolType):
    type = "list_table_rows"
    function = rows.list_table_rows


class ListViewsAgentToolType(DatabaseAgentToolType):
    type = "list_views"
    function = views.list_views


class CreateTablesAgentToolType(DatabaseAgentToolType):
    type = "create_tables"
    function = tables.create_tables
    changes_data = True


class CreateFieldsAgentToolType(DatabaseAgentToolType):
    type = "create_fields"
    function = fields.create_fields
    changes_data = True


class UpdateFieldsAgentToolType(DatabaseAgentToolType):
    type = "update_fields"
    function = fields.update_fields
    changes_data = True


class DeleteFieldsAgentToolType(DatabaseAgentToolType):
    type = "delete_fields"
    function = fields.delete_fields
    changes_data = True


class CreateViewsAgentToolType(DatabaseAgentToolType):
    type = "create_views"
    function = views.create_views
    changes_data = True


class CreateViewFiltersAgentToolType(DatabaseAgentToolType):
    type = "create_view_filters"
    function = views.create_view_filters
    changes_data = True


class CreateRowsAgentToolType(DatabaseAgentToolType):
    type = "create_rows"
    function = rows.create_rows
    changes_data = True


class UpdateRowsAgentToolType(DatabaseAgentToolType):
    type = "update_rows"
    function = rows.update_rows
    changes_data = True


class DeleteRowsAgentToolType(DatabaseAgentToolType):
    type = "delete_rows"
    function = rows.delete_rows
    changes_data = True
