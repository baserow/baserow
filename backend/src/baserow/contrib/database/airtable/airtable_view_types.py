from typing import Optional

from baserow.contrib.database.airtable.constants import (
    AIRTABLE_GALLERY_VIEW_COVER_CROP_TYPE,
)
from baserow.contrib.database.airtable.import_report import (
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_VIEW,
    AirtableImportReport,
)
from baserow.contrib.database.airtable.registry import AirtableViewType
from baserow.contrib.database.fields.field_types import FileFieldType
from baserow.contrib.database.views.models import (
    GalleryView,
    GalleryViewFieldOptions,
    GridView,
    GridViewFieldOptions,
)
from baserow.contrib.database.views.view_types import GalleryViewType, GridViewType
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


class GalleryAirtableViewType(AirtableViewType):
    type = "gallery"
    baserow_view_type = GalleryViewType.type

    def get_cover_column(
        self,
        field_mapping: dict,
        view: GalleryView,
        raw_airtable_table: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> Optional[str]:
        """
        Checks if the chosen coverColumnId is set, if the field exist, and if the
        field is compatible with the cover type Baserow. If all is True, it returns
        the referenced field id.
        """

        cover_column_id = get_value_at_path(
            raw_airtable_view_data, "metadata.gallery.coverColumnId", None
        )

        if not cover_column_id:
            return

        cover_column = field_mapping.get(cover_column_id, None)
        if cover_column is None:
            import_report.add_failed(
                view.name,
                SCOPE_VIEW,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'View "{view.name}" cover column with id '
                f'"{cover_column_id}" is not found.',
            )
            return

        if cover_column["baserow_field_type"].type != FileFieldType.type:
            import_report.add_failed(
                view.name,
                SCOPE_VIEW,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'View "{view.name}" cover column with id '
                f'"{cover_column_id}" is not a file field.',
            )
            return

        return cover_column_id

    def prepare_view_object(
        self,
        field_mapping,
        view: GalleryView,
        raw_airtable_table,
        raw_airtable_view,
        raw_airtable_view_data,
        config,
        import_report,
    ):
        cover_column_id = self.get_cover_column(
            field_mapping,
            view,
            raw_airtable_table,
            raw_airtable_view_data,
            import_report,
        )
        view.card_cover_image_field_id = cover_column_id

        cover_fit_type = get_value_at_path(
            raw_airtable_view_data, "metadata.gallery.coverFitType", None
        )

        if (
            cover_column_id
            and cover_fit_type
            and cover_fit_type != AIRTABLE_GALLERY_VIEW_COVER_CROP_TYPE
        ):
            import_report.add_failed(
                view.name,
                SCOPE_VIEW,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'View "{view.name}" cover fit type "{cover_fit_type}" is not '
                f'supported, so it defaulted to "crop"',
            )

        # Map the columnOrder entries to the matching `GalleryViewFieldOptions`,
        # and set that as `get_field_options`, so that it's correctly serialized
        # exported.
        field_options = []
        column_orders = raw_airtable_view_data.get("columnOrder", None) or []
        for index, column_order in enumerate(column_orders):
            if column_order["columnId"] not in field_mapping:
                continue

            field_options.append(
                GalleryViewFieldOptions(
                    id=f"{raw_airtable_view['id']}_columnOrder_{index}",
                    gallery_view_id=view.id,
                    field_id=column_order["columnId"],
                    hidden=not column_order.get("visibility", True),
                    order=index + 1,
                )
            )
        view.get_field_options = lambda *args, **kwargs: field_options

        return view
