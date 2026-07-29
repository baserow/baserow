from typing import TYPE_CHECKING, Any, List, Union

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

        return dispatch_context.human_readable_row_values.get(first_part, "")


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
        row = dispatch_context.row

        field_names = {
            field_object["name"]
            for field_object in row._meta.model._field_objects.values()
        }
        if field_name not in field_names:
            return None

        return getattr(row, field_name, None)
