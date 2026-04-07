from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ListRowsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to list rows from.")
    search: str | None = Field(None, description="Optional search term to filter rows.")
    page: int = Field(1, description="Page number (1-based).")
    size: int = Field(100, description="Maximum number of rows to return.")


class CreateRowsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to create rows in.")
    rows: list[dict] = Field(
        ...,
        description=(
            "List of rows to create. Each row is an object mapping field name to value."
        ),
    )


class RowUpdateSpec(BaseModel):
    """A row to update: id is required, extra keys are field name → new value."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="The row ID.")


class UpdateRowsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table containing the rows.")
    rows: list[RowUpdateSpec] = Field(
        ...,
        description=(
            "List of rows to update. Each row must have 'id' "
            "plus the field names and their new values."
        ),
    )


class DeleteRowsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to delete rows from.")
    row_ids: list[int] = Field(..., description="List of row IDs to delete.")
