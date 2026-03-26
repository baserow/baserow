from typing import TYPE_CHECKING, Annotated, Any, Literal

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger
from pydantic import Field, create_model
from pydantic_ai import RunContext, Tool
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.actions import (
    CreateViewActionType,
    UpdateViewFieldOptionsActionType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.toolset import inline_refs
from baserow_enterprise.assistant.types import TableNavigationType, ViewNavigationType
from baserow_premium.prompts import get_formula_docs

from . import helpers
from .agents import (
    formula_generation_agent,
    generate_sample_rows,
    get_formula_type_tool,
    make_formula_fixer,
)
from .prompts import format_formula_generation_prompt
from .types import (
    FieldItemCreate,
    FieldItemUpdate,
    ListTablesFilterArg,
    TableItemCreate,
    ViewFiltersArgs,
    ViewItem,
    ViewItemCreate,
    get_create_row_model,
    get_link_row_hints,
    get_update_row_model,
)

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers

MAX_HINT_TABLES = 10


def _no_tables_found_hint(
    user: AbstractUser, workspace: Workspace, filters: "ListTablesFilterArg"
) -> str:
    """Build an informative message when no tables match the filters.

    When the caller supplied a ``database_id`` that doesn't correspond to any
    real database in the workspace, say so explicitly and list the first
    available tables so the model can self-correct.
    """

    parts: list[str] = []

    # Check whether the requested database actually exists.
    db_ref = filters.database_id_or_name
    if db_ref is not None:
        if isinstance(db_ref, int):
            db_exists = Database.objects.filter(workspace=workspace, id=db_ref).exists()
        else:
            db_exists = Database.objects.filter(
                workspace=workspace, name__icontains=db_ref
            ).exists()
        if not db_exists:
            parts.append(
                f"No database matching '{db_ref}' exists in this "
                f"workspace. Note: workspace, application, and database IDs "
                f"are different — make sure you are using a database ID."
            )
        else:
            parts.append(
                f"Database '{db_ref}' exists but has no tables "
                f"matching the provided filters."
            )
    else:
        parts.append("No tables found matching the provided filters.")

    # Fetch a sample of available tables across the workspace.
    all_tables = (
        helpers.filter_tables(user, workspace)
        .select_related("database")
        .order_by("database_id", "id")
    )
    total_tables = all_tables.count()

    if total_tables == 0:
        parts.append("This workspace has no database tables at all.")
        return " ".join(parts)

    sample = all_tables[:MAX_HINT_TABLES]
    db_ids_seen: set[int] = set()
    table_lines: list[str] = []
    for t in sample:
        db_ids_seen.add(t.database_id)
        table_lines.append(
            f'  - table_id={t.id}, table_name="{t.name}", '
            f'database_id={t.database_id}, database_name="{t.database.name}"'
        )

    total_dbs = Database.objects.filter(workspace=workspace).count()

    parts.append(
        f"Available tables ({total_tables} table(s) across "
        f"{total_dbs} database(s) in this workspace):"
    )
    parts.append("\n".join(table_lines))

    remaining_tables = total_tables - len(sample)
    remaining_dbs = total_dbs - len(db_ids_seen)
    if remaining_tables > 0:
        parts.append(
            f"  ... and {remaining_tables} more table(s) in "
            f"{remaining_dbs} more database(s)."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 1: list_tables
# ---------------------------------------------------------------------------


def list_tables(
    ctx: RunContext[AssistantDeps],
    filters: Annotated[
        ListTablesFilterArg,
        Field(description="Filter criteria to narrow down which tables to list."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> list[dict[str, Any]] | dict[str, Any]:
    """\
    List tables, optionally filtered by database or name.

    WHEN to use: Before creating tables (to avoid duplicates), when you need table IDs, or to discover what tables exist in the workspace.
    WHAT it does: Lists tables matching the filter criteria (database_id, name, starred), grouped by database.
    RETURNS: Tables with id, name, database_id. Includes a hint with available tables if no match found.
    DO NOT USE when: You already have the table IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    tables = (
        helpers.filter_tables(user, workspace)
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
        return {"tables": [], "_info": _no_tables_found_hint(user, workspace, filters)}
    elif len(databases) == 1:
        # Return just the tables array when there's only one database
        return list(databases.values())[0]["tables"]
    else:
        return list(databases.values())


# ---------------------------------------------------------------------------
# Tool 2: get_tables_schema
# ---------------------------------------------------------------------------


def get_tables_schema(
    ctx: RunContext[AssistantDeps],
    table_ids: Annotated[
        list[int], Field(description="List of table IDs to retrieve schemas for.")
    ],
    full_schema: Annotated[
        bool,
        Field(
            description="If True, include all fields. If False, only table names, IDs, primary keys, and relationships."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Get field definitions for tables (full_schema=True for all fields).

    WHEN to use: Before creating/modifying fields to understand table structure and avoid duplicates. Also for understanding relationships when creating link_row fields.
    WHAT it does: Returns the schema of specified tables. full_schema=True returns all fields with types and configs. full_schema=False returns only names, IDs, primary keys, and relationships.
    RETURNS: Table schemas with field names, types, IDs, primary keys, and relationships.
    DO NOT USE when: You need row data — use list_rows instead. For row operations, use load_row_tools, those tools already provide the necessary schema info in their instructions.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not table_ids:
        return {"tables_schema": []}

    tables = helpers.filter_tables(user, workspace).filter(id__in=table_ids)

    tool_helpers.update_status(
        _("Inspecting %(table_names)s schema...")
        % {"table_names": ", ".join(t.name for t in tables)}
    )

    return {
        "tables_schema": [
            ts.model_dump() for ts in helpers.get_tables_schema(tables, full_schema)
        ]
    }


# ---------------------------------------------------------------------------
# Tool 3: list_rows
# ---------------------------------------------------------------------------


def list_rows(
    ctx: RunContext[AssistantDeps],
    table_id: Annotated[
        int, Field(description="The ID of the table to list rows from.")
    ],
    offset: Annotated[
        int,
        Field(
            description="Number of rows to skip for pagination. Use 0 for the first page."
        ),
    ],
    limit: Annotated[
        int, Field(description="Maximum number of rows to return (max 20).")
    ],
    field_ids: Annotated[
        list[int] | None,
        Field(description="List of field IDs to include, or null for all fields."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Read rows from a table with pagination (max 20 per call).

    WHEN to use: User wants to see data in a table, or you need to check existing row values.
    WHAT it does: Lists rows from a table with pagination (offset/limit) and optional field filtering. Max 20 rows per call.
    RETURNS: Rows array with field values, plus total row count for pagination.
    DO NOT USE when: You need to create, update, or delete rows — call load_row_tools first to get row manipulation tools.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    table = helpers.get_table(user, workspace, table_id)

    tool_helpers.update_status(
        _("Listing rows in %(table_name)s ") % {"table_name": table.name}
    )

    rows_qs = table.get_model().objects.all()
    rows = rows_qs[offset : offset + limit]

    response_model = create_model(
        f"ResponseTable{table.id}RowWithFieldFilter",
        id=(int, ...),
        __base__=get_create_row_model(table, field_ids=field_ids),
    )

    return {
        "rows": [
            response_model.from_django_orm(row, field_ids).model_dump() for row in rows
        ],
        "total": rows_qs.count(),
    }


# ---------------------------------------------------------------------------
# Tool 4: list_views
# ---------------------------------------------------------------------------


def list_views(
    ctx: RunContext[AssistantDeps],
    table_id: Annotated[
        int, Field(description="The ID of the table to list views for.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List views in a table.

    WHEN to use: Before creating views (to avoid duplicate names), or to find existing view IDs.
    WHAT it does: Lists all views in a table with their id, name, and type.
    RETURNS: Views array with id, name, type configuration.
    DO NOT USE when: You already have the view IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    table = helpers.get_table(user, workspace, table_id)

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

    return {"views": [ViewItem.from_django_orm(view).model_dump() for view in views]}


# ---------------------------------------------------------------------------
# Tool 5: create_tables
# ---------------------------------------------------------------------------


def _create_empty_tables(
    user: AbstractUser,
    database: Database,
    tables: list[TableItemCreate],
    tool_helpers: "ToolHelpers",
) -> list[Table]:
    """Create bare tables and rename each one's auto-created primary field."""
    created: list[Table] = []
    with transaction.atomic():
        for table in tables:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(
                _("Creating table %(table_name)s...") % {"table_name": table.name}
            )
            created_table, __ = CreateTableActionType.do(
                user, database, table.name, fill_example=False
            )
            created.append(created_table)
            primary_field = created_table.get_primary_field().specific
            UpdateFieldActionType.do(user, primary_field, name=table.primary_field_name)
    return created


def _create_table_fields(
    user: AbstractUser,
    tables: list[TableItemCreate],
    created_tables: list[Table],
    tool_helpers: "ToolHelpers",
    formula_fixer,
) -> list[str]:
    """Create non-primary fields for each table; return collected notes/errors."""
    notes: list[str] = []
    for table, created_table in zip(tables, created_tables):
        tool_helpers.raise_if_cancelled()
        with transaction.atomic():
            # Drop any field whose name matches the primary field name — it's
            # already set via UpdateFieldActionType.do() above. Including it in
            # fields too is a common model mistake that would otherwise produce
            # a "field already exists" error note.
            non_primary_fields = [
                f
                for f in table.fields
                if f.name.lower() != table.primary_field_name.lower()
            ]
            _created, field_errors, formula_errors = helpers.create_fields(
                user,
                created_table,
                non_primary_fields,
                tool_helpers,
                formula_fixer=formula_fixer,
            )
            notes.extend(field_errors)
            for err in formula_errors:
                notes.append(
                    f"Invalid formula for field '{err['field_name']}' "
                    f"in table_{created_table.id}: {err['error']}. "
                    f"Use generate_formula to fix it."
                )
    return notes


def create_tables(
    ctx: RunContext[AssistantDeps],
    database_id: Annotated[
        int,
        Field(
            ...,
            description="The ID of the database to create tables in.",
        ),
    ],
    tables: Annotated[
        list[TableItemCreate],
        Field(
            ...,
            description="List of tables to create, each with a name, primary field, fields and relationships.",
        ),
    ],
    add_sample_rows: Annotated[
        bool | str,
        Field(
            ...,
            description="Controls sample row generation. True (default): generate realistic example rows. "
            "A string: a brief describing what kind of data to create (e.g. 'Italian recipes with calorie counts'). "
            "False: create empty tables, only use when the user explicitly asks for no sample data.",
        ),
    ],
    thought: Annotated[
        str,
        Field(
            ...,
            description="Brief reasoning for calling this tool.",
        ),
    ],
) -> dict[str, Any]:
    """\
    Create tables with fields; generates sample rows by default.

    WHEN to use: User wants new tables created in a database. Always set add_sample_rows=true (or a descriptive string) unless explicitly asked for empty tables.
    WHAT it does: Creates tables with fields, generates sample rows by default. Pass add_sample_rows=false ONLY when the user explicitly asks for empty tables.
        Pass a string to guide the kind of sample data generated (e.g. "Italian recipes with calorie counts"). Table names must be unique. Reversed link_row fields are auto-created.
        At the end, this tool automatically navigates the user to the last created table.
    RETURNS: Created table schemas with all field IDs. Notes on any errors.
    DO NOT USE when: Tables already exist — check with list_tables first.
    HOW: Pass ALL related tables in a single call — link_row fields can reference other tables in the same call by name (they are created internally before fields are added). Choose appropriate field types for each column.
        Use single_select/multiple_select with select_options for categorical data. The primary field is always text — pick a meaningful name for it.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not tables:
        return {"created_tables": []}

    database = CoreService().get_application(
        user,
        database_id,
        specific=False,
        base_queryset=Database.objects.filter(workspace=workspace),
    )

    created_tables = _create_empty_tables(user, database, tables, tool_helpers)

    formula_fixer = make_formula_fixer(user, workspace, tool_helpers)
    notes = _create_table_fields(
        user, tables, created_tables, tool_helpers, formula_fixer
    )

    last_table = created_tables[-1]
    tool_helpers.navigate_to(
        TableNavigationType(
            type="database-table",
            database_id=database.id,
            table_id=last_table.id,
            table_name=last_table.name,
        )
    )

    created_rows = {}
    if add_sample_rows:
        try:
            data_brief = add_sample_rows if isinstance(add_sample_rows, str) else None
            created_rows = generate_sample_rows(
                user, workspace, tool_helpers, created_tables, data_brief=data_brief
            )
        except Exception as e:
            logger.exception(
                "[assistant] generate_sample_rows raised unexpectedly: {}", e
            )
            notes.append(f"Error creating sample rows: {e}")

    # Return the full schema so callers don't need a separate
    # get_tables_schema call to learn field IDs.
    tables_schema = [
        ts.model_dump()
        for ts in helpers.get_tables_schema(created_tables, full_schema=True)
    ]

    response: dict[str, Any] = {"created_tables": tables_schema, "notes": notes}
    if created_rows:
        response["created_rows"] = {
            f"Row IDs for newly created rows in table_{table_id}": [
                row.id for row in rows
            ]
            for table_id, rows in created_rows.items()
        }

    return response


# ---------------------------------------------------------------------------
# Tool 6: create_fields
# ---------------------------------------------------------------------------


def create_fields(
    ctx: RunContext[AssistantDeps],
    table_id: Annotated[
        int, Field(description="The ID of the table to add fields to.")
    ],
    fields: Annotated[
        list[FieldItemCreate],
        Field(
            description="List of fields to create with their types and configurations."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add fields to an existing table.

    WHEN to use: Adding fields to an existing table, or retrying failed field creation after create_tables partial failure.
    WHAT it does: Creates fields in the specified table. Field names must be unique. For link_row fields, the linked table must already exist.
    RETURNS: Created fields with id, name, type. Formula errors with hints if any.
    DO NOT USE when: Creating a brand new table — use create_tables instead, which handles fields as part of table creation.
    HOW: Call get_tables_schema first to see existing fields and avoid duplicates. For link_row fields, ensure the target table already exists.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not fields:
        return {"created_fields": []}

    table = helpers.get_table(user, workspace, table_id)

    with transaction.atomic():
        formula_fixer = make_formula_fixer(user, workspace, tool_helpers)
        created_fields, field_errors, formula_errors = helpers.create_fields(
            user, table, fields, tool_helpers, formula_fixer=formula_fixer
        )
        result = {"created_fields": [field.model_dump() for field in created_fields]}
        if field_errors:
            result["field_errors"] = field_errors
        if formula_errors:
            for err in formula_errors:
                err["hint"] = (
                    "Use generate_formula to create a valid formula for this field."
                )
            result["formula_errors"] = formula_errors
        return result


# ---------------------------------------------------------------------------
# Tool 7: update_fields
# ---------------------------------------------------------------------------


def update_fields(
    ctx: RunContext[AssistantDeps],
    fields: Annotated[
        list[FieldItemUpdate],
        Field(
            description="List of field updates, each with a field_id and the properties to change."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update existing fields (rename, change properties).

    WHEN to use: User wants to rename a field, change decimal places, update select options, or modify other field properties.
    WHAT it does: Updates field properties. Cannot change field type or link_row targets — create a new field instead.
    RETURNS: Updated fields with id, name, type and current properties.
    DO NOT USE when: You need to change a field's type — delete and recreate it instead.
    HOW: Call get_tables_schema first to see current field IDs and types.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not fields:
        return {"updated_fields": [], "errors": []}

    updated = []
    errors = []
    formula_fixer = make_formula_fixer(user, workspace, tool_helpers)

    with transaction.atomic():
        for field_update in fields:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(
                _("Updating field %(field_id)s...")
                % {"field_id": field_update.field_id}
            )
            try:
                field_item = helpers.update_field(
                    user, workspace, field_update, formula_fixer=formula_fixer
                )
                updated.append(field_item.model_dump())
            except Exception as e:
                errors.append(f"Error updating field {field_update.field_id}: {e}")

    result: dict[str, Any] = {"updated_fields": updated}
    if errors:
        result["errors"] = errors
    return result


# ---------------------------------------------------------------------------
# Tool 8: delete_fields
# ---------------------------------------------------------------------------


def delete_fields(
    ctx: RunContext[AssistantDeps],
    field_ids: Annotated[
        list[int],
        Field(description="List of field IDs to delete."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Delete fields (moves them to trash).

    WHEN to use: User wants to remove fields from a table.
    WHAT it does: Soft-deletes fields (moves to trash, can be restored). Primary fields cannot be deleted.
    RETURNS: List of deleted field IDs.
    DO NOT USE when: You want to change a field — use update_fields instead.
    HOW: Call get_tables_schema first to confirm field IDs.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not field_ids:
        return {"deleted_field_ids": [], "errors": []}

    deleted = []
    errors = []

    with transaction.atomic():
        for field_id in field_ids:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(
                _("Deleting field %(field_id)s...") % {"field_id": field_id}
            )
            try:
                helpers.delete_field(user, workspace, field_id)
                deleted.append(field_id)
            except Exception as e:
                errors.append(f"Error deleting field {field_id}: {e}")

    result: dict[str, Any] = {"deleted_field_ids": deleted}
    if errors:
        result["errors"] = errors
    return result


# ---------------------------------------------------------------------------
# Tool 9: create_views
# ---------------------------------------------------------------------------


def create_views(
    ctx: RunContext[AssistantDeps],
    table_id: Annotated[
        int, Field(description="The ID of the table to create views for.")
    ],
    views: Annotated[
        list[ViewItemCreate],
        Field(
            description="List of views to create (grid, form, gallery, kanban, calendar, timeline)."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create views (grid, form, gallery, kanban, calendar, timeline).

    WHEN to use: User wants a new view (grid, form, gallery, kanban, calendar, timeline) on a table.
    WHAT it does: Creates views in the table. View names must be unique. A default grid view is auto-created with every new table — no need to recreate it.
    RETURNS: Created views with id, name, type configuration.
    DO NOT USE when: The default grid view already meets the user's needs. Check existing views with list_views to avoid duplicates.
    HOW: Each view type requires specific config. Form views: provide field_options listing every field to show (field_id, name, order, required). Kanban: set column_field_id to a single_select field. Calendar: set date_field_id to a date field. Timeline: set both start/end date fields. Gallery: optionally set cover_field_id to a file field. Call get_tables_schema first to get the field IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not views:
        return {"created_views": []}

    table = helpers.get_table(user, workspace, table_id)

    created_views = []
    with transaction.atomic():
        for view in views:
            tool_helpers.raise_if_cancelled()
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


# ---------------------------------------------------------------------------
# Tool 8: create_view_filters
# ---------------------------------------------------------------------------


def create_view_filters(
    ctx: RunContext[AssistantDeps],
    view_filters: Annotated[
        list[ViewFiltersArgs],
        Field(
            description="List of view filter configurations, each specifying a view ID and its filters."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add filters to views.

    WHEN to use: User wants to filter a view to show only specific rows matching conditions.
    WHAT it does: Creates filter conditions on one or more views. Supports multiple filters per view.
    RETURNS: Created filters with id and configuration per view.
    DO NOT USE when: The view doesn't exist yet — create it first with create_views.
    HOW: Get the table schema first to know field IDs and types. Match filter type to field type.

    ## Value formats by type

    - text: string
    - number: number
    - date: ISO date string (mode=exact_date) or integer (mode=nr_days_ago etc.) or "" (mode=today etc.)
    - single_select / multiple_select: list of option label strings (matched case-insensitively)
    - link_row: row ID (integer)
    - boolean: true / false
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not view_filters:
        return {"created_view_filters": []}

    created_view_filters = []
    for vf in view_filters:
        tool_helpers.raise_if_cancelled()
        orm_view = helpers.get_view(user, workspace, vf.view_id)
        tool_helpers.update_status(
            _("Creating filters in %(view_name)s...") % {"view_name": orm_view.name}
        )

        fields = {f.id: f for f in orm_view.table.field_set.all()}
        created_filters = []
        with transaction.atomic():
            for filter in vf.filters:
                try:
                    orm_filter = helpers.create_view_filter(
                        user, orm_view, fields, filter
                    )
                except ValueError as e:
                    logger.warning(f"Skipping filter creation: {e}")
                    continue

                created_filters.append({"id": orm_filter.id, **filter.model_dump()})
        created_view_filters.append({"view_id": vf.view_id, "filters": created_filters})

    return {"created_view_filters": created_view_filters}


# ---------------------------------------------------------------------------
# Tool 9: generate_formula
# ---------------------------------------------------------------------------


def generate_formula(
    ctx: RunContext[AssistantDeps],
    database_id: Annotated[
        int,
        Field(
            description="The ID of the database containing the tables for the formula."
        ),
    ],
    description: Annotated[
        str,
        Field(
            description="A natural language description of what the formula should compute."
        ),
    ],
    save_to_field: Annotated[
        bool,
        Field(
            description="If true, save the formula to a field. If false, only return it. Should be true unless explicitly asked otherwise."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, str]:
    """\
    Generate a formula from a natural-language description and save it.

    WHEN to use: User needs a computed field (formulas, calculations, cross-table lookups). No need to inspect the schema first — this tool does it automatically.
    WHAT it does: Generates a valid Baserow formula from a natural-language description. Finds the best table and fields automatically. Saves to a formula field by default (save_to_field=true).
    RETURNS: Generated formula string, formula type, and field details (name, table, operation).
    DO NOT USE when: The user wants a simple non-formula field — use create_fields instead.
    HOW: Describe what the formula should compute in plain language. The tool auto-discovers the table schema — no need to inspect it first.
    """
    from baserow_enterprise.assistant.model_profiles import (
        UTILITY,
        get_model_settings,
        get_model_string,
    )

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    database_tables = helpers.filter_tables(user, workspace).filter(
        database_id=database_id
    )
    database_tables_schema = [
        t.model_dump() for t in helpers.get_tables_schema(database_tables, True)
    ]

    tool_helpers.update_status(_("Generating formula..."))

    formula_docs = get_formula_docs()
    formula_type_tool = Tool(get_formula_type_tool(user, workspace))
    formula_toolset = FunctionToolset([formula_type_tool])

    prompt = format_formula_generation_prompt(
        description, database_tables_schema, formula_docs
    )

    model = get_model_string()
    agent_result = formula_generation_agent.run_sync(
        prompt,
        model=model,
        model_settings=get_model_settings(model, UTILITY),
        toolsets=[formula_toolset],
        usage_limits=UsageLimits(request_limit=20),
    )
    result = agent_result.output

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


# ---------------------------------------------------------------------------
# Dynamic row tools (create / update / delete)
# ---------------------------------------------------------------------------


def _build_row_tools(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: "ToolHelpers",
    table: Table,
    field_ids: list[int] | None = None,
) -> dict[str, Tool]:
    """
    Build pydantic-ai Tool objects for row CRUD on a single table.

    Returns a dict with keys ``"create"``, ``"update"``, ``"delete"``, each
    containing a ready-to-use ``Tool`` whose schema is derived from the table's
    fields.

    :param user: The acting user.
    :param workspace: Current workspace.
    :param tool_helpers: Provides status updates and cancellation.
    :param table: The table to build row tools for.
    :param field_ids: If given, only include these field IDs in the
        create model (useful for excluding reverse link_row fields).
    """

    row_model_for_create = get_create_row_model(table, field_ids=field_ids)
    row_model_for_update = get_update_row_model(table)
    link_row_hints = get_link_row_hints(row_model_for_create)

    def _create_rows(
        rows: list[row_model_for_create],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """Create new rows in the specified table."""

        if not rows:
            return {"created_row_ids": []}

        tool_helpers.update_status(
            _("Creating rows in %(table_name)s ") % {"table_name": table.name}
        )

        validated_rows = [row.to_django_orm() for row in rows]

        with transaction.atomic():
            orm_rows = CreateRowsActionType.do(user, table, validated_rows)

        return {"created_row_ids": [r.id for r in orm_rows]}

    create_rows_tool = Tool(
        _create_rows,
        name=f"create_rows_in_table_{table.id}",
        description=(
            f"WHEN: Creating new rows in '{table.name}' (ID: {table.id}). "
            f"WHAT: Inserts up to 20 rows with field values matching the table schema. "
            f"RETURNS: Created row IDs. "
            f"DO NOT USE: For other tables — each table has its own create tool. "
            f"HOW: Fill EVERY field including ALL link_row (relationship) fields. Never skip a field unless data is genuinely unavailable."
            f"{link_row_hints}"
        ),
        max_retries=2,
    )
    create_rows_tool.function_schema.json_schema = inline_refs(
        create_rows_tool.function_schema.json_schema
    )

    def _update_rows(
        rows: list[row_model_for_update],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """Update existing rows in the specified table."""

        if not rows:
            return {"updated_row_ids": []}

        tool_helpers.update_status(
            _("Updating rows in %(table_name)s ") % {"table_name": table.name}
        )

        validated_rows = [row.to_django_orm() for row in rows]

        with transaction.atomic():
            orm_rows = UpdateRowsActionType.do(user, table, validated_rows).updated_rows

        return {"updated_row_ids": [r.id for r in orm_rows]}

    update_rows_tool = Tool(
        _update_rows,
        name=f"update_rows_in_table_{table.id}",
        description=(
            f"WHEN: Updating existing rows in '{table.name}' (ID: {table.id}) by row ID. "
            f"WHAT: Updates specified fields on up to 20 rows. Only include fields you want to change — omit fields to keep them unchanged. "
            f"RETURNS: Updated row IDs. "
            f"DO NOT USE: For other tables — each table has its own update tool."
            f"{link_row_hints}"
        ),
        max_retries=2,
    )
    update_rows_tool.function_schema.json_schema = inline_refs(
        update_rows_tool.function_schema.json_schema
    )

    def _delete_rows(
        row_ids: list[int],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """Delete rows in the specified table."""

        if not row_ids:
            return {"deleted_row_ids": []}

        tool_helpers.update_status(
            _("Deleting rows in %(table_name)s ") % {"table_name": table.name}
        )

        with transaction.atomic():
            DeleteRowsActionType.do(user, table, row_ids)

        return {"deleted_row_ids": row_ids}

    delete_rows_tool = Tool(
        _delete_rows,
        name=f"delete_rows_in_table_{table.id}",
        description=(
            f"WHEN: Deleting rows from '{table.name}' (ID: {table.id}) by row ID. "
            f"WHAT: Permanently removes up to 20 specified rows. "
            f"RETURNS: Deleted row IDs. "
            f"DO NOT USE: For other tables — each table has its own delete tool."
        ),
    )

    return {
        "create": create_rows_tool,
        "update": update_rows_tool,
        "delete": delete_rows_tool,
    }


# ---------------------------------------------------------------------------
# Tool 10: load_row_tools
# ---------------------------------------------------------------------------


def load_row_tools(
    ctx: RunContext[AssistantDeps],
    table_ids: Annotated[
        list[int], Field(description="List of table IDs to load row tools for.")
    ],
    operations: Annotated[
        list[Literal["create", "update", "delete"]],
        Field(
            description="Which row operations to enable: 'create', 'update', and/or 'delete'."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    TOOL LOADER — unlocks create/update/delete row tools for directly manipulating DATABASE rows. No need to know the schema beforehand, the loaded tools include it.

    WHEN to use: You need to directly create, update, or delete rows in a database table. Must be called before any row manipulation.
    WHAT it does: Unlocks table-specific tools and their schema: create_rows_in_table_X, update_rows_in_table_X, delete_rows_in_table_X for each table ID provided. The loaded tools include the full field schema — no need to call get_tables_schema.
    RETURNS: Names of newly available tools.
    DO NOT USE when: Row tools for these tables are already loaded from a previous call in this session.
    DO NOT USE for builder workflow actions — if you want a button/form in an Application Builder page to create/update/delete rows, use create_actions instead. load_row_tools is for direct database manipulation, NOT for configuring app behavior.
    HOW: Just call this with the table ID(s) and operations you need. The loaded row tools already contain the complete field schema in their parameters — do NOT call get_tables_schema or search_user_docs before or after this tool.

    EXAMPLES:
    - "Create 5 rows" → load_row_tools([table_id], ["create"]) → create_rows_in_table_X(rows=[...])
    - "Update row 7" → load_row_tools([table_id], ["update"]) → update_rows_in_table_X(rows=[{id: 7, ...}])
    - "Delete rows 1-3" → load_row_tools([table_id], ["delete"]) → delete_rows_in_table_X(row_ids=[1,2,3])
    - To find linked row values, use list_rows with field_ids filter on the linked table.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    tables = helpers.filter_tables(user, workspace).filter(id__in=table_ids)
    if not tables:
        return (
            "No valid tables found for the given IDs. "
            "Make sure the table IDs are correct."
        )

    new_tools: list[Tool] = []
    for table in tables:
        table_tools = _build_row_tools(user, workspace, tool_helpers, table)

        if "create" in operations:
            new_tools.append(table_tools["create"])
        if "update" in operations:
            new_tools.append(table_tools["update"])
        if "delete" in operations:
            new_tools.append(table_tools["delete"])

    # Store new tools in dynamic_tools for the dynamic toolset
    # to pick up on the next agent step
    ctx.deps.dynamic_tools.extend(new_tools)

    tool_names = [t.name for t in new_tools]
    return f"Tools loaded: {', '.join(tool_names)}"


# ---------------------------------------------------------------------------
# Module-level toolset
# ---------------------------------------------------------------------------


TOOL_FUNCTIONS = [
    list_tables,
    get_tables_schema,
    list_rows,
    list_views,
    create_tables,
    create_fields,
    update_fields,
    delete_fields,
    create_views,
    create_view_filters,
    generate_formula,
    load_row_tools,
]
database_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)

ROUTING_RULES = """\
- switch_mode: switch domain if task needs tools not in the current mode.
- Database row CRUD → call load_row_tools first (includes schema — skip get_tables_schema).
- create_tables: include ALL related tables in one call so link_row fields connect properly. Add sample rows unless told otherwise.
- create_rows: fill EVERY field including ALL link_row fields.
- When creating views/filters for a builder data source, complete ALL view + filter creation before switching back to application mode. Workflow: create_views → create_view_filters → then switch_mode("application").
- After creating tables or views for an application/data source/automation task, switch_mode back to continue building."""
