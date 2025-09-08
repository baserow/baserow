from typing import Any, Dict, List, Optional, Tuple, Union

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.constants import (
    AIRTABLE_ASCENDING_MAP,
    AIRTABLE_BASEROW_COLOR_MAPPING,
)
from baserow.contrib.database.airtable.exceptions import (
    AirtableSkipCellValue,
    AirtableSkipFilter,
)
from baserow.contrib.database.airtable.import_report import (
    ERROR_TYPE_DATA_TYPE_MISMATCH,
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_FIELD,
    SCOPE_VIEW,
    SCOPE_VIEW_COLOR,
    SCOPE_VIEW_FILTER,
    SCOPE_VIEW_GROUP_BY,
    SCOPE_VIEW_SORT,
    AirtableImportReport,
)
from baserow.contrib.database.airtable.models import DownloadFile
from baserow.contrib.database.airtable.utils import (
    get_airtable_column_name,
    unknown_value_to_human_readable,
)
from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    FILTER_TYPE_OR,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views.models import (
    DEFAULT_SORT_TYPE_KEY,
    SORT_ORDER_ASC,
    SORT_ORDER_DESC,
    View,
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import (
    ViewFilterType,
    ViewType,
    view_type_registry,
)
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
        files_to_download: Dict[str, DownloadFile],
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
        files_to_download: Dict[str, DownloadFile],
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
            can_order_by = baserow_field_type.check_can_order_by(
                baserow_field, DEFAULT_SORT_TYPE_KEY
            )

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
            can_order_by = baserow_field_type.check_can_group_by(
                baserow_field, DEFAULT_SORT_TYPE_KEY
            )

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

    def get_filter(
        self,
        field_mapping: dict,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_view: dict,
        raw_airtable_table: dict,
        import_report: AirtableImportReport,
        filter_object: dict,
        parent_group: Optional[ViewFilterGroup] = None,
    ):
        """
        This method converts a raw airtable filter object into a Baserow filter object
        that's ready for the export system.
        """

        # If it's not a group, then it's an individual filter, and it must be
        # parsed accordingly.
        if filter_object["columnId"] not in field_mapping:
            column_name = get_airtable_column_name(
                raw_airtable_table, filter_object["columnId"]
            )
            filter_value = unknown_value_to_human_readable(filter_object["value"])
            import_report.add_failed(
                f'View "{raw_airtable_view["name"]}", Field ID "{column_name}"',
                SCOPE_VIEW_FILTER,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'The "{filter_object["operator"]}" filter with value '
                f'"{filter_value}" on field "{column_name}" was ignored '
                f'in view {raw_airtable_view["name"]} because the field was not '
                f"imported.",
            )
            return None

        mapping_entry = field_mapping[filter_object["columnId"]]
        baserow_field_type = mapping_entry["baserow_field_type"]
        baserow_field = mapping_entry["baserow_field"]
        raw_airtable_column = mapping_entry["raw_airtable_column"]
        can_filter_by = baserow_field_type.check_can_filter_by(baserow_field)

        if not can_filter_by:
            filter_value = unknown_value_to_human_readable(filter_object["value"])
            import_report.add_failed(
                f'View "{raw_airtable_view["name"]}", Field "{baserow_field.name}"',
                SCOPE_VIEW_FILTER,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'The "{filter_object["operator"]}" filter with value '
                f'"{filter_value}" on field "{baserow_field.name}" was '
                f'ignored in view {raw_airtable_view["name"]} because it\'s not '
                f"possible to filter by that field type.",
            )
            return None

        try:
            filter_operator = airtable_filter_operator_registry.get(
                filter_object["operator"]
            )
            filter_type, value = filter_operator.to_baserow_filter_and_value(
                row_id_mapping,
                raw_airtable_table,
                raw_airtable_column,
                baserow_field,
                import_report,
                filter_object["value"],
            )

            if not filter_type.field_is_compatible(baserow_field):
                raise AirtableSkipFilter
        except (
            airtable_filter_operator_registry.does_not_exist_exception_class,
            # If the `AirtableSkipFilter` exception is raised, then the Airtable
            # filter existing, but is not compatible with the Baserow filters. This
            # can be raised in the `to_baserow_filter_and_value`, but also if it
            # appears to not be compatible afterward.
            AirtableSkipFilter,
        ):
            filter_value = unknown_value_to_human_readable(filter_object["value"])
            import_report.add_failed(
                f'View "{raw_airtable_view["name"]}", Field "{baserow_field.name}"',
                SCOPE_VIEW_FILTER,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'The "{filter_object["operator"]}" filter with value '
                f'"{filter_value}" on field "{baserow_field.name}" was '
                f'ignored in view {raw_airtable_view["name"]} because not no '
                f"compatible filter exists.",
            )
            return None

        return ViewFilter(
            id=filter_object["id"],
            type=filter_type.type,
            value=value,
            field_id=filter_object["columnId"],
            view_id=raw_airtable_view["id"],
            group_id=parent_group.id if parent_group else None,
        )

    def get_filters(
        self,
        field_mapping: dict,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_view: dict,
        raw_airtable_table: dict,
        import_report: AirtableImportReport,
        filter_object: dict,
        filter_groups: Optional[List[ViewFilterGroup]] = None,
        parent_group: Optional[ViewFilterGroup] = None,
    ) -> Union[List[ViewFilter], List[ViewFilterGroup]]:
        """
        Recursive method that either loops over the filters in the `filter_object`, and
        converts it to two flat lists containing the Baserow ViewFilter and
        ViewFilterGroup objects.
        """

        if filter_groups is None:
            filter_groups = []

        filters = []
        conjunction = filter_object.get("conjunction", None)
        filter_set = filter_object.get("filterSet", None)
        column_id = filter_object.get("columnId", None)

        if conjunction and filter_set:
            # The filter_object is a nested structure, where if the `conjunction` and
            # `filterSet` are in the object, it means that it's a filter group.
            view_group = ViewFilterGroup(
                # Specifically keep the id `None` for the root group because that
                # doesn't exist in Baserow.
                id=filter_object.get("id", None),
                parent_group=parent_group,
                filter_type=FILTER_TYPE_OR if conjunction == "or" else FILTER_TYPE_AND,
                view_id=raw_airtable_view["id"],
            )

            if view_group not in filter_groups:
                filter_groups.append(view_group)

            for child_filter in filter_set:
                child_filters, _ = self.get_filters(
                    field_mapping,
                    row_id_mapping,
                    raw_airtable_view,
                    raw_airtable_table,
                    import_report,
                    child_filter,
                    filter_groups,
                    view_group,
                )
                filters.extend(child_filters)

            return filters, filter_groups
        elif column_id:
            baserow_filter = self.get_filter(
                field_mapping,
                row_id_mapping,
                raw_airtable_view,
                raw_airtable_table,
                import_report,
                filter_object,
                parent_group,
            )

            if baserow_filter is None:
                return [], []
            else:
                return [baserow_filter], []

        return [], []

    def get_select_column_decoration(
        self,
        field_mapping: dict,
        view_type: ViewType,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> Optional[ViewDecoration]:
        color_config = raw_airtable_view_data["colorConfig"]
        select_column_id = color_config["selectColumnId"]

        if select_column_id not in field_mapping:
            column_name = get_airtable_column_name(raw_airtable_table, select_column_id)
            import_report.add_failed(
                raw_airtable_view["name"],
                SCOPE_VIEW_COLOR,
                raw_airtable_table["name"],
                ERROR_TYPE_DATA_TYPE_MISMATCH,
                f'The select field coloring was ignored in {raw_airtable_view["name"]} '
                f"because {column_name} does not exist.",
            )
            return None

        return ViewDecoration(
            id=f"{raw_airtable_view['id']}_decoration",
            view_id=raw_airtable_view["id"],
            type="left_border_color",
            value_provider_type="single_select_color",
            value_provider_conf={"field_id": select_column_id},
            order=1,
        )

    def get_color_definitions_decoration(
        self,
        field_mapping: dict,
        view_type: ViewType,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> Optional[ViewDecoration]:
        color_config = raw_airtable_view_data["colorConfig"]
        color_definitions = color_config["colorDefinitions"]
        default_color = AIRTABLE_BASEROW_COLOR_MAPPING.get(
            color_config.get("defaultColor", ""),
            "",
        )
        baserow_colors = []

        for color_definition in color_definitions:
            filters, filter_groups = self.get_filters(
                field_mapping,
                row_id_mapping,
                raw_airtable_view,
                raw_airtable_table,
                import_report,
                color_definition,
            )
            # Pop the first group because that shouldn't be in Baserow, and the type is
            # defined on the view.
            if len(filter_groups) > 0:
                root_group = filter_groups.pop(0)
            color = AIRTABLE_BASEROW_COLOR_MAPPING.get(
                color_definition.get("color", ""),
                "blue",
            )
            baserow_colors.append(
                {
                    "filter_groups": [
                        {
                            "id": filter_group.id,
                            "filter_type": filter_group.filter_type,
                            "parent_group": (
                                None
                                if filter_group.parent_group_id == root_group.id
                                else filter_group.parent_group_id
                            ),
                        }
                        for filter_group in filter_groups
                    ],
                    "filters": [
                        {
                            "id": filter_object.id,
                            "type": filter_object.type,
                            "field": filter_object.field_id,
                            "group": (
                                None
                                if filter_object.group_id == root_group.id
                                else filter_object.group_id
                            ),
                            "value": filter_object.value,
                        }
                        for filter_object in filters
                    ],
                    "operator": root_group.filter_type,
                    "color": color,
                }
            )

        if default_color != "":
            baserow_colors.append(
                {
                    "filter_groups": [],
                    "filters": [],
                    "operator": "AND",
                    "color": default_color,
                }
            )

        return ViewDecoration(
            id=f"{raw_airtable_view['id']}_decoration",
            view_id=raw_airtable_view["id"],
            type="left_border_color",
            value_provider_type="conditional_color",
            value_provider_conf={"colors": baserow_colors},
            order=1,
        )

    def get_decorations(
        self,
        field_mapping: dict,
        view_type: ViewType,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_view: dict,
        raw_airtable_view_data: dict,
        import_report: AirtableImportReport,
    ) -> List[ViewDecoration]:
        """
        Converts the raw Airtable color config into matching Baserow view decorations.
        """

        color_config = raw_airtable_view_data.get("colorConfig", None)

        if not view_type.can_decorate or color_config is None:
            return []

        color_config_type = color_config.get("type", "")
        decoration = None

        if color_config_type == "selectColumn":
            decoration = self.get_select_column_decoration(
                field_mapping,
                view_type,
                row_id_mapping,
                raw_airtable_table,
                raw_airtable_view,
                raw_airtable_view_data,
                import_report,
            )
        elif color_config_type == "colorDefinitions":
            decoration = self.get_color_definitions_decoration(
                field_mapping,
                view_type,
                row_id_mapping,
                raw_airtable_table,
                raw_airtable_view,
                raw_airtable_view_data,
                import_report,
            )

        if decoration:
            return [decoration]
        else:
            return []

    def _check_personal_or_locked(
        self,
        view_name: str,
        raw_airtable_view: dict,
        raw_airtable_table: dict,
        import_report: AirtableImportReport,
    ) -> str:
        if raw_airtable_view.get("personalForUserId", ""):
            import_report.add_failed(
                view_name,
                SCOPE_VIEW,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'View "{view_name}" is personal, but was made collaborative because '
                f"it can't be linked to a user. (Personal) was added to the name.",
            )
            view_name += " (Personal)"

        if raw_airtable_view.get("lock", None):
            import_report.add_failed(
                view_name,
                SCOPE_VIEW,
                raw_airtable_table["name"],
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f'View "{view_name}" is locked, but was made collaborative because '
                f"it Baserow does not support this yet.",
            )

        return view_name

    def to_serialized_baserow_view(
        self,
        field_mapping,
        row_id_mapping,
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

        view_id = raw_airtable_view["id"]
        view_name = raw_airtable_view["name"]
        view_name = self._check_personal_or_locked(
            view_name, raw_airtable_view, raw_airtable_table, import_report
        )

        # Extract the ordered views from the sections and put them in a flat list so
        # that we can find the order for the Baserow view.
        flattened_view_order = []
        for view in raw_airtable_table["viewOrder"]:
            if view in raw_airtable_table["viewSectionsById"]:
                section = raw_airtable_table["viewSectionsById"][view]
                section_views = section["viewOrder"]
                flattened_view_order.extend(section_views)
                # Baserow doesn't support sections, but we can prepend the name of the
                # section.
                if view_id in section_views:
                    view_name = f"{section['name']} / {view_name}"
            else:
                flattened_view_order.append(view)

        view_type = view_type_registry.get(self.baserow_view_type)
        view = view_type.model_class(
            id=raw_airtable_view["id"],
            pk=raw_airtable_view["id"],
            name=view_name,
            order=flattened_view_order.index(raw_airtable_view["id"]) + 1,
        )

        filters_object = raw_airtable_view_data.get("filters", None)
        filters = []
        filter_groups = []
        if view_type.can_filter and filters_object is not None:
            filters, filter_groups = self.get_filters(
                field_mapping,
                row_id_mapping,
                raw_airtable_view,
                raw_airtable_table,
                import_report,
                filters_object,
            )
            # Pop the first group because that shouldn't be in Baserow, and the type is
            # defined on the view.
            if len(filter_groups) > 0:
                view.filter_type = filter_groups.pop(0).filter_type

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
        decorations = self.get_decorations(
            field_mapping,
            view_type,
            row_id_mapping,
            raw_airtable_table,
            raw_airtable_view,
            raw_airtable_view_data,
            import_report,
        )

        view.get_field_options = lambda *args, **kwargs: []
        view._prefetched_objects_cache = {
            "viewfilter_set": filters,
            "filter_groups": filter_groups,
            "viewsort_set": sorts,
            "viewgroupby_set": group_bys,
            "viewdecoration_set": decorations,
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
        serialized = view_type.export_serialized(view, config)

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

        :param field_mapping: A dict containing all the imported fields.
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
        row_id_mapping: Dict[str, Dict[str, int]],
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
        :param row_id_mapping: A dict mapping the Airable row IDs to Baserow row IDs
            per table ID.
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
                row_id_mapping,
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


class AirtableFilterOperator(Instance):
    def to_baserow_filter_and_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        raw_airtable_table: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        import_report: AirtableImportReport,
        value: str,
    ) -> Union[ViewFilterType, str]:
        """
        Converts the given Airtable value into the matching Baserow filter type and
        correct value.

        :param row_id_mapping: A dict mapping the Airable row IDs to Baserow row IDs
            per table ID.
        :param raw_airtable_table: The raw Airtable table data related to the filter.
        :param raw_airtable_column: The raw Airtable column data related to the filter.
        :param baserow_field: The Baserow field related to the filter.
        :param import_report: Used to collect what wasn't imported to report to the
            user.
        :param value: The value that must be converted.
        :raises AirtableSkipFilter: If no compatible Baserow filter can be found.
        :return: The matching Baserow filter type and value.
        """

        raise NotImplementedError(
            f"The `to_baserow_filter` must be implemented for {self.type}."
        )


class AirtableFilterOperatorRegistry(Registry):
    name = "airtable_filter_operator"


# A default airtable column type registry is created here, this is the one that is used
# throughout the whole Baserow application to add a new airtable column type.
airtable_column_type_registry = AirtableColumnTypeRegistry()
airtable_view_type_registry = AirtableViewTypeRegistry()
airtable_filter_operator_registry = AirtableFilterOperatorRegistry()
