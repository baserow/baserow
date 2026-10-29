from baserow.contrib.database.tools import fields, rows, tables, views

from .registries import AgentToolType


class ListTablesAgentToolType(AgentToolType):
    type = "list_tables"
    function = tables.list_tables


class GetTableSchemaAgentToolType(AgentToolType):
    type = "get_table_schema"
    function = tables.get_table_schema


class ListTableRowsAgentToolType(AgentToolType):
    type = "list_table_rows"
    function = rows.list_table_rows


class ListViewsAgentToolType(AgentToolType):
    type = "list_views"
    function = views.list_views


class CreateTablesAgentToolType(AgentToolType):
    type = "create_tables"
    function = tables.create_tables
    changes_data = True


class CreateFieldsAgentToolType(AgentToolType):
    type = "create_fields"
    function = fields.create_fields
    changes_data = True


class UpdateFieldsAgentToolType(AgentToolType):
    type = "update_fields"
    function = fields.update_fields
    changes_data = True


class DeleteFieldsAgentToolType(AgentToolType):
    type = "delete_fields"
    function = fields.delete_fields
    changes_data = True


class CreateViewsAgentToolType(AgentToolType):
    type = "create_views"
    function = views.create_views
    changes_data = True


class CreateViewFiltersAgentToolType(AgentToolType):
    type = "create_view_filters"
    function = views.create_view_filters
    changes_data = True


class CreateRowsAgentToolType(AgentToolType):
    type = "create_rows"
    function = rows.create_rows
    changes_data = True


class UpdateRowsAgentToolType(AgentToolType):
    type = "update_rows"
    function = rows.update_rows
    changes_data = True


class DeleteRowsAgentToolType(AgentToolType):
    type = "delete_rows"
    function = rows.delete_rows
    changes_data = True
