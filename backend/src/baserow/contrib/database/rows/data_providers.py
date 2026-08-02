from typing import TYPE_CHECKING, Any, Dict, List, Union

from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.core.formula.registries import DataProviderType

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


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

        # Both providers live in the same registry, so a `get('fields.…')`
        # written in a button action argument resolves here against a
        # `DatabaseDispatchContext`, which has no human readable values. Return
        # nothing rather than raising an `AttributeError` the caller sees as a
        # 500.
        row_values = getattr(dispatch_context, "human_readable_row_values", None)
        if row_values is None:
            return None

        return row_values.get(first_part, "")


class RowDataProviderType(DataProviderType):
    """
    Exposes the clicked row's values with their real types, for button field
    workflow actions.

    Deliberately separate from `HumanReadableFieldsDataProviderType`, which
    stringifies every value. That is correct for prompt text and for building a
    URL client side, and wrong for writing a number, date or link into a row
    (ADR 006 section 4). Action arguments must resolve through this provider.

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

        # The mirror of the guard in `HumanReadableFieldsDataProviderType`: a
        # `get('row.…')` written in an AI field's prompt resolves here against a
        # `HumanReadableRowContext`, which carries no row.
        row = getattr(dispatch_context, "row", None)
        if row is None:
            return None

        # The row's own id, so an update or delete action can target the row
        # that was clicked. `row_id` on those services is a formula, so
        # `get('row.id')` is the only way to express it.
        if field_name == "id":
            return row.id

        field_names = {
            field_object["name"]
            for field_object in row._meta.model._field_objects.values()
        }
        if field_name not in field_names:
            return None

        return getattr(row, field_name, None)

    def import_path(
        self, path: List[str], id_mapping: Dict[str, Any], **kwargs
    ) -> List[str]:
        """
        Points a `get('row.field_25')` at the imported field, so a duplicated
        table or an imported database writes the field of the copy rather than
        the one the formula was written against.
        """

        if len(path) != 1 or "database_fields" not in id_mapping:
            return path

        field_dbname = path[0]

        # `row.id` is the only other path this provider serves, and it is not a
        # field reference. Anything else isn't ours to remap either.
        if not str(field_dbname).startswith("field_"):
            return path

        field_id = get_field_id_from_field_key(field_dbname)
        new_field_id = id_mapping["database_fields"].get(field_id)

        # A field missing from the mapping was trashed or never exported. The
        # reference is kept as it is, the same as the `open_url` action's url:
        # the import must not fail, and the broken state surfaces at dispatch.
        if not new_field_id:
            return path

        return [f"field_{new_field_id}"]
