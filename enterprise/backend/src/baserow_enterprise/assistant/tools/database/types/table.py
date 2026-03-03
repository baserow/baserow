from django.db.models import Q

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .fields import FieldItem, FieldItemCreate


class BaseTableItemCreate(BaseModel):
    """Model for an existing table (with ID)."""

    name: str = Field(..., description="The name of the table.")


class BaseTableItem(BaseTableItemCreate):
    """Base model for creating a new table (no ID)."""

    id: int = Field(..., description="The unique identifier of the table.")


class TableItemCreate(BaseTableItemCreate):
    """Model for creating a table with fields."""

    primary_field_name: str = Field(
        ...,
        description="The name of the primary field (text field).",
    )
    fields: list[FieldItemCreate] = Field(..., description="The fields of the table.")


class TableItem(BaseTableItem):
    """Model for an existing table with fields."""

    primary_field: FieldItem = Field(..., description="The primary field of the table.")
    fields: list[FieldItem] = Field(..., description="The fields of the table.")


class ListTablesFilterArg(BaseModel):
    database_id_or_name: int | str = Field(
        ...,
        description="The ID or name of the database to filter. null to exclude this filter.",
    )
    table_ids_or_names: list[int | str] | None = Field(
        ...,
        description="A list of table ids or names to filter in an OR fashion. null to exclude this filter.",
    )

    def to_orm_filter(self) -> Q:
        q_filter = Q()
        if isinstance(self.database_id_or_name, int):
            q_filter &= Q(database_id=self.database_id_or_name)
        elif isinstance(self.database_id_or_name, str):
            q_filter &= Q(database__name__icontains=self.database_id_or_name)
        if self.table_ids_or_names:
            id_filter = Q()
            name_filter = Q()
            for item in self.table_ids_or_names:
                if isinstance(item, int):
                    id_filter |= Q(id=item)
                elif isinstance(item, str):
                    name_filter |= Q(name__icontains=item)
            q_filter &= id_filter | name_filter
        return q_filter
