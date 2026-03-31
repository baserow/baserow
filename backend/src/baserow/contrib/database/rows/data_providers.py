from typing import List, Union

from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
from baserow.core.formula.registries import DataProviderType


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
