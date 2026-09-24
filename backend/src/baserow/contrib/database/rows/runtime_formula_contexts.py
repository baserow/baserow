from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext


class HumanReadableRowContext(RuntimeFormulaContext):
    def __init__(self, row, exclude_field_ids=None):
        if exclude_field_ids is None:
            exclude_field_ids = []

        model = row._meta.model
        self.human_readable_row_values = {
            f"field_{field['field'].id}": field["type"].get_human_readable_value(
                getattr(row, field["name"]), field
            )
            for field in model._field_objects.values()
            if field["field"].id not in exclude_field_ids
        }
        # Not a field, but a button's URL is resolved through this provider and
        # linking back to the clicked row is the common case.
        self.human_readable_row_values["id"] = row.id

        super().__init__()

    @property
    def data_provider_registry(self):
        return database_data_provider_type_registry
