from baserow.contrib.database.airtable.registry import AirtableViewType
from baserow.contrib.database.views.models import GridView, GridViewFieldOptions
from baserow.contrib.database.views.view_types import GridViewType
from baserow.core.utils import get_value_at_path


class GridAirtableViewType(AirtableViewType):
    type = "grid"
    baserow_view_type = GridViewType.type

    def prepare_view_object(
        self,
        field_mapping,
        view: GridView,
        raw_airtable_table,
        raw_airtable_view,
        raw_airtable_view_data,
        config,
        import_report,
    ):
        # Airtable doesn't have this option, and by default it is count.
        view.row_identifier_type = GridView.RowIdentifierTypes.count.value

        # Set the row height if the value size is available. Baserow doesn't support
        # `xlarge`, so we're falling back on `large`in that case.
        row_height_mapping = {v: v for v in GridView.RowHeightSizes.values}
        row_height_mapping["xlarge"] = GridView.RowHeightSizes.large.value
        row_height = get_value_at_path(
            raw_airtable_view_data, "metadata.grid.rowHeight"
        )
        view.row_height_size = row_height_mapping.get(
            row_height, GridView.RowHeightSizes.small.value
        )

        # Map the columnOrder entries to the matching `GridViewFieldOptions`,
        # and set that as `get_field_options`, so that it's correctly serialized
        # exported.
        field_options = []
        column_orders = raw_airtable_view_data.get("columnOrder", None) or []
        for index, column_order in enumerate(column_orders):
            if column_order["columnId"] not in field_mapping:
                continue

            field_options.append(
                GridViewFieldOptions(
                    id=f"{raw_airtable_view['id']}_columnOrder_{index}",
                    grid_view_id=view.id,
                    field_id=column_order["columnId"],
                    width=column_order.get("width", 200),
                    hidden=not column_order.get("visibility", True),
                    order=index + 1,
                )
            )
        view.get_field_options = lambda *args, **kwargs: field_options

        return view
