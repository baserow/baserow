from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .fields import AnyFieldItem, AnyFieldItemCreate


class BaseTableItemCreate(BaseModel):
    """Model for an existing table (with ID)."""

    name: str = Field(..., description="The name of the table.")


class BaseTableItem(BaseTableItemCreate):
    """Base model for creating a new table (no ID)."""

    id: int = Field(..., description="The unique identifier of the table.")


class TableItemCreate(BaseTableItemCreate):
    """Model for creating a table with fields."""

    primary_field: AnyFieldItemCreate = Field(
        ...,
        description="The primary field of the table. Preferbly a text field with a sensible name for a primary field of the table.",
    )
    fields: list[AnyFieldItemCreate] = Field(
        ..., description="The fields of the table."
    )


class TableItem(BaseTableItem):
    """Model for an existing table with fields."""

    primary_field: AnyFieldItem = Field(
        ..., description="The primary field of the table."
    )
    fields: list[AnyFieldItem] = Field(..., description="The fields of the table.")
