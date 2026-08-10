from typing import TYPE_CHECKING, Any, Dict, List, Union

from baserow.contrib.database.fields.exceptions import (
    ReadOnlyFieldHasNoInternalDbValueError,
)
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.core.formula.registries import DataProviderType

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


def _import_field_path(path: List[str], id_mapping: Dict[str, Any]) -> List[str]:
    """
    Rewrites a `field_25` path segment to the id that field got on import, so a
    duplicated table or an imported database reads its own field rather than the
    one the formula was written against.
    """

    if len(path) != 1 or "database_fields" not in id_mapping:
        return path

    field_dbname = path[0]

    # Paths that are not field references are not ours to remap.
    if not str(field_dbname).startswith("field_"):
        return path

    new_field_id = id_mapping["database_fields"].get(
        get_field_id_from_field_key(field_dbname)
    )

    # A field missing from the mapping was trashed or never exported. The
    # reference is kept as it is: the import must not fail, and the broken state
    # surfaces at dispatch.
    if not new_field_id:
        return path

    return [f"field_{new_field_id}"]


class HumanReadableFieldsDataProviderType(DataProviderType):
    """
    This data provider type is used to read the human-readable values for the row
    fields. This is used for example in the AI field to be able to reference other
    fields in the same row to generate a different prompt for each row based on the
    values of the other fields.
    """

    type = "fields"

    def get_data_chunk(
        self, dispatch_context: HumanReadableRowContext, path: List[str]
    ) -> Union[int, str] | None:
        """
        When a page parameter is read, returns the value previously saved from the
        request object.
        """

        if len(path) != 1:
            return None

        first_part = path[0]

        # Both providers share a registry, so a button action's `get('fields.…')`
        # lands here against a context with no human readable values.
        row_values = getattr(dispatch_context, "human_readable_row_values", None)
        if row_values is None:
            return None

        return row_values.get(first_part, "")

    def import_path(
        self, path: List[str], id_mapping: Dict[str, Any], **kwargs
    ) -> List[str]:
        return _import_field_path(path, id_mapping)


class RowDataProviderType(DataProviderType):
    """
    Exposes the clicked row's values with their real types, for button field
    workflow actions.

    Separate from `HumanReadableFieldsDataProviderType`, which stringifies every
    value. That suits prompt text and client-side URLs, but not writing a
    number, date or link back into a row (ADR 006 section 4).

    The row is a snapshot taken when the click was dispatched: every action in a
    sequence sees the row as it was at click time, even if an earlier action
    changed or deleted it.
    """

    type = "row"

    def get_data_chunk(
        self, dispatch_context: "DatabaseDispatchContext", path: List[str]
    ) -> Any:
        if len(path) != 1:
            return None

        field_name = path[0]

        # The mirror of the guard above: an AI prompt's `get('row.…')` lands
        # here against a context that carries no row.
        row = getattr(dispatch_context, "row", None)
        if row is None:
            return None

        # Lets an update or delete target the clicked row: `row_id` is a
        # formula, so `get('row.id')` is the only way to express it.
        if field_name == "id":
            return row.id

        field_object = next(
            (
                candidate
                for candidate in row._meta.model._field_objects.values()
                if candidate["name"] == field_name
            ),
            None,
        )
        if field_object is None:
            return None

        try:
            # A link row, select or collaborator field holds a manager or a
            # model instance, which no action can write. The field type turns
            # those into the ids the row API takes, and leaves the rest alone.
            return field_object["type"].get_internal_value_from_db(row, field_name)
        except ReadOnlyFieldHasNoInternalDbValueError:
            # A formula, count or rollup has nothing writable, but its computed
            # value is still worth reading as an argument.
            return getattr(row, field_name, None)

    def import_path(
        self, path: List[str], id_mapping: Dict[str, Any], **kwargs
    ) -> List[str]:
        # `row.id` is left alone: it is not a field reference.
        return _import_field_path(path, id_mapping)
