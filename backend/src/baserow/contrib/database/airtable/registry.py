from typing import Any, Dict, List, Optional, Tuple, Union

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.constants import AIRTABLE_ASCENDING_MAP
from baserow.contrib.database.airtable.exceptions import AirtableSkipCellValue
from baserow.contrib.database.airtable.import_report import (
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_FIELD,
    SCOPE_VIEW_GROUP_BY,
    SCOPE_VIEW_SORT,
    AirtableImportReport,
)
from baserow.contrib.database.airtable.utils import get_airtable_column_name
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views.models import (
    SORT_ORDER_ASC,
    SORT_ORDER_DESC,
    View,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import ViewType, view_type_registry
from baserow.core.registry import Instance, Registry


class AirtableColumnType(Instance):
    def to_baserow_field(
        self,
        raw_airtable_table: dict,
        raw_airtable_column: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> Union[Field, None]:
        """
        Converts the raw Airtable column to a Baserow field object. It should be
        possible to pass this object directly into the FieldType::export_serialized
        method to convert it to the Baserow export format.

        :param raw_airtable_table: The raw Airtable table data related to the column.
        :param raw_airtable_column: The raw Airtable column values that must be
            converted.
        :param timezone: The main timezone used for date conversions if needed.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The Baserow field type related to the Airtable column. If None is
            provided, then the column is ignored in the conversion.
        """

        raise NotImplementedError("The `to_baserow_field` must be implemented.")

    def after_field_objects_prepared(
        self,
        field_mapping_per_table: Dict[str, Dict[str, Any]],
        baserow_field: Field,
        raw_airtable_column: dict,
    ):
        """
        Hook that is called after all field objects of all tables are prepared. This
        allows to do some post-processing on the fields in case they depend on each
        other.
        """

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        value: Any,
        files_to_download: Dict[str, str],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        """
        This method should convert a raw Airtable row value to a Baserow export row
        value. This method is only called if the Airtable field is compatible with a
        Baserow field type, this is determined by the
        `from_airtable_field_to_serialized` method.

        :param row_id_mapping: A mapping containing the table as key as the value is
            another mapping where the Airtable row id maps the Baserow row id.
        :param raw_airtable_table: The original Airtable table object.
        :param raw_airtable_row: The original row object.
        :param raw_airtable_column: A dict containing the raw Airtable column values.
        :param baserow_field: The Baserow field that the column has been converted to.
        :param value: The raw Airtable value that must be converted.
        :param files_to_download: A dict that contains all the user file URLs that must
            be downloaded. The key is the file name and the value the URL. Additional
            files can be added to this dict.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The converted value is Baserow export format.
        """

        return value

    def to_baserow_export_empty_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        files_to_download: Dict[str, str],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # By default, raise the `AirtableSkipCellValue` so that the value is not
        # included in the export.
        raise AirtableSkipCellValue

    def add_import_report_failed_if_default_is_provided(
        self,
        raw_airtable_table: dict,
        raw_airtable_column: dict,
        import_report: AirtableImportReport,
        to_human_readable_default=(lambda x: x),
    ):
        default = raw_airtable_column.get("default", "")
        if default:
            default = to_human_readable_default(default)
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the default value "
                f"{default} was dropped because that's not supported in Baserow.",
            )


class AirtableColumnTypeRegistry(Registry):
    name = "airtable_column"

    def from_airtable_column_to_serialized(
        self,
        raw_airtable_table: dict,
        raw_airtable_column: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> Union[Tuple[Field, AirtableColumnType], Tuple[None, None]]:
        """
        Tries to find a Baserow field that matches that raw Airtable column data. If
        None is returned, the column is not compatible with Baserow and must be ignored.

        :param raw_airtable_table: The raw Airtable table data related to the column.
        :param raw_airtable_column: The raw Airtable column data that must be imported.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The related Baserow field and AirtableColumnType that should be used
            for the conversion.
        """

        try:
            type_name = raw_airtable_column.get("type", "")
            airtable_column_type = self.get(type_name)
            baserow_field = airtable_column_type.to_baserow_field(
                raw_airtable_table, raw_airtable_column, config, import_report
            )

            if baserow_field is None:
                return None, None
            else:
                return baserow_field, airtable_column_type
        except self.does_not_exist_exception_class:
            return None, None


class AirtableViewType(Instance):
    baserow_view_type: Optional[str] = None

    def get_sorts(
        self,
        field_mapping: dict,
        view_type: ViewType,
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> List[ViewSort]:
        """
        Maps the sorts from the raw Airtable view data to a list of Baserow
        compatible ViewSort objects.
        """

        last_sorts_applied = raw_airtable_view_data.get("lastSortsApplied", None)

        if not view_type.can_sort or last_sorts_applied is None:
            return []

        sort_set = last_sorts_applied.get("sortSet", None) or []

        view_sorts = []
        for sort in sort_set:
            if sort["columnId"] not in field_mapping:
                column_name = get_airtable_column_name(
                    raw_airtable_table, sort["columnId"]
                )
                import_report.add_failed(
                    f'View "{raw_airtable_view["name"]}", Field ID "{column_name}"',
                    SCOPE_VIEW_SORT,
                    raw_airtable_table["name"],
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f'The sort on field "{column_name}" was ignored in view'
                    f' {raw_airtable_view["name"]} because the field is not imported.',
                )
                continue

            mapping_entry = field_mapping[sort["columnId"]]
            baserow_field_type = mapping_entry["baserow_field_type"]
            baserow_field = mapping_entry["baserow_field"]
            can_order_by = baserow_field_type.check_can_order_by(baserow_field)

            if not can_order_by:
                import_report.add_failed(
                    f'View "{raw_airtable_view["name"]}", Field "{baserow_field.name}"',
                    SCOPE_VIEW_SORT,
                    raw_airtable_table["name"],
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f'The sort on field "{baserow_field.name}" was ignored in view'
                    f' {raw_airtable_view["name"]} because it\'s not possible to '
                    f"order by that field type.",
                )
                continue

            view_sort = ViewSort(
                id=sort["id"],
                field_id=sort["columnId"],
                order=SORT_ORDER_ASC if sort["ascending"] else SORT_ORDER_DESC,
            )
            view_sorts.append(view_sort)

        return view_sorts

    def get_group_bys(
        self,
        field_mapping: dict,
        view_type: ViewType,
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> List[ViewGroupBy]:
        """
        Maps the group bys from the raw Airtable view data to a list of Baserow
        compatible ViewGroupBy objects.
        """

        group_levels = raw_airtable_view_data.get("groupLevels", None)

        if not view_type.can_sort or group_levels is None:
            return []

        view_group_by = []
        for group in group_levels:
            if group["columnId"] not in field_mapping:
                column_name = get_airtable_column_name(
                    raw_airtable_table, group["columnId"]
                )
                import_report.add_failed(
                    f'View "{raw_airtable_view["name"]}", Field ID "{column_name}"',
                    SCOPE_VIEW_GROUP_BY,
                    raw_airtable_table["name"],
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f'The group by on field "{column_name}" was ignored in view'
                    f' {raw_airtable_view["name"]} because the field was not imported.',
                )
                continue

            mapping_entry = field_mapping[group["columnId"]]
            baserow_field_type = mapping_entry["baserow_field_type"]
            baserow_field = mapping_entry["baserow_field"]
            can_order_by = baserow_field_type.check_can_group_by(baserow_field)

            if not can_order_by:
                import_report.add_failed(
                    f'View "{raw_airtable_view["name"]}", Field "{baserow_field.name}"',
                    SCOPE_VIEW_GROUP_BY,
                    raw_airtable_table["name"],
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f'The group by on field "{baserow_field.name}" was ignored in view {raw_airtable_view["name"]} because it\'s not possible to group by that field type.',
                )
                continue

            ascending = AIRTABLE_ASCENDING_MAP.get(group["order"], None)

            if ascending is None:
                import_report.add_failed(
                    f'View "{raw_airtable_view["name"]}", Field "{baserow_field.name}"',
                    SCOPE_VIEW_GROUP_BY,
                    raw_airtable_table["name"],
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f'The group by on field "{baserow_field.name}" was ignored in view {raw_airtable_view["name"]} because the order {group["order"]} is incompatible.',
                )
                continue

            view_group = ViewGroupBy(
                id=group["id"],
                field_id=group["columnId"],
                order=SORT_ORDER_ASC if ascending else SORT_ORDER_DESC,
            )
            view_group_by.append(view_group)

        return view_group_by

    def to_serialized_baserow_view(
        self,
        field_mapping,
        raw_airtable_table,
        raw_airtable_view,
        raw_airtable_view_data,
        config,
        import_report,
    ):
        if self.baserow_view_type is None:
            raise NotImplementedError(
                "The `baserow_view_type` must be implemented for the AirtableViewType."
            )

        view_type = view_type_registry.get(self.baserow_view_type)
        view = view_type.model_class(
            id=raw_airtable_view["id"],
            pk=raw_airtable_view["id"],
            name=raw_airtable_view["name"],
            order=raw_airtable_table["viewOrder"].index(raw_airtable_view["id"]) + 1,
        )

        sorts = self.get_sorts(
            field_mapping,
            view_type,
            raw_airtable_table,
            raw_airtable_view,
            raw_airtable_view_data,
            import_report,
        )
        group_bys = self.get_group_bys(
            field_mapping,
            view_type,
            raw_airtable_table,
            raw_airtable_view,
            raw_airtable_view_data,
            import_report,
        )

        view.get_field_options = lambda *args, **kwargs: []
        view._prefetched_objects_cache = {
            "viewfilter_set": [],
            "filter_groups": [],
            "viewsort_set": sorts,
            "viewgroupby_set": group_bys,
            "viewdecoration_set": [],
        }
        view = self.prepare_view_object(
            field_mapping,
            view,
            raw_airtable_table,
            raw_airtable_view,
            raw_airtable_view_data,
            config,
            import_report,
        )
        serialized = view_type.export_serialized(view)

        return serialized

    def prepare_view_object(
        self,
        field_mapping: dict,
        view: View,
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> Union[dict, None]:
        """
        Prepares the given view object before it's passed into the view type specific
        `export_serialized` method. This should be used to set any properties that
        are needed for the view specific export operations.

        Note that the common properties like name, filters, sorts, etc are added by
        default depending on the Baserow view support for it.

        :param field_mapping: @TODO
        :param view: The view object that must be prepared.
        :param raw_airtable_table: The raw Airtable table data related to the column.
        :param raw_airtable_view: The raw Airtable view values that must be
            converted, this contains the name, for example.
        :param raw_airtable_view_data: The Airtable view data. This contains the
            filters, sorts, etc.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The Baserow view type related to the Airtable column. If None is
            provided, then the view is ignored in the conversion.
        """

        raise NotImplementedError(
            "The `to_serialized_baserow_view` must be implemented."
        )


class AirtableViewTypeRegistry(Registry):
    name = "airtable_view"

    def from_airtable_view_to_serialized(
        self,
        field_mapping: dict,
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ) -> dict:
        """
        Tries to find a Baserow view that matches that raw Airtable view data. If
        None is returned, the view is not compatible with Baserow and must be ignored.

        :param field_mapping: A dict containing all the imported fields.
        :param raw_airtable_table: The raw Airtable table data related to the column.
        :param raw_airtable_view: The raw Airtable column data that must be imported.
        :param raw_airtable_view_data: The raw Airtable view data containing filters,
            sorts, etc.
        :param config: Additional configuration related to the import.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :return: The related Baserow view and AirtableViewType that should be used
            for the conversion.
        """

        try:
            type_name = raw_airtable_view.get("type", "")
            airtable_view_type = self.get(type_name)
            serialized_view = airtable_view_type.to_serialized_baserow_view(
                field_mapping,
                raw_airtable_table,
                raw_airtable_view,
                raw_airtable_view_data,
                config,
                import_report,
            )

            return serialized_view
        except self.does_not_exist_exception_class:
            # Returning `None` because it's okay to not important the incompatible
            # views. It will be added to the `import_later` from the handler.
            return None


# A default airtable column type registry is created here, this is the one that is used
# throughout the whole Baserow application to add a new airtable column type.
airtable_column_type_registry = AirtableColumnTypeRegistry()
airtable_view_type_registry = AirtableViewTypeRegistry()
