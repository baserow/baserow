from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FieldSpec(BaseModel):
    """A field to create: name and type are required, extra keys are type-specific."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="The field name.")
    type: str = Field(..., description="The field type (e.g. text, number, link_row).")


class FieldUpdateSpec(BaseModel):
    """A field to update: id is required, extra keys are the properties to change."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(..., description="The ID of the field to update.")


class CreateFieldsInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to add fields to.")
    fields: list[FieldSpec] = Field(
        ...,
        description=(
            "List of fields to create. Each item must have 'name' "
            "and 'type'. See create_table for valid types and extras."
        ),
    )


class UpdateFieldsInput(BaseModel):
    fields: list[FieldUpdateSpec] = Field(
        ...,
        description=(
            "List of field updates. Each item must have 'id' "
            "plus the properties to change (name, type, "
            "or type-specific options)."
        ),
    )


class DeleteFieldsInput(BaseModel):
    field_ids: list[int] = Field(..., description="List of field IDs to delete.")
