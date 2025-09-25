from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple, NewType, TypedDict, TypeVar

from django.db.models import QuerySet

from baserow.contrib.database.field_rules.collector import CascadeUpdatedRows
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.core.action.registries import ActionType
from baserow.core.action.signals import ActionCommandType

GeneratedTableModelForUpdate = NewType(
    "GeneratedTableModelForUpdate", GeneratedTableModel
)

RowsForUpdate = NewType("RowsForUpdate", QuerySet)


class FileImportConfiguration(TypedDict):
    upsert_fields: list[int]
    upsert_values: list[list[Any]]
    skipped_fields: list[int]


class FileImportDict(TypedDict):
    data: list[list[Any]]
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
    updated_field_ids: Iterable[int] | None = None

    # use cascade update fields to propagate rows that weren't requested
    # by the user to be updated, but were updated by various operations in the
    # code (i.e. field rules).
    cascade_update: CascadeUpdatedRows | None = None


class CreatedRowsData(NamedTuple):
    created_rows: list[GeneratedTableModel]
    errors: dict[int, dict[str, Any]] | None = None
    updated_field_ids: list[int] | None = None
    cascade_update: CascadeUpdatedRows | None = None


FieldName = NewType("FieldName", str)

# Dict of table_id -> row_id -> field_name ->
# {added: List[row_id], removed:List[row_id], metadata: Dict}
RelatedRowsDiff = dict[int, dict[int, dict[str, dict[str, Any]]]]


@dataclass
class ActionData:
    """
    A container for action params to be used in post-action handlers
    """

    uuid: str
    type: "ActionType"
    timestamp: datetime
    command_type: ActionCommandType
    params: dict[str, Any]


class RowChangeDiff(NamedTuple):
    """
    Represents the diff between the before and after values of a row. It
    contains the names of the fields that have changed, as well as the before
    and after values of those fields.
    """

    row_id: int
    table_id: int
    changed_field_names: list[FieldName]
    before_values: dict[FieldName, Any]
    after_values: dict[FieldName, Any]


ActionTypeVar = TypeVar("ActionTypeVar", bound=ActionType)
