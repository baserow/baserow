import dataclasses
import random

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.models import (
    LongTextField,
    SelectOption,
    SingleSelectField,
    TextField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.constants import BASEROW_COLORS
from baserow.core.registries import ImportExportConfig

REPORT_TABLE_ID = "report"
REPORT_TABLE_NAME = "Airtable import report"

SCOPE_FIELD = SelectOption(id="scope_field", value="Field", color="light-blue", order=1)
SCOPE_CELL = SelectOption(id="scope_cell", value="Cell", color="light-green", order=2)
SCOPE_VIEW = SelectOption(id="scope_view", value="View", color="light-cyan", order=3)
SCOPE_VIEW_SORT = SelectOption(
    id="scope_view_sort", value="View sort", color="light-red", order=4
)
SCOPE_VIEW_GROUP_BY = SelectOption(
    id="scope_view_group_by", value="View group by", color="light-brown", order=5
)
SCOPE_VIEW_FILTER = SelectOption(
    id="scope_view_filter", value="View filter", color="light-pink", order=6
)
SCOPE_VIEW_COLOR = SelectOption(
    id="scope_view_color", value="View color", color="light-gray", order=7
)
SCOPE_VIEW_FIELD_OPTIONS = SelectOption(
    id="scope_view_field_options",
    value="View field options",
    color="light-purple",
    order=8,
)
SCOPE_AUTOMATIONS = SelectOption(
    id="scope_automations", value="Automations", color="light-orange", order=9
)
SCOPE_INTERFACES = SelectOption(
    id="scope_interfaces", value="Interfaces", color="light-yellow", order=10
)
ALL_SCOPES = [
    SCOPE_FIELD,
    SCOPE_CELL,
    SCOPE_VIEW,
    SCOPE_VIEW_SORT,
    SCOPE_VIEW_GROUP_BY,
    SCOPE_VIEW_FILTER,
    SCOPE_VIEW_COLOR,
    SCOPE_AUTOMATIONS,
    SCOPE_INTERFACES,
]

ERROR_TYPE_UNSUPPORTED_FEATURE = SelectOption(
    id="error_type_unsupported_feature",
    value="Unsupported feature",
    color="yellow",
    order=1,
)
ERROR_TYPE_DATA_TYPE_MISMATCH = SelectOption(
    id="error_type_data_type_mismatch", value="Data type mismatch", color="red", order=2
)
ERROR_TYPE_OTHER = SelectOption(
    id="error_type_other", value="Other", color="brown", order=3
)
ALL_ERROR_TYPES = [
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    ERROR_TYPE_DATA_TYPE_MISMATCH,
    ERROR_TYPE_OTHER,
]


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
            grid_view,
            ImportExportConfig(include_permission_data=False),
            None,
            None,
            None,
        )
        empty_serialized_grid_view["id"] = 0
        exported_views = [empty_serialized_grid_view]

        unique_table_names = {item.table for item in self.items if item.table}
        unique_table_select_options = {
            name: SelectOption(
                id=f"table_{name}",
                value=name,
                color=random.choice(BASEROW_COLORS),  # nosec
                order=index + 1,
            )
            for index, name in enumerate(unique_table_names)
        }

        object_name_field = TextField(
            id="object_name",
            name="Object name",
            order=0,
            primary=True,
        )
        scope_field = SingleSelectField(id="scope", pk="scope", name="Scope", order=1)
        scope_field._prefetched_objects_cache = {"select_options": ALL_SCOPES}
        table_field = SingleSelectField(
            id="table", pk="error_type", name="Table", order=2
        )
        table_field._prefetched_objects_cache = {
            "select_options": unique_table_select_options.values()
        }
        error_field_type = SingleSelectField(
            id="error_type", pk="error_type", name="Error type", order=3
        )
        error_field_type._prefetched_objects_cache = {"select_options": ALL_ERROR_TYPES}
        message_field = LongTextField(id="message", name="Message", order=4)

        fields = [
            object_name_field,
            scope_field,
            table_field,
            error_field_type,
            message_field,
        ]
        exported_fields = [
            field_type_registry.get_by_model(field).export_serialized(field)
            for field in fields
        ]

        exported_rows = []
        for index, item in enumerate(self.items):
            table_select_option = unique_table_select_options.get(item.table, None)
            row = DatabaseExportSerializedStructure.row(
                id=index + 1,
                order=f"{index + 1}.00000000000000000000",
                created_on=None,
                updated_on=None,
            )
            row["field_object_name"] = item.object_name
            row["field_scope"] = item.scope.id
            row["field_table"] = table_select_option.id if table_select_option else None
            row["field_error_type"] = item.error_type.id
            row["field_message"] = item.message
            exported_rows.append(row)

        exported_table = DatabaseExportSerializedStructure.table(
            id=REPORT_TABLE_ID,
            name=REPORT_TABLE_NAME,
            order=order,
            fields=exported_fields,
            views=exported_views,
            rows=exported_rows,
            data_sync=None,
            field_rules=[],
        )

        return exported_table

    def append_items_to_exported_table(
        self, exported_database: dict, items: list
    ) -> None:
        """
        Appends new items to an existing exported table.

        :param exported_database: The exported database
        :param items: List of ImportReportFailedItem to append
        """

        if not items:
            return

        report_table = next(
            (
                table
                for table in exported_database["tables"]
                if table["id"] == REPORT_TABLE_ID
            ),
            None,
        )
        if not report_table:
            return

        current_row_count = len(report_table["rows"])
        table_select_options = {
            opt["value"]: opt for opt in report_table["fields"][2]["select_options"]
        }

        for index, item in enumerate(items, start=current_row_count + 1):
            table_select_option = table_select_options.get(item.table)
            row = DatabaseExportSerializedStructure.row(
                id=index,
                order=f"{index}.00000000000000000000",
                created_on=None,
                updated_on=None,
            )
            row["field_object_name"] = item.object_name
            row["field_scope"] = item.scope.id
            row["field_table"] = (
                table_select_option["id"] if table_select_option else None
            )
            row["field_error_type"] = item.error_type.id
            row["field_message"] = item.message
            report_table["rows"].append(row)
