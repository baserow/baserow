from typing import Any, Callable, Literal, Tuple

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.translation import gettext as _

import dspy
from loguru import logger
from pydantic import create_model

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.views.actions import (
    CreateViewActionType,
    CreateViewFilterActionType,
    UpdateViewFieldOptionsActionType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.actions import CreateApplicationActionType
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.tools.registries import AssistantToolType, ToolHelpers
from baserow_enterprise.assistant.types import (
    TableNavigationType,
    ToolSignature,
    ToolsUpgradeResponse,
    ViewNavigationType,
)

from . import utils
from .types import (
    AnyFieldItem,
    AnyFieldItemCreate,
    AnyViewFilterItem,
    AnyViewFilterItemCreate,
    AnyViewItemCreate,
    BaseTableItem,
    DatabaseItem,
    ListTablesFilterArg,
    TableItemCreate,
    view_item_registry,
)


def get_list_databases_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[], list[DatabaseItem]]:
    """
    Returns a function that lists all the databases the user has access to in the
    current workspace.
    """

    def list_databases() -> list[DatabaseItem]:
        """
        Lists all the databases the user can access.
        """

        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(_("Listing databases..."))

        applications_qs = CoreService().list_applications_in_workspace(
            user, workspace, specific=False
        )

        database_content_type = ContentType.objects.get_for_model(Database)

        return {
            "databases": [
                DatabaseItem(id=database.id, name=database.name).model_dump()
                for database in applications_qs.filter(
                    content_type=database_content_type
                )
            ]
        }

    return list_databases


class ListDatabasesToolType(AssistantToolType):
    type = "list_databases"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_list_databases_tool(user, workspace, tool_helpers)


def get_list_tables_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int], list[str]]:
    """
    Returns a function that lists all the tables in a given database the user has
    access to in the current workspace.
    """

    def list_tables(filters: ListTablesFilterArg) -> list[dict[str, Any]]:
        """
        List tables that verifies the filters

        - Always call this before creating new tables to avoid duplicates.
        - Always call this to link existing tables when table IDs are not known.
        """

        nonlocal user, workspace, tool_helpers

        tables = (
            utils.filter_tables(user, workspace)
            .filter(filters.to_orm_filter())
            .select_related("database")
        )

        databases = {}
        database_names = []
        for table in tables:
            if table.database_id not in databases:
                databases[table.database_id] = {
                    "id": table.database_id,
                    "name": table.database.name,
                    "tables": [],
                }
                database_names.append(table.database.name)
            databases[table.database_id]["tables"].append(
                {
                    "id": table.id,
                    "name": table.name,
                    "database_id": table.database_id,
                }
            )

        tool_helpers.update_status(
            _("Listing tables in %(database_names)s...")
            % {"database_names": ", ".join(database_names)}
        )

        if len(databases) == 0:
            return "No tables found"
        elif len(databases) == 1:
            # Return just the tables array when there's only one database
            return list(databases.values())[0]["tables"]
        else:
            return list(databases.values())

    return list_tables


class ListTablesToolType(AssistantToolType):
    type = "list_tables"
    thinking_message = "Looking for tables..."

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_list_tables_tool(user, workspace, tool_helpers)


def get_tables_schema_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int], list[str]]:
    """
    Returns a function that lists all the fields in a given table the user has
    access to in the current workspace.
    """

    def get_tables_schema(
        table_ids: list[int],
        full_schema: bool,
    ) -> list[dict[str, Any]]:
        """
        Returns the schema of the specified tables, including their fields if requested.
        Use `full_schema=True` to get all the fields, otherwise only the table names,
        IDs, primary keys, and relationships will be included.

        When to use: - Understanding table structure before creating/modifying fields -
        Checking existing field names to avoid duplicates - Understanding table
        relationships when creating link_row fields

        Remember: - Always call this before creating fields to avoid duplicate names -
        Use get_rows_tools() for any row operations - not this one
        """

        nonlocal user, workspace, tool_helpers

        if not table_ids:
            return []

        tables = utils.filter_tables(user, workspace).filter(id__in=table_ids)

        tool_helpers.update_status(
            _("Inspecting %(table_names)s schema...")
            % {"table_names": ", ".join(t.name for t in tables)}
        )

        return {
            "tables_schema": [
                ts.model_dump() for ts in utils.get_tables_schema(tables, full_schema)
            ]
        }

    return get_tables_schema


