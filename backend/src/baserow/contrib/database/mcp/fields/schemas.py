from __future__ import annotations

from pydantic import BaseModel, Field


class CreateFieldsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to add fields to.")
    fields: list[dict] = Field(
        ...,
        description=(
            "List of fields to create. Each item must have 'name' "
            "and 'type'. See create_table for valid types and extras."
        ),
    )


class UpdateFieldsInput(BaseModel):
    fields: list[dict] = Field(
        ...,
        description=(
            "List of field updates. Each item must have 'id' "
            "plus the properties to change (name, type, "
            "or type-specific options)."
        ),
    )


class DeleteFieldsInput(BaseModel):
    field_ids: list[int] = Field(..., description="List of field IDs to delete.")
