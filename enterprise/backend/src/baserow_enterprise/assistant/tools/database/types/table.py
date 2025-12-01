from django.db.models import Q

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


class ListTablesFilterArg(BaseModel):
    database_ids: list[int] | None = Field(
        default=None,
        description="A list of database_ids to filter. None to exclude this filter",
    )
    database_names: list[str] | None = Field(
        default=None,
        description="A list of database_names to filter. None to exclude this filter",
    )
    table_ids: list[int] | None = Field(
        default=None,
        description="A list of table ids to filter. None to exclude this filter",
    )
    table_names: list[str] | None = Field(
        default=None,
        description="A list of table names to filter. None to exclude this filter",
    )

    def to_orm_filter(self) -> Q:
        q_filter = Q()
        if self.database_ids:
            q_filter &= Q(database_id__in=self.database_ids)
        if self.database_names:
            q_filter &= Q(database__name__in=self.database_names)
        if self.table_ids:
            q_filter &= Q(id__in=self.table_ids)
        if self.table_names:
            q_filter &= Q(name__in=self.table_names)
        return q_filter
