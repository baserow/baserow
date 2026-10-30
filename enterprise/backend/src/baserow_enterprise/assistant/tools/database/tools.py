from itertools import groupby
from typing import TYPE_CHECKING, Annotated, Any, Literal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger
from pydantic import Field, create_model
from pydantic_ai import ModelRetry, RunContext, Tool

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
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools import fields as shared_fields
from baserow.contrib.database.tools import tables as shared_tables
from baserow.contrib.database.tools import views as shared_views
from baserow.core.exceptions import PermissionDenied, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow_enterprise.assistant.deps import AssistantDeps, ResourceChanges
from baserow_enterprise.assistant.prompts import MISSING_RECORDS_GUIDANCE
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    raise_if_permission_denied,
    require_payload,
    return_permission_error,
)
from baserow_enterprise.assistant.tools.toolset import (
    AssistantFunctionToolset,
    inline_refs,
)
from baserow_enterprise.assistant.types import TableNavigationType, ViewNavigationType
from baserow_premium.prompts import get_formula_docs

from . import helpers, reconciliation
from .agents import (
    generate_sample_rows,
    make_formula_fixer,
    run_formula_generation,
)
from .prompts import format_formula_generation_prompt
from .types import (
    FieldItem,
    FieldItemCreate,
    FieldItemUpdate,
    ListTablesFilterArg,
    TableItemCreate,
    ViewFiltersArgs,
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
    database the user can see, say so explicitly and list the first available
    tables so the model can self-correct. Only databases and tables the user can
    see are named or counted.
    """

    parts: list[str] = []
    databases = CoreService().list_applications_in_workspace(
        user, workspace, specific=False, base_queryset=Database.objects
    )

    # Check whether the requested database actually exists.
    db_ref = filters.database_id_or_name
    if db_ref is not None:
        if isinstance(db_ref, int):
            db_exists = databases.filter(id=db_ref).exists()
        else:
            db_exists = databases.filter(name__icontains=db_ref).exists()
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
    all_tables = helpers.filter_tables(user, workspace)
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

    total_dbs = databases.count()

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
) -> dict[str, Any]:
    """\
    List tables, optionally filtered by database or name.

    WHEN to use: Before creating tables (to avoid duplicates), when you need table IDs, or to discover what tables exist in the workspace.
    WHAT it does: Lists tables matching the filter criteria (database_id, name, starred), grouped by database.
    RETURNS: Tables with id, name, database_id and next_steps for resolving missing data. Includes a hint with available tables if no match found.
    DO NOT USE when: You already have the table IDs you need.
    """

    tables = shared_tables.list_tables(
        ctx.deps.tool_context(), **filters.to_tool_filters()
    )

    databases = {}
    for table in tables:
        database = databases.setdefault(
            table["database_id"],
            {"id": table["database_id"], "name": table["database_name"], "tables": []},
        )
        database["tables"].append(
            {
                "id": table["id"],
                "name": table["name"],
                "database_id": table["database_id"],
            }
        )

    result = {
        "next_steps": (
            "For an app that shows records, use a matching table from these results. "
            "If the requested records are absent (even if unrelated tables exist), "
            f"create nothing. {MISSING_RECORDS_GUIDANCE} "
            "Exception: when the user asked for an "
            "example, demo, or sample app, or for new data storage, create the table "
            "with sample data and build without asking. "
            "Setting up application login is a storage request: setup_user_source "
            "can create its backing users table if none was specified."
        ),
    }
    if len(databases) == 0:
        result.update(
            tables=[],
            _info=_no_tables_found_hint(ctx.deps.user, ctx.deps.workspace, filters),
        )
    elif len(databases) == 1:
        result["tables"] = list(databases.values())[0]["tables"]
    else:
        result["databases"] = list(databases.values())
    return result


# ---------------------------------------------------------------------------
# Tool 2: get_tables_schema
# ---------------------------------------------------------------------------


def _kuma_field(field: dict[str, Any]) -> dict[str, Any]:
    """
    The keys of a shared schema field that ``FieldItem`` sends. MCP also gets the
    generated formula of lookup, count and rollup fields, which Kuma never sees.
    """

    keys = set(FieldItem.model_fields)
    if field["type"] != "formula":
        keys -= {"formula", "formula_type"}
    return {key: value for key, value in field.items() if key in keys}


def _kuma_table_schema(table: dict[str, Any]) -> dict[str, Any]:
    """
    Kuma's shape of a shared table schema: the primary field apart, and only the
    field keys its other tools take.
    """

    fields = [_kuma_field(field) for field in table["fields"]]
    return {
        "id": table["id"],
        "name": table["name"],
        "primary_field": fields[0],
        "fields": fields[1:],
    }


def get_tables_schema(
    ctx: RunContext[AssistantDeps],
    table_ids: Annotated[
        list[int], Field(description="List of table IDs to retrieve schemas for.")
    ],
    full_schema: Annotated[
        bool,
        Field(
            description="Use True to inspect fields, configure views/filters, or check whether a field exists. False is only a relationship overview and omits ordinary fields."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Get field definitions for tables (full_schema=True for all fields).

    WHEN to use: Before creating/modifying fields to understand table structure and avoid duplicates. Also for understanding relationships when creating link_row fields.
    WHAT it does: Returns the schema of specified tables. Use full_schema=True for field IDs, view/filter configuration, or deciding whether a field exists. full_schema=False is only a compact relationship overview: it omits ordinary fields, so an empty fields list does not establish that a field is missing.
    RETURNS: Table schemas with field names, types, IDs, primary keys, and relationships.
    DO NOT USE when: You need row data — use list_rows instead. For row operations, use load_row_tools, those tools already provide the necessary schema info in their instructions.
    """

    if not table_ids:
        return {"tables_schema": [], "full_schema": full_schema}

    tables = shared_tables.get_table_schema(
        ctx.deps.tool_context(), table_ids, full_schema
    )
    result = {
        # A table without a primary field has no Kuma shape, so it's left out.
        "tables_schema": [
            _kuma_table_schema(table)
            for table in tables
            if table["fields"] and table["fields"][0]["primary"]
        ],
        "full_schema": full_schema,
    }
    if not full_schema:
        result["next_steps"] = (
            "This relationship overview omits ordinary fields. An empty fields list "
            "does not mean the table has no other fields. Call get_tables_schema "
            "with full_schema=True to get field IDs or configure views and filters. "
            "Do that before reporting a field missing or asking the user for its ID."
        )
    return result


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
    CoreHandler().check_permissions(
        user,
        ListRowsDatabaseTableOperationType.type,
        workspace=workspace,
        context=table,
    )

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

    try:
        return shared_views.list_views(ctx.deps.tool_context(), table_id)
    except Table.DoesNotExist:
        raise ToolInputError(
            f"Table with ID {table_id} not found. "
            "Use get_tables_schema to find valid table IDs."
        )


# ---------------------------------------------------------------------------
# Tool 5: create_tables
# ---------------------------------------------------------------------------


def _repair_table_formulas(
    ctx: RunContext[AssistantDeps], creation: shared_tables.TableCreation
) -> None:
    """
    Repair the invalid formulas of new tables with the formula fixer, and note
    the ones it can't repair. Runs after the tables are committed, because the
    fixer calls a model.
    """

    if not creation.formula_errors:
        return

    tool_context = ctx.deps.tool_context()
    formula_fixer = make_formula_fixer(
        ctx.deps.user, ctx.deps.workspace, ctx.deps.tool_helpers
    )
    tables_by_id = {table.id: table for table in creation.created_tables}
    denied = False
    for table_id, errors in groupby(
        creation.formula_errors, key=lambda error: error["table_id"]
    ):
        table = tables_by_id[table_id]
        errors = list(errors)
        if denied:
            _note_unrepaired_formulas(creation, table_id, errors)
            continue
        try:
            _, remaining = helpers.create_repaired_formula_fields(
                tool_context.user,
                table,
                formula_fixer,
                errors,
                ctx.deps.tool_helpers.raise_if_cancelled,
            )
        except PermissionException:
            creation.notes.append(
                f"Permission denied while creating fields in table_{table_id}. "
                "The tables were created, but further field setup stopped. "
                "Do not retry the denied operation."
            )
            creation.permission_denied = True
            denied = True
            # The fields repaired before the denial exist.
            created = set(table.field_set.values_list("name", flat=True))
            remaining = [e for e in errors if e["field_name"] not in created]
        _note_unrepaired_formulas(creation, table_id, remaining)
    creation.formula_errors = []


def _note_unrepaired_formulas(
    creation: shared_tables.TableCreation, table_id: int, errors: list[dict]
) -> None:
    for error in errors:
        if not helpers.has_formula(error):
            creation.notes.append(
                f"Formula field '{error['field_name']}' in table_{table_id} was "
                f"not created: it needs a formula."
            )
            continue
        creation.notes.append(
            f"Invalid formula for field '{error['field_name']}' "
            f"in table_{table_id}: {error['error'].rstrip('.')}. "
            f"Use generate_formula to fix it."
        )


def _create_sample_rows(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers: "ToolHelpers",
    tables: list[Table],
    sample_rows: bool | str,
) -> tuple[dict[int, list[Any]], list[str]]:
    """Create requested sample rows and return any failure note."""

    if not sample_rows or not tables:
        return {}, []

    data_brief = sample_rows if isinstance(sample_rows, str) else None
    try:
        rows = generate_sample_rows(
            user, workspace, tool_helpers, tables, data_brief=data_brief
        )
    except Exception as exc:
        logger.exception(
            "[assistant] generate_sample_rows raised unexpectedly: {}", exc
        )
        return {}, [f"Error creating sample rows: {exc}"]
    missing = [
        f"{table.name} (table_{table.id})" for table in tables if not rows.get(table.id)
    ]
    if missing:
        return rows, [
            f"Sample rows are still missing for {', '.join(missing)}. "
            "The tables were created, but the sample-data request is incomplete. "
            "Use load_row_tools for those table IDs, inspect existing rows, and "
            "add the missing samples before finishing the request."
        ]
    return rows, []


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
    DO NOT USE to invent backing data when an app request only asks to show records. If list_tables found no matching data, ask_user where it should come from unless the user already authorized new data storage or sample rows. An app's stated purpose alone does not authorize them.
    WHAT it does: Reuses exact-name matches, creates missing tables with fields, and generates sample rows for newly created tables by default. A reused table returns its actual schema and next_steps when that schema is incomplete. Pass add_sample_rows=false ONLY when the user explicitly asks for empty tables.
        Pass a string to guide the kind of sample data generated (e.g. "Italian recipes with calorie counts"). Table names must be unique. Reversed link_row fields are auto-created.
        At the end, this tool automatically navigates the user to the last created table.
    RETURNS: Created and reused table schemas with all field IDs. Notes on any errors.
    HOW: Pass ALL related tables in a single call — link_row fields can reference other tables in the same call by name (they are created internally before fields are added). Choose appropriate field types for each column.
        Use single_select/multiple_select with select_options for categorical data. The primary field is always text — pick a meaningful name for it.
        A lookup whose target is a formula or lookup of a table listed after it fails, as that target doesn't exist yet: list that table first, or add the lookup with create_fields after this call.
    REQUIRED: `database_id` and `tables` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_tables", "tables", tables)

    tool_context = ctx.deps.tool_context()
    database = shared_tables.get_database(tool_context, database_id)
    try:
        creation = shared_tables.create_tables_in_database(
            tool_context, database, tables
        )
    except DjangoValidationError as exc:
        raise ModelRetry(" ".join(exc.messages))

    # The tables are committed now, so the fixer's model call is outside it.
    _repair_table_formulas(ctx, creation)
    created_tables = creation.created_tables
    if created_tables:
        last_table = created_tables[-1]
        tool_helpers.navigate_to(
            TableNavigationType(
                type="database-table",
                database_id=database.id,
                table_id=last_table.id,
                table_name=last_table.name,
            )
        )

    # A link_row or lookup to an existing table adds a reverse field there.
    _refresh_row_tools(ctx)
    created_rows, row_notes = _create_sample_rows(
        user,
        workspace,
        tool_helpers,
        created_tables,
        add_sample_rows if not creation.permission_denied else False,
    )
    creation.notes.extend(row_notes)

    response = creation.to_response()
    if created_rows:
        response["created_rows"] = {
            f"Row IDs for newly created rows in table_{table_id}": [
                row.id for row in rows
            ]
            for table_id, rows in created_rows.items()
        }
    if "next_steps" in response:
        response["next_steps"] = reconciliation.reused_tables_next_steps(
            response["incomplete_reused_tables"]
        )
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
    REQUIRED: `table_id` and `fields` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace

    require_payload("create_fields", "fields", fields)

    table = helpers.get_table(user, workspace, table_id)
    result = shared_fields.create_fields(ctx.deps.tool_context(), table.id, fields)

    formula_errors = result.pop("formula_errors", [])
    if formula_errors:
        formula_fixer = make_formula_fixer(user, workspace, ctx.deps.tool_helpers)
        repaired, formula_errors = helpers.create_repaired_formula_fields(
            user,
            table,
            formula_fixer,
            formula_errors,
            ctx.deps.tool_helpers.raise_if_cancelled,
        )
        result["created_fields"].extend(field.model_dump() for field in repaired)
    if formula_errors:
        for err in formula_errors:
            err["hint"] = (
                "Use generate_formula to create a valid formula for this field."
            )
        result["formula_errors"] = formula_errors

    _refresh_row_tools(ctx)
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
    HOW: Call get_tables_schema first to see current field IDs, types and option IDs. For select options, use add_options, update_options and remove_options; options you don't list stay as they are.
    """

    if not fields:
        return {"updated_fields": [], "errors": [], "changed": False}

    tool_context = ctx.deps.tool_context()
    try:
        result = shared_fields.update_fields(tool_context, fields)
    except DjangoValidationError as exc:
        # Another operation holds a lock on one of the fields.
        raise ModelRetry(" ".join(exc.messages))

    formula_errors = result.pop("formula_errors", [])
    if formula_errors:
        formula_fixer = make_formula_fixer(
            ctx.deps.user, ctx.deps.workspace, ctx.deps.tool_helpers
        )
        repaired, changed, errors = helpers.apply_repaired_formula_updates(
            tool_context,
            formula_fixer,
            fields,
            formula_errors,
            ctx.deps.tool_helpers.raise_if_cancelled,
        )
        result["updated_fields"].extend(field.model_dump() for field in repaired)
        result["changed"] = result["changed"] or changed
        if errors:
            result["errors"] = [*result.get("errors", []), *errors]

    _refresh_row_tools(ctx)
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

    if not field_ids:
        return {"deleted_field_ids": [], "errors": []}

    result = shared_fields.delete_fields(ctx.deps.tool_context(), field_ids)

    _refresh_row_tools(ctx)
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
    RETURNS: Created views with id, name, type configuration. Views whose name is already used are not created and are listed in skipped_views.
    DO NOT USE when: The default grid view already meets the user's needs. Check existing views with list_views to avoid duplicates.
    HOW: Each view type requires specific config. Form views: provide field_options listing every field to show (field_id, name, order, required). Kanban: set column_field_id to a single_select field. Calendar: set date_field_id to a date field. Timeline: set both start/end date fields. Gallery: optionally set cover_field_id to a file field. Call get_tables_schema first to get the field IDs you need.
    REQUIRED: `table_id` and `views` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.
    """

    require_payload("create_views", "views", views)

    table = helpers.get_table(ctx.deps.user, ctx.deps.workspace, table_id)
    try:
        result = shared_views.create_views(ctx.deps.tool_context(), table.id, views)
    except DjangoValidationError as exc:
        raise ModelRetry(" ".join(exc.messages))

    created_views = result["created_views"]
    if created_views:
        ctx.deps.tool_helpers.navigate_to(
            ViewNavigationType(
                type="database-view",
                database_id=table.database_id,
                table_id=table.id,
                view_id=created_views[0]["id"],
                view_name=created_views[0]["name"],
                view_type=created_views[0]["type"],
            )
        )

    return result


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
    RETURNS: Created filters with id and configuration per view. Filters that can't be created (missing field, another type, wrong value, unknown option label, or a form view) are returned in skipped_filters with the reason.
    DO NOT USE when: The view doesn't exist yet — create it first with create_views.
    HOW: Get the table schema first to know field IDs and types. Match filter type to field type.
    REQUIRED: `view_filters` must contain at least one entry, each carrying the ID of the view it applies to. The ID says where to act; the payload says what to create. A call carrying no entries creates nothing and is rejected.

    ## Value formats by type

    - text: string
    - number: number
    - date: ISO date string (mode=exact_date) or integer (mode=nr_days_ago etc.) or "" (mode=today etc.)
    - single_select / multiple_select: list of option label strings (matched ignoring case and outer spaces)
    - link_row: row ID (integer)
    - boolean: true / false
    """

    require_payload("create_view_filters", "view_filters", view_filters)

    return shared_views.create_view_filters(ctx.deps.tool_context(), view_filters)


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
) -> dict[str, str | int]:
    """\
    Generate a formula from a natural-language description and save it.

    WHEN to use: User needs a computed field (formulas, calculations, cross-table lookups). No need to inspect the schema first — this tool does it automatically.
    WHAT it does: Generates a valid Baserow formula from a natural-language description. Finds the best table and fields automatically. Saves to a formula field by default (save_to_field=true).
    RETURNS: Generated formula string, formula type, and field details (name, table, operation).
    DO NOT USE when: The user wants a simple non-formula field — use create_fields instead.
    HOW: Describe what the formula should compute in plain language. The tool auto-discovers the table schema — no need to inspect it first.

    :param ctx: The assistant context containing the user, workspace, and helpers.
    :param database_id: The database whose tables may receive the formula.
    :param description: A natural-language description of the desired formula.
    :param save_to_field: Whether to save the formula to a field.
    :param thought: Brief reasoning for invoking the tool.
    :return: Formula metadata, including an integer table ID when a field is saved.
    :raises ModelRetry: If generation fails, the formula is invalid, or its target
        table is unavailable.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    database_tables = helpers.readable_database_tables(user, workspace, database_id)
    database_tables_schema = [
        t.model_dump() for t in helpers.get_tables_schema(database_tables, True)
    ]

    tool_helpers.update_status(_("Generating formula..."))

    prompt = format_formula_generation_prompt(
        description, database_tables_schema, get_formula_docs()
    )

    try:
        agent_result = run_formula_generation(
            user, workspace, prompt, tool_helpers.model_profile
        )
    except ModelRetry:
        # A retry prompt for the model, not a failure to rewrite as one below.
        raise
    except Exception as exc:
        raise_if_permission_denied(exc)
        # A sub-agent failure must not end the turn; create_tables does the same.
        logger.exception("[assistant] formula_generation_agent raised unexpectedly")
        raise ModelRetry(
            f"The formula generator failed: {exc}. Retry with a simpler "
            "description, or create the field without a formula."
        ) from exc

    result = agent_result.output

    # Recoverable: the orchestrator can rephrase or retarget; raising ends the turn.
    if not result.is_formula_valid:
        raise ModelRetry(
            f"Could not generate a valid formula: {result.error_message} "
            "Rephrase the description, or tell the user which part is not "
            "expressible in the Baserow formula language."
        )

    table = next((t for t in database_tables if t.id == result.table_id), None)
    if table is None:
        valid = ", ".join(f"{t.id} ({t.name})" for t in database_tables)
        raise ModelRetry(
            f"The generated formula targets table {result.table_id}, which is not "
            f"in database {database_id}. Tables available: {valid}"
        )

    data: dict[str, str | int] = {
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

        # Saving over a non-formula field trashes it, changing the row schema.
        _refresh_row_tools(ctx)

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
    resource_changes: ResourceChanges | None = None,
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
    :param resource_changes: Successful changes shared for the current run so
        rebuilding tools after a schema change preserves the running count.
    """

    row_model_for_create = get_create_row_model(table, field_ids=field_ids)
    row_model_for_update = get_update_row_model(table)
    link_row_hints = get_link_row_hints(row_model_for_create)
    if resource_changes is None:
        resource_changes = ResourceChanges()

    @return_permission_error(f"create_rows_in_table_{table.id}")
    def _create_rows(
        rows: list[row_model_for_create],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """Create new rows in the specified table."""

        require_payload(f"create_rows_in_table_{table.id}", "rows", rows)

        tool_helpers.update_status(
            _("Creating rows in %(table_name)s ") % {"table_name": table.name}
        )

        validated_rows = [row.to_django_orm() for row in rows]

        with transaction.atomic():
            orm_rows = CreateRowsActionType.do(user, table, validated_rows)

        total_rows_created = resource_changes.record_created_rows(
            table.id, len(orm_rows)
        )
        return {
            "created_row_ids": [r.id for r in orm_rows],
            "total_rows_created": total_rows_created,
        }

    create_rows_tool = Tool(
        _create_rows,
        name=f"create_rows_in_table_{table.id}",
        metadata={"table_id": table.id},
        description=(
            f"WHEN: Creating new rows in '{table.name}' (ID: {table.id}). "
            f"WHAT: Inserts rows with field values matching the table schema. "
            f"Use property names exactly as listed in the schema, including spaces; "
            f"do not include extra quote characters in the property names. "
            f"Keep batches to at most 20 rows to avoid oversized generated arguments; "
            f"for more rows, call this tool again with the next batch. When the user "
            f"asks for N rows, the batches must add up to exactly N. "
            f"RETURNS: Created row IDs and total_rows_created, the rows created in "
            f"this table during this run; use it to reach a requested count exactly. "
            f"DO NOT USE: For other tables — each table has its own create tool. "
            f"HOW: Fill EVERY field including ALL link_row (relationship) fields. Never skip a field unless data is genuinely unavailable."
            f"{link_row_hints}"
            f" REQUIRED: `rows` must contain at least one row. This tool already "
            f"knows where to write, so the call must also carry what to create; a "
            f"call with an empty `rows` creates nothing and is rejected."
        ),
        max_retries=2,
    )
    create_rows_tool.function_schema.json_schema = inline_refs(
        create_rows_tool.function_schema.json_schema
    )

    @return_permission_error(f"update_rows_in_table_{table.id}")
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
        metadata={"table_id": table.id},
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

    @return_permission_error(f"delete_rows_in_table_{table.id}")
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
        metadata={"table_id": table.id},
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


def _refresh_row_tools(ctx: RunContext[AssistantDeps]) -> None:
    """
    Rebuild the loaded row tools so their schema matches the table's fields.

    Row tools bake the table schema into their signature when loaded, so a field
    change leaves them rejecting new fields or writing to dropped columns. Every
    loaded table is rebuilt, because a link_row field also adds a reverse field
    to the table it points at.

    :param ctx: The run context holding the dynamic tool registry.
    """

    dynamic_tools = ctx.deps.dynamic_tools
    if not dynamic_tools:
        return

    table_ids = {
        tool.metadata["table_id"]
        for tool in dynamic_tools
        if tool.metadata and "table_id" in tool.metadata
    }
    tables = helpers.filter_tables(ctx.deps.user, ctx.deps.workspace).filter(
        id__in=table_ids
    )

    rebuilt: dict[str, Tool] = {}
    for table in tables:
        try:
            row_tools = _build_row_tools(
                ctx.deps.user,
                ctx.deps.workspace,
                ctx.deps.tool_helpers,
                table,
                resource_changes=ctx.deps.resource_changes,
            )
        except Exception:
            # Raising would fail a field change that already succeeded.
            logger.exception(
                "[assistant] could not refresh row tools for table {}", table.id
            )
            continue
        # delete_rows takes row IDs only, so its signature cannot go stale.
        rebuilt.update(
            {row_tools[op].name: row_tools[op] for op in ("create", "update")}
        )

    dynamic_tools[:] = [rebuilt.get(tool.name, tool) for tool in dynamic_tools]


# ---------------------------------------------------------------------------
# Tool 10: load_row_tools
# ---------------------------------------------------------------------------


_ROW_OPERATION_NAMES = {
    "create": CreateRowDatabaseTableOperationType.type,
    "update": UpdateDatabaseRowOperationType.type,
    "delete": DeleteDatabaseRowOperationType.type,
}


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
    DO NOT USE when: Row tools for these tables are already loaded and no field has changed since — one call per table is enough.
    AFTER A SCHEMA CHANGE: create_fields, update_fields and delete_fields refresh the loaded row tools automatically, so no reload is needed. If a row tool still rejects a field you just created, call this again: reloading replaces the stale tools with ones matching the current schema.
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

    tables = list(helpers.filter_tables(user, workspace).filter(id__in=table_ids))
    if not tables:
        return (
            "No valid tables found for the given IDs. "
            "Make sure the table IDs are correct."
        )

    # The loaded tools describe every field, so only permitted operations load.
    permitted_table_ids = {
        operation: {
            table.id
            for table in shared_tables.permitted_tables(
                ctx.deps.tool_context(), tables, operation_name
            )
        }
        for operation, operation_name in _ROW_OPERATION_NAMES.items()
        if operation in operations
    }
    new_tools: list[Tool] = []
    for table in tables:
        permitted = [
            operation
            for operation, ids in permitted_table_ids.items()
            if table.id in ids
        ]
        if not permitted:
            continue
        table_tools = _build_row_tools(
            user,
            workspace,
            tool_helpers,
            table,
            resource_changes=ctx.deps.resource_changes,
        )
        new_tools.extend(table_tools[operation] for operation in permitted)
    if permitted_table_ids and not new_tools:
        raise PermissionDenied()

    # Replaced by name: reloads must see schema changes, and add_tool rejects dupes.
    new_names = {t.name for t in new_tools}
    ctx.deps.dynamic_tools[:] = [
        t for t in ctx.deps.dynamic_tools if t.name not in new_names
    ] + new_tools

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
database_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)
