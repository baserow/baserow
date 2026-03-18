import json

from django.db.models import Q

from pydantic import Field, ValidationError, model_validator

from baserow_enterprise.assistant.types import BaseModel

from .fields import _FIELD_EXAMPLES, _TYPE_ALIASES, FieldItem, FieldItemCreate


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

    @model_validator(mode="wrap")
    @classmethod
    def _validate_with_field_examples(cls, data, handler):
        try:
            return handler(data)
        except ValidationError as exc:
            if not isinstance(data, dict):
                raise

            table_name = data.get("name", "unknown")
            fields_data = data.get("fields", [])
            if not isinstance(fields_data, list):
                raise

            # Collect field indices that have errors
            error_field_indices: set[int] = set()
            for error in exc.errors():
                loc = error.get("loc", ())
                if len(loc) >= 2 and loc[0] == "fields" and isinstance(loc[1], int):
                    error_field_indices.add(loc[1])

            if not error_field_indices:
                raise  # No field-level errors, re-raise as-is

            error_fields = []
            error_types: set[str] = set()
            for idx in sorted(error_field_indices):
                if idx < len(fields_data) and isinstance(fields_data[idx], dict):
                    fd = fields_data[idx]
                    fname = fd.get("name", f"fields[{idx}]")
                    ftype = str(fd.get("type", "unknown"))
                    ftype = _TYPE_ALIASES.get(ftype, ftype)
                    error_fields.append(f"'{fname}' ({ftype})")
                    if ftype in _FIELD_EXAMPLES:
                        error_types.add(ftype)

            if not error_fields:
                raise

            parts = [
                f"Table '{table_name}': invalid fields: {', '.join(error_fields)}."
            ]
            for ft in sorted(error_types):
                parts.append(f"  {ft}: {json.dumps(_FIELD_EXAMPLES[ft])}")

            raise ValueError("\n".join(parts)) from None


class TableItem(BaseTableItem):
    """Model for an existing table with fields."""

    primary_field: FieldItem = Field(..., description="The primary field of the table.")
    fields: list[FieldItem] = Field(..., description="The fields of the table.")


class ListTablesFilterArg(BaseModel):
    database_id_or_name: int | str | None = Field(
        default=None,
        description="The ID or name of the database to filter. null to exclude this filter.",
    )
    table_ids_or_names: list[int | str] | None = Field(
        default=None,
        description="A list of table ids or names to filter in an OR fashion. null to exclude this filter.",
    )

    def to_orm_filter(self) -> Q:
        q_filter = Q()
        if isinstance(self.database_id_or_name, int):
            q_filter &= Q(database_id=self.database_id_or_name)
        elif isinstance(self.database_id_or_name, str):
            q_filter &= Q(database__name__icontains=self.database_id_or_name)
        if self.table_ids_or_names:
            combined = Q()
            ids = [item for item in self.table_ids_or_names if isinstance(item, int)]
            names = [item for item in self.table_ids_or_names if isinstance(item, str)]
            if ids:
                combined |= Q(id__in=ids)
            if names:
                for name in names:
                    combined |= Q(name__icontains=name)
            q_filter &= combined
        return q_filter
