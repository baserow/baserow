import dataclasses

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.models import LongTextField, TextField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.registries import view_type_registry

SCOPE_FIELD = "Field"
SCOPE_CELL = "Cell"
SCOPE_VIEW = "View"
SCOPE_AUTOMATIONS = "Automations"
SCOPE_INTERFACES = "Interfaces"

ERROR_TYPE_UNSUPPORTED_FEATURE = "Unsupported feature"
ERROR_TYPE_DATA_TYPE_MISMATCH = "Data type mismatch"
ERROR_TYPE_OTHER = "Other"


@dataclasses.dataclass
class ImportReportFailedItem:
    object_name: str
    scope: str
    table: str
    error_type: str
    message: str


class AirtableImportReport:
    def __init__(self):
        self.items = []

    def add_failed(self, object_name, scope, table, error_type, message):
        self.items.append(
            ImportReportFailedItem(object_name, scope, table, error_type, message)
        )

    def get_baserow_export_table(self, order: int) -> dict:
        # Create an empty grid view because the importing of views doesn't work
        # yet. It's a bit quick and dirty, but it will be replaced soon.
        grid_view = GridView(pk=0, id=None, name="Grid", order=1)
        grid_view.get_field_options = lambda *args, **kwargs: []
        grid_view_type = view_type_registry.get_by_model(grid_view)
        empty_serialized_grid_view = grid_view_type.export_serialized(
            grid_view, None, None, None
        )
        empty_serialized_grid_view["id"] = 0
        exported_views = [empty_serialized_grid_view]

        fields = [
            TextField(id="object_name", name="Object name", order=0, primary=True),
            TextField(id="scope", name="Scope", order=1),
            TextField(id="table", name="Table", order=2),
            TextField(id="error_type", name="Error type", order=3),
            LongTextField(id="message", name="Message", order=4),
        ]
        exported_fields = [
            field_type_registry.get_by_model(field).export_serialized(field)
            for field in fields
        ]

        exported_rows = []
        for index, item in enumerate(self.items):
            row = DatabaseExportSerializedStructure.row(
                id=index + 1,
                order=f"{index + 1}.00000000000000000000",
                created_on=None,
                updated_on=None,
            )
            row["field_object_name"] = item.object_name
            row["field_scope"] = item.scope
            row["field_table"] = item.table
            row["field_error_type"] = item.error_type
            row["field_message"] = item.message
            exported_rows.append(row)

        exported_table = DatabaseExportSerializedStructure.table(
            id="report",
            name="Airtable import report",
            order=order,
            fields=exported_fields,
            views=exported_views,
            rows=exported_rows,
            data_sync=None,
        )

        return exported_table
