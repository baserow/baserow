from __future__ import annotations

from pydantic import BaseModel, Field


class ListDatabasesInput(BaseModel):
    pass


class UpdateTableInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to rename.")
    name: str = Field(..., description="The new name for the table.")


class DeleteTableInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to delete.")
