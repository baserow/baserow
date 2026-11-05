"""
Row tools shared by the clients that act for a user. Rows are read and written with
user field names and validated like the REST API's batch endpoints, and every tool
checks the table permission its REST endpoint checks.
"""

from typing import Annotated, Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from pydantic import BaseModel, ConfigDict, Field

from baserow.api.exceptions import RequestBodyValidationException
from baserow.api.utils import validate_data
from baserow.contrib.database.api.rows.serializers import (
    get_batch_row_serializer_class,
    get_row_serializer_class,
    serialize_rows_for_response,
)
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools.tables import get_table
from baserow.core.tools import ToolContext


class RowUpdate(BaseModel):
    """A row to update: its id, and its new values by field name."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="The row ID.")


def _check_field_names(model: type[GeneratedTableModel], rows: list[dict]) -> None:
    """
    Checks that every key of every row is ``id`` or a field name.

    :raises DjangoValidationError: When a key is neither.
    """

    names = [info["field"].name for info in model._field_objects.values()]
    for row in rows:
        for key in row:
            if key != "id" and key not in names:
                raise DjangoValidationError(
                    f"Unknown field name '{key}'. Available fields: {names}"
                )


def _validate_rows(
    model: type[GeneratedTableModel], rows: list[dict], update: bool = False
) -> list[dict]:
    """
    Validates rows keyed by field names with the REST API's row serializer, so a
    value the API would refuse gets the same message.

    :return: The validated rows, keyed by internal column names.
    :raises DjangoValidationError: When a key isn't a field name.
    :raises RequestBodyValidationException: When a value is invalid, with the
        errors of each row under ``rows``.
    """

    _check_field_names(model, rows)
    extra = {"include_id": True, "required_fields": ["id"]} if update else {}
    row_serializer = get_row_serializer_class(model, user_field_names=True, **extra)
    try:
        data = validate_data(
            get_batch_row_serializer_class(row_serializer),
            {"items": rows},
            partial=True,
            return_validated=True,
        )
    except RequestBodyValidationException as exc:
        detail = exc.detail["detail"]
        detail = detail.get("items", detail) if isinstance(detail, dict) else detail
        raise RequestBodyValidationException({"rows": detail}) from exc
    return data["items"]


def list_table_rows(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to list rows from.")
    ],
    search: Annotated[
        str | None, Field(description="Optional search term to filter rows.")
    ] = None,
    page: Annotated[int, Field(description="Page number (1-based).")] = 1,
    size: Annotated[int, Field(description="Maximum number of rows to return.")] = 100,
) -> dict[str, Any]:
    """
    List rows from a table with optional search and pagination. Returns rows with
    user-facing field names as keys.
    """

    table = get_table(ctx, table_id, ListRowsDatabaseTableOperationType.type)
    page = max(1, page)
    size = max(1, min(size, settings.ROW_PAGE_SIZE_LIMIT))
    model = table.get_model()
    queryset = model.objects.filter(trashed=False).order_by("order", "id")
    if search:
        queryset = queryset.search_all_fields(search)

    rows = list(queryset[(page - 1) * size : page * size])
    return {
        "count": queryset.count(),
        "results": list(
            serialize_rows_for_response(rows, model, user_field_names=True)
        ),
    }


def create_rows(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to create rows in.")
    ],
    rows: Annotated[
        list[dict],
        Field(
            description="List of rows to create. Each row is an object mapping "
            "field name to value."
        ),
    ],
) -> list[dict[str, Any]]:
    """
    Create one or more rows in a table. Call get_table_schema first to learn the
    field names and types. Use user-facing field names as keys, not internal field
    IDs.
    """

    table = get_table(ctx, table_id, CreateRowDatabaseTableOperationType.type)
    model = table.get_model()
    rows_values = _validate_rows(model, rows)
    with transaction.atomic():
        created = CreateRowsActionType.do(ctx.user, table, rows_values, model=model)
    return list(serialize_rows_for_response(created, model, user_field_names=True))


def update_rows(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table containing the rows.")
    ],
    rows: Annotated[
        list[RowUpdate],
        Field(
            description="List of rows to update. Each row must have 'id' plus the "
            "field names and their new values."
        ),
    ],
) -> list[dict[str, Any]]:
    """
    Update one or more existing rows in a table. Each row must include 'id' plus the
    fields to update. Call get_table_schema first to learn the field names. Use
    user-facing field names as keys, not internal field IDs.
    """

    table = get_table(ctx, table_id, UpdateDatabaseRowOperationType.type)
    model = table.get_model()
    rows_values = _validate_rows(model, [row.model_dump() for row in rows], update=True)
    with transaction.atomic():
        result = UpdateRowsActionType.do(ctx.user, table, rows_values, model=model)
    return list(
        serialize_rows_for_response(result.updated_rows, model, user_field_names=True)
    )


def delete_rows(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to delete rows from.")
    ],
    row_ids: Annotated[
        list[int],
        Field(
            max_length=settings.BATCH_ROWS_SIZE_LIMIT,
            description="List of row IDs to delete.",
        ),
    ],
) -> str:
    """
    Delete one or more rows from a table by ID. Use list_table_rows to find row IDs
    first.
    """

    table = get_table(ctx, table_id, DeleteDatabaseRowOperationType.type)
    DeleteRowsActionType.do(ctx.user, table, row_ids)
    return "Rows successfully deleted."
