import dataclasses

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.models import LongTextField, TextField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.registries import view_type_registry


@dataclasses.dataclass
class ImportReportFailedItem:
    object_name: str
    category: str
    table: str
    message: str


class AirtableImportReport:
    def __init__(self):
        self.items = []

    def add_failed(self, object_name, category, table, message):
        self.items.append(ImportReportFailedItem(object_name, category, table, message))

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
            TextField(id="object", name="Object", order=0, primary=True),
            TextField(id="category", name="Category", order=1),
            TextField(id="table", name="Table", order=2),
            LongTextField(id="message", name="Message", order=3),
        ]
        exported_fields = [
            field_type_registry.get_by_model(field).export_serialized(field)
            for field in fields
        ]

        exported_rows = []
        for index, item in enumerate(self.items):
            row = DatabaseExportSerializedStructure.row(
                id=index,
                order=f"{index + 1}.00000000000000000000",
                created_on=None,
                updated_on=None,
            )
            row["field_object"] = item.object_name
            row["field_category"] = item.category
            row["field_table"] = item.table
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
