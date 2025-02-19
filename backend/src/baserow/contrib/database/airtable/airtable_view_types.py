from baserow.contrib.database.airtable.registry import AirtableViewType
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.utils import get_value_at_path


class GridAirtableViewType(AirtableViewType):
    type = "grid"
    baserow_view_type = GridViewType.type

    def prepare_view_object(
        self,
        view: GridView,
        raw_airtable_table,
        raw_airtable_view,
        raw_airtable_view_data,
        config,
        import_report,
    ):
        # Airtable doesn't have this option, and by default it is count .
        view.row_identifier_type = GridView.RowIdentifierTypes.count.value

        # Set the row height if the value size is available. Baserow doesn't support
        # `xlarge`, so we're falling back on `large`in that case.
        row_height_mapping = {v: v for v in GridView.RowHeightSizes.__members__.keys()}
        row_height_mapping["xlarge"] = "large"
        row_height = get_value_at_path(
            raw_airtable_view_data, "metadata.grid.rowHeight"
        )
        view.row_height_size = row_height_mapping.get(row_height, "small")

        return view