class GetTablesSchemaToolType(AssistantToolType):
    type = "get_tables_schema"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_tables_schema_tool(user, workspace, tool_helpers)


def get_create_database_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[str], dict[str, Any]]:
    """
    Returns a function that creates a database in the current workspace.
    """

    def create_database(name: str) -> dict[str, Any]:
        """
        Create a database in the current workspace and return its ID and name.
        **ALWAYS** create tables afterwards unless explicitly asked otherwise.

        - name: desired database name (must be unique in the workspace)
        - call list_databases first to avoid duplicates
        - call the create_tables tools afterwards unless explicitly asked otherwise
        """

        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(
            _("Creating database %(database_name)s...") % {"database_name": name}
        )

        with transaction.atomic():
            database = CreateApplicationActionType.do(
                user, workspace, "database", name=name
            )

        return {
            "created_database": DatabaseItem(
                id=database.id, name=database.name
            ).model_dump()
        }

    return create_database


class CreateDatabaseToolType(AssistantToolType):
    type = "create_database"
    thinking_message = "Creating a new database..."

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_create_database_tool(user, workspace, tool_helpers)


def get_create_tables_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[list[TableItemCreate]], list[dict[str, Any]]]:
    """
    Returns a function that creates a set of tables in a given database the user has
    access to
    """

    def create_tables(
        database_id: int, tables: list[TableItemCreate], add_sample_rows: bool = True
    ) -> list[dict[str, Any]]:
        """
        Creates tables with fields and rows in a database. **ALWAYS** add sample rows
        unless explicitly asked otherwise.

        - table names should be unique in a database
        - add meaningful fields with the appropriate types and relationships to other
          existing tables. The reversed link_row fields will be created automatically.
        - if add_sample_rows is True (default), add some example rows to each table
        """

        nonlocal user, workspace, tool_helpers

        if not tables:
            return {"created_tables": []}

        database = CoreService().get_application(
            user,
            database_id,
            specific=False,
            base_queryset=Database.objects.filter(workspace=workspace),
        )

        created_tables = []
        with transaction.atomic():
            for i, table in enumerate(tables):
                tool_helpers.update_status(
                    _("Creating table %(table_name)s...") % {"table_name": table.name}
                )

                created_table, __ = CreateTableActionType.do(
                    user, database, table.name, fill_example=False
                )
                created_tables.append(created_table)

                primary_field_item = table.primary_field
                primary_field = created_table.get_primary_field().specific
                new_field_type = field_type_registry.get(primary_field_item.type)
                UpdateFieldActionType.do(
                    user,
                    primary_field,
                    new_type_name=new_field_type.type,
                    name=primary_field_item.name,
                )

        # Now that we have all the tables created, we can create the fields
        notes = []
        for table, created_table in zip(tables, created_tables):
            with transaction.atomic():
                try:
                    utils.create_fields(user, created_table, table.fields, tool_helpers)
                except Exception as e:
                    notes.append(
                        f"Error creating fields for table_{created_table.id}: {e}.\n"
                        f"Please retry recreating fields for table_{created_table.id} manually."
                    )

        tool_helpers.navigate_to(
            TableNavigationType(
                type="database-table",
                database_id=database.id,
                table_id=created_table.id,
                table_name=created_table.name,
            )
        )

        if add_sample_rows:
            tools = {}
            instructions = []
            tool_helpers.update_status(
                _("Preparing example rows for these new tables...")
            )
            for table, created_table in zip(tables, created_tables):
                create_rows_tool = utils.get_table_rows_tools(
                    user, workspace, tool_helpers, created_table
                )["create"]
                tools[create_rows_tool.name] = create_rows_tool
                instructions.append(
                    f"- Create 5 example rows for table_{created_table.id}. Fill every relationship with valid data when possible."
                )

            predictor = dspy.Predict(ToolSignature)
            result = predictor(
                question=("\n".join(instructions)),
                tools=list(tools.values()),
            )
            for call in result.outputs.tool_calls:
                with transaction.atomic():
                    try:
                        result = tools[call.name](**call.args)
                        notes.append(
                            f"Rows created for table_{created_table.id}: {result}"
                        )
                    except Exception as e:
                        notes.append(
                            f"Error creating example rows for table_{created_table.id}: {e}\n."
                            f"Please retry recreating rows for table_{created_table.id} manually."
                        )

        return {
            "created_tables": [
                BaseTableItem(id=t.id, name=t.name).model_dump() for t in created_tables
            ],
            "notes": notes,
        }

    return create_tables


