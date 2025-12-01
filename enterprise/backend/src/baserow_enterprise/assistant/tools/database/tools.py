from typing import TYPE_CHECKING, Any, Callable, Literal, Tuple

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

import udspy
from baserow_premium.prompts import get_formula_docs
from loguru import logger
from pydantic import create_model

from baserow.contrib.database.api.formula.serializers import TypeFormulaResultSerializer
from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.views.actions import (
    CreateViewActionType,
    UpdateViewFieldOptionsActionType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.tools.registries import AssistantToolType
from baserow_enterprise.assistant.types import TableNavigationType, ViewNavigationType

from . import utils
from .types import (
    AnyFieldItem,
    AnyFieldItemCreate,
    AnyViewFilterItem,
    AnyViewItemCreate,
    BaseTableItem,
    ListTablesFilterArg,
    TableItemCreate,
    ViewFiltersArgs,
    view_item_registry,
)

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def get_list_tables_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
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
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_list_tables_tool(user, workspace, tool_helpers)


def get_tables_schema_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
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
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_tables_schema_tool(user, workspace, tool_helpers)


def get_table_and_fields_tools_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[list[TableItemCreate]], list[dict[str, Any]]]:
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
            instructions = []
            tool_helpers.update_status(
                _("Preparing example rows for these new tables...")
            )
            tools = []
            for table, created_table in zip(tables, created_tables):
                create_rows_tool = utils.get_table_rows_tools(
                    user, workspace, tool_helpers, created_table
                )["create"]
                tools.append(create_rows_tool)
                instructions.append(
                    f"- Create 5 example rows with realistic data for {created_table.name} (Id: {created_table.id}). "
                    "Fill every relationship with valid data when possible."
                )

            predictor = udspy.ReAct(
                "instructions -> result", tools=tools, max_iters=len(tables * 2)
            )
            result = predictor(instructions=("\n".join(instructions)))
            notes.append(result)

        return {
            "created_tables": [
                BaseTableItem(id=t.id, name=t.name).model_dump() for t in created_tables
            ],
            "notes": notes,
        }

    def load_table_and_fields_tools():
        """
        TOOL LOADER: Loads table and field creation tools for a database.

        After calling this loader, you will have access to:
        - create_tables: Create new tables in a database with fields and sample rows
        - create_fields: Add new fields to an existing table

        Use this when you need to create tables or add fields but don't have the tools.
        """

        @udspy.module_callback
        def _load_table_and_fields_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            create_tool = udspy.Tool(create_tables)
            new_tools = [create_tool]
            observation.append("- Use `create_tables` to create tables in a database.")

            create_fields_tool = udspy.Tool(create_fields)
            new_tools.append(create_fields_tool)
            observation.append("- Use `create_fields` to create fields in a table.")

            # Re-initialize the module with the new tools for the next iteration
            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_table_and_fields_tools

    return load_table_and_fields_tools


class TableAndFieldsToolFactoryToolType(AssistantToolType):
    type = "table_and_fields_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_table_and_fields_tools_factory(user, workspace, tool_helpers)


