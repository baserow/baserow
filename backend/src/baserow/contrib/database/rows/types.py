import typing
from typing import Any, NamedTuple, NewType

from django.db.models import QuerySet

from baserow.contrib.database.table.models import GeneratedTableModel

GeneratedTableModelForUpdate = NewType(
    "GeneratedTableModelForUpdate", GeneratedTableModel
)

RowsForUpdate = NewType("RowsForUpdate", QuerySet)


class FileImportConfiguration(typing.TypedDict):
    upsert_fields: list[int]
    upsert_values: list[list[typing.Any]]


class FileImportDict(typing.TypedDict):
    data: list[list[typing.Any]]
    configuration: FileImportConfiguration | None


FieldsMetadata = NewType("FieldsMetadata", dict[str, Any])
RowValues = NewType("RowValues", dict[str, Any])
RowId = NewType("RowId", int)


class UpdatedRowsData(NamedTuple):
    updated_rows: list[GeneratedTableModelForUpdate]
    updated_rows_values: list[RowValues]
    original_rows_values_by_id: dict[RowId, RowValues]
    updated_fields_metadata_by_row_id: dict[RowId, FieldsMetadata]
    errors: dict[int, dict[str, Any]] | None = None


class CreatedRowsData(NamedTuple):
    created_rows: list[GeneratedTableModel]
    errors: dict[int, dict[str, Any]] | None = None