class CreateTablesToolType(AssistantToolType):
    type = "create_tables"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_create_tables_tool(user, workspace, tool_helpers)


def get_create_fields_tool(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: ToolHelpers,
) -> Callable[[int, list[AnyFieldItemCreate]], list[dict[str, Any]]]:
    """
    Returns a function that creates fields in a given table the user has access to
    in the current workspace.
    """

    def create_fields(
        table_id: int, fields: list[AnyFieldItemCreate]
    ) -> list[AnyFieldItem]:
        """
        Creates fields in the specified table.

        - Choose the most appropriate field type for each field.
        - Field names must be unique within a table: check existing names
          when needed and skip duplicates.
        - For link_row fields, ensure the linked table already exists in
          the same database; create it first if needed.
        """

        nonlocal user, workspace, tool_helpers

        if not fields:
            return []

        table = utils.filter_tables(user, workspace).get(id=table_id)

        with transaction.atomic():
            created_fields = utils.create_fields(user, table, fields, tool_helpers)
            return {"created_fields": [field.model_dump() for field in created_fields]}

    return create_fields


class CreateFieldsToolType(AssistantToolType):
    type = "create_fields"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_create_fields_tool(user, workspace, tool_helpers)


def get_list_rows_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int, int, int, list[int] | None], list[dict[str, Any]]]:
    """
    Returns a function that lists rows in a given table the user has access to in the
    current workspace.
    """

    def list_rows(
        table_id: int,
        offset: int = 0,
        limit: int = 10,
        field_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lists rows in the specified table.

        - Use offset and limit for pagination.
        - Use field_ids to limit the response to specific fields.
        """

        nonlocal user, workspace, tool_helpers

        table = utils.filter_tables(user, workspace).get(id=table_id)

        tool_helpers.update_status(
            _("Listing rows in %(table_name)s ") % {"table_name": table.name}
        )

        rows_qs = table.get_model().objects.all()
        rows = rows_qs[offset : offset + limit]

        response_model = create_model(
            f"ResponseTable{table.id}RowWithFieldFilter",
            id=(int, ...),
            __base__=utils.get_create_row_model(table, field_ids=field_ids),
        )

        return {
            "rows": [
                response_model.from_django_orm(row, field_ids).model_dump()
                for row in rows
            ],
            "total": rows_qs.count(),
        }

    return list_rows


class ListRowsToolType(AssistantToolType):
    type = "list_rows"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_list_rows_tool(user, workspace, tool_helpers)


def get_rows_meta_tool(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: ToolHelpers,
) -> Callable[[int, list[dict[str, Any]]], list[Any]]:
    """
    Returns a meta-tool that, given a table ID, returns an observation that says that
    new tools are available and a list of tools to create, update and delete rows
    in that table.
    """

    def get_rows_tools(
        table_ids: list[int],
        operations: list[Literal["create", "update", "delete"]],
    ) -> Tuple[str, list[Callable[[Any], Any]]]:
        """
        Generates row operation tools for specified tables. Required before:
        create/update/delete rows.
        """

        nonlocal user, workspace, tool_helpers

        observation = ["New tools are now available.\n"]

        new_tools = []
        tables = utils.filter_tables(user, workspace).filter(id__in=table_ids)
        for table in tables:
            table_tools = utils.get_table_rows_tools(
                user, workspace, tool_helpers, table
            )

            observation.append(f"Table '{table.name}' (ID: {table.id}):")

            if "create" in operations:
                create_rows = table_tools["create"]
                new_tools.append(create_rows)
                observation.append(f"- Use {create_rows.name} to create new rows.")

            if "update" in operations:
                update_rows = table_tools["update"]
                new_tools.append(update_rows)
                observation.append(
                    f"- Use {update_rows.name} to update existing rows by their IDs."
                )

            if "delete" in operations:
                delete_rows = table_tools["delete"]
                new_tools.append(delete_rows)
                observation.append(
                    f"- Use {delete_rows.name} to delete rows by their IDs."
                )

            observation.append("")

        return ToolsUpgradeResponse(
            observation="\n".join(observation), new_tools=new_tools
        )

    return get_rows_tools


class GetRowsToolsToolType(AssistantToolType):
    type = "get_rows_tools"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_rows_meta_tool(user, workspace, tool_helpers)


def get_list_views_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int], list[dict[str, Any]]]:
    """
    Returns a function that lists all the views in a given table the user has
    access to in the current workspace.
    """

    def list_views(table_id: int) -> list[dict[str, Any]]:
        """
        List views in the specified table.

        - Always call this for existing tables to avoid creating views with duplicate
          names.
        """

        nonlocal user, workspace, tool_helpers

        table = utils.filter_tables(user, workspace).get(id=table_id)

        tool_helpers.update_status(
            _("Listing views in %(table_name)s...") % {"table_name": table.name}
        )

        views = ViewHandler().list_views(
            user,
            table,
            filters=False,
            sortings=False,
            decorations=False,
            group_bys=False,
            limit=100,
        )

        return {
            "views": [
                view_item_registry.from_django_orm(view).model_dump() for view in views
            ]
        }

    return list_views


class ListViewsToolType(AssistantToolType):
    type = "list_views"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_list_views_tool(user, workspace, tool_helpers)


def get_create_views_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int, list[str]], list[str]]:
    """
    Returns a function that creates views in a given table the user has access to
    in the current workspace.
    """

    def create_views(
        table_id: int, views: list[AnyViewItemCreate]
    ) -> list[dict[str, Any]]:
        """
        Creates views in the specified table. A default grid view showing all the rows
        is created automatically when a table is created, no need to recreate it.

        - Choose the most appropriate view type for each view.
        - View names must be unique within a table: check existing names when needed and
          skip duplicates.
        """

        nonlocal user, workspace, tool_helpers

        if not views:
            return []

        table = utils.filter_tables(user, workspace).get(id=table_id)

        created_views = []
        with transaction.atomic():
            for view in views:
                tool_helpers.update_status(
                    _("Creating %(view_type)s view %(view_name)s")
                    % {"view_type": view.type, "view_name": view.name}
                )

                orm_view = CreateViewActionType.do(
                    user,
                    table,
                    view.type,
                    **view.to_django_orm_kwargs(table),
                )

                field_options = view.field_options_to_django_orm()
                if field_options:
                    UpdateViewFieldOptionsActionType.do(user, orm_view, field_options)
                created_views.append({"id": orm_view.id, **view.model_dump()})

        tool_helpers.navigate_to(
            ViewNavigationType(
                type="database-view",
                database_id=table.database_id,
                table_id=table.id,
                view_id=created_views[0]["id"],
                view_name=created_views[0]["name"],
            )
        )

        return {"created_views": created_views}

    return create_views


class CreateViewsToolType(AssistantToolType):
    type = "create_views"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_create_views_tool(user, workspace, tool_helpers)


def get_create_view_filters_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
) -> Callable[[int, list[str]], list[str]]:
    """
    Returns a function that creates views in a given table the user has access to
    in the current workspace.
    """

    def create_view_filters(
        view_id: int, filters: list[AnyViewFilterItemCreate]
    ) -> list[AnyViewFilterItem]:
        """
        Creates filters in the specified view.

        - Choose the most appropriate filter for each view.
        - Filter names must be unique within a view: check existing names
          when needed and skip duplicates.
        """

        nonlocal user, workspace, tool_helpers

        if not filters:
            return []

        orm_view = utils.get_view(user, view_id)
        tool_helpers.update_status(
            _("Creating filters in %(view_name)s...") % {"view_name": orm_view.name}
        )

        fields = {f.id: f for f in orm_view.table.field_set.all()}

        created_filters = []
        with transaction.atomic():
            for filter in filters:
                field = fields.get(filter.field_id)
                if field is None:
                    logger.info("Skipping filter creation due to missing field")
                    continue
                field_type = field_type_registry.get_by_model(field.specific_class)
                if field_type.type != filter.type:
                    logger.info("Skipping filter creation due to type mismatch")
                    continue

                filter_type = filter.get_django_orm_type(field)
                filter_value = filter.get_django_orm_value(
                    field, timezone=user.profile.timezone
                )

                orm_filter = CreateViewFilterActionType.do(
                    user,
                    orm_view,
                    field,
                    filter_type,
                    filter_value,
                    filter_group_id=None,
                )

                created_filters.append({"id": orm_filter.id, **filter.model_dump()})

        return {"created_view_filters": created_filters}

    return create_view_filters


class CreateViewFiltersToolType(AssistantToolType):
    type = "create_view_filters"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: ToolHelpers
    ) -> Callable[[Any], Any]:
        return get_create_view_filters_tool(user, workspace, tool_helpers)