def get_list_rows_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, int, int, list[int] | None], list[dict[str, Any]]]:
    """
    Returns a function that lists rows in a given table the user has access to in the
    current workspace.
    """

    def list_rows(
        table_id: int,
        offset: int = 0,
        limit: int = 20,
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
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_list_rows_tool(user, workspace, tool_helpers)


def get_rows_tools_factory(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: "ToolHelpers",
) -> Callable[[int, list[dict[str, Any]]], list[Any]]:
    def load_rows_tools(
        table_ids: list[int],
        operations: list[Literal["create", "update", "delete"]],
    ) -> Tuple[str, list[Callable[[Any], Any]]]:
        """
        TOOL LOADER: Loads row manipulation tools for specified tables.
        Make sure to have the correct table IDs.

        After calling this loader, you will have access to table-specific tools:
        - create_rows_in_table_X: Create new rows in table X
        - update_rows_in_table_X: Update existing rows in table X by their IDs
        - delete_rows_in_table_X: Delete rows from table X by their IDs

        Use this when you need to create, update, or delete rows but don't have
        the tools.
        Call with the table IDs and desired operations (create/update/delete).
        """

        @udspy.module_callback
        def _load_rows_tools(context):
            nonlocal user, workspace, tool_helpers

            tables = utils.filter_tables(user, workspace).filter(id__in=table_ids)
            if not tables:
                observation = [
                    "No valid tables found for the given IDs. ",
                    "Make sure the table IDs are correct.",
                ]
                return "\n".join(observation)

            new_tools = []
            observation = ["New tools are now available.\n"]
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

            # Re-initialize the module with the new tools for the next iteration
            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_rows_tools

    return load_rows_tools


class RowsToolFactoryToolType(AssistantToolType):
    type = "rows_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_rows_tools_factory(user, workspace, tool_helpers)


def get_list_views_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
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
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_list_views_tool(user, workspace, tool_helpers)


def get_views_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, list[str]], list[str]]:
    def create_view_filters(
        view_filters: list[ViewFiltersArgs],
    ) -> list[AnyViewFilterItem]:
        """
        Creates filters in the specified views.
        """

        nonlocal user, workspace, tool_helpers

        if not view_filters:
            return []

        created_view_filters = []
        for vf in view_filters:
            orm_view = utils.get_view(user, vf.view_id)
            tool_helpers.update_status(
                _("Creating filters in %(view_name)s...") % {"view_name": orm_view.name}
            )

            fields = {f.id: f for f in orm_view.table.field_set.all()}
            created_filters = []
            with transaction.atomic():
                for filter in vf.filters:
                    try:
                        orm_filter = utils.create_view_filter(
                            user, orm_view, fields, filter
                        )
                    except ValueError as e:
                        logger.warning(f"Skipping filter creation: {e}")
                        continue

                    created_filters.append({"id": orm_filter.id, **filter.model_dump()})
            created_view_filters.append(
                {"view_id": vf.view_id, "filters": created_filters}
            )

        return {"created_view_filters": created_view_filters}

    def create_views(
        table_id: int, views: list[AnyViewItemCreate]
    ) -> list[dict[str, Any]]:
        """
        Creates views in the specified table. A default grid view showing all the rows
        is created automatically when a table is created, no need to recreate it.

        - Choose the most appropriate view type for each view.
        - View names must be unique within a table: check existing names when needed and
          avoid duplicates.
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
                view_type=created_views[0]["type"],
            )
        )

        return {"created_views": created_views}

    def load_views_tools():
        """
        TOOL LOADER: Loads tools to manage views and filters
        (grid, gallery, form, kanban, calendar and timeline).

        After calling this loader, you will be able to:
        - create_views: Create grid, gallery, form, kanban, calendar and timeline views
        - create_view_filters: Create filters for specific views to filter rows

        Use this when you need to create views or filters but don't have the tools yet.
        """

        @udspy.module_callback
        def _load_views_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            create_tool = udspy.Tool(create_views)
            new_tools = [create_tool]
            observation.append("- Use `create_views` to create views.")

            create_filters_tool = udspy.Tool(create_view_filters)
            new_tools.append(create_filters_tool)
            observation.append(
                "- Use `create_view_filters` to create filters in views."
            )

            # Re-initialize the module with the new tools for the next iteration
            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_views_tools

    return load_views_tools


class ViewsToolFactoryToolType(AssistantToolType):
    type = "views_tool_factory"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_views_tool_factory(user, workspace, tool_helpers)


def get_formula_type_tool(
    user: AbstractUser, workspace: Workspace
) -> Callable[[str], str]:
    """
    Returns a function that returns the type of a formula.
    """

    def get_formula_type(table_id: int, field_name: str, formula: str) -> str:
        """
        Returns the type of a formula. Raises an exception if the formula is not valid.
        **ALWAYS** call this to validate a formula is valid before returning it.
        """

        nonlocal user, workspace

        table = utils.filter_tables(user, workspace).get(id=table_id)
        field = FormulaField(formula=formula, table=table, name=field_name, order=0)
        field.recalculate_internal_fields(raise_if_invalid=True)

        result = TypeFormulaResultSerializer(field).data
        if result["error"]:
            raise Exception(f"Invalid formula: {result['error']}")

        return result["formula_type"]

    return get_formula_type


class FormulaGenerationSignature(udspy.Signature):
    """
    Generates a Baserow formula based on the provided description and table schema.
    """

    description: str = udspy.InputField(
        desc="A brief description of what the formula should do."
    )
    tables_schema: dict = udspy.InputField(
        desc="The schema of all the tables in the database."
    )
    formula_documentation: str = udspy.InputField(
        desc="Documentation about Baserow formulas and their syntax."
    )
    table_id: int = udspy.OutputField(
        desc=(
            "The ID of the table the formula is intended for. "
            "Should be the same as current_table_id, unless the formula can "
            "only be created in a different table."
        )
    )
    field_name: str = udspy.OutputField(
        desc="The name of the formula field to be created. For a new field, it must be unique in the table."
    )
    formula: str = udspy.OutputField(
        desc="The generated formula. Must be a valid Baserow formula."
    )
    formula_type: str = udspy.OutputField(
        desc="The type of the generated formula. Must be one of: text, long_text, "
        "number, boolean, date, link_row, single_select, multiple_select, duration, array."
    )
    is_formula_valid: bool = udspy.OutputField(
        desc="Whether the generated formula is valid or not."
    )
    error_message: str = udspy.OutputField(
        desc="If the formula is not valid, an error message explaining why."
    )


def get_generate_database_formula_tool(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: "ToolHelpers",
) -> Callable[[str, int], dict[str, str]]:
    """
    Returns a function that generates a formula for a given field in a table.
    """

    def generate_database_formula(
        database_id: int,
        description: str,
        save_to_field: bool = True,
    ) -> dict[str, str]:
        """
        Generate a database formula for a formula field. No need to inspect the schema
        before, this tool will do it automatically and find the best table and fields to
        use.

        - table_id: The database ID where the formula field is located.
        - description: A brief description of what the formula should do.
        - save_to_field: Whether to save the generated formula to a field with the given
          name (default: True). If False, the formula will be generated but not saved
          into a field.
        """

        nonlocal user, workspace, tool_helpers

        database_tables = utils.filter_tables(user, workspace).filter(
            database_id=database_id
        )
        database_tables_schema = [
            t.model_dump() for t in utils.get_tables_schema(database_tables, True)
        ]

        tool_helpers.update_status(_("Generating formula..."))

        formula_docs = get_formula_docs()

        formula_generator = udspy.ReAct(
            FormulaGenerationSignature,
            tools=[get_formula_type_tool(user, workspace)],
            max_iters=20,
        )
        result = formula_generator(
            description=description,
            tables_schema={"tables": database_tables_schema},
            formula_documentation=formula_docs,
        )

        if not result.is_formula_valid:
            raise Exception(f"Error generating formula: {result.error_message}")

        table = next((t for t in database_tables if t.id == result.table_id), None)
        if table is None:
            raise Exception(
                "The generated formula is intended for a different table "
                f"than the current one. Table with ID {result.table_id} not found."
            )

        data = {
            "formula": result.formula,
            "formula_type": result.formula_type,
        }
        field_name = result.field_name

        if save_to_field:
            field = table.field_set.filter(name=field_name).first()
            if field:
                field = field.specific

            with transaction.atomic():
                # Trash any existing non-formula field so it can be replaced, allowing
                # the user to easily restore the original field if needed.
                if field and field_type_registry.get_by_model(field).type != "formula":
                    DeleteFieldActionType.do(user, field)
                    field = None

                if field is None:
                    CreateFieldActionType.do(
                        user,
                        table,
                        type_name="formula",
                        name=field_name,
                        formula=result.formula,
                    )
                    operation = "field created"
                else:
                    # Only update the formula of an existing formula field.
                    UpdateFieldActionType.do(
                        user,
                        field,
                        formula=result.formula,
                    )
                    operation = "field updated"

                tool_helpers.navigate_to(
                    TableNavigationType(
                        type="database-table",
                        database_id=table.database_id,
                        table_id=table.id,
                        table_name=table.name,
                    )
                )

                data.update(
                    {
                        "table_id": table.id,
                        "table_name": table.name,
                        "field_name": result.field_name,
                        "operation": operation,
                    }
                )

        return data

    return generate_database_formula


class GenerateDatabaseFormulaToolType(AssistantToolType):
    type = "generate_database_formula"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_generate_database_formula_tool(user, workspace, tool_helpers)
