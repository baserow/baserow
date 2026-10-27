import re
from contextlib import closing
from typing import TYPE_CHECKING

from baserow.contrib.dashboard.filters.models import DashboardFilter
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.utils import get_value_at_path

if TYPE_CHECKING:
    from baserow.contrib.dashboard.filters.option_context import (
        DashboardFilterOptionsContext,
    )


class DashboardFilterDataProviderType(DataProviderType):
    type = "dashboard_filter"

    def is_valid(self, path):
        if not (
            1 <= len(path) <= 2
            and re.fullmatch(r"[1-9][0-9]*", path[0])
            and (len(path) == 1 or path[1] == "*" or re.fullmatch(r"[0-9]+", path[1]))
        ):
            raise BaserowFormulaSyntaxError(
                "The dashboard filter reference is invalid."
            )

    def get_data_chunk(self, dispatch_context, path):
        self.is_valid(path)
        configuration = self.get_configuration(dispatch_context, path[0])
        if configuration is None:
            return None

        values = configuration.values
        multiple = (
            configuration.mode == DashboardFilter.Mode.DROPDOWN
            and configuration.multiple
        )
        if not multiple:
            values = values[:1]
        if configuration.mode == DashboardFilter.Mode.INPUT:
            values = [value.strip() for value in values]
        # Explicit selectors retain their array semantics across format changes.
        # Bare references keep the current control's scalar/array formula type.
        if len(path) > 1:
            return get_value_at_path(values, path[1:])
        return values if multiple else next(iter(values), "")

    def get_configuration(self, dispatch_context, filter_id):
        if dispatch_context.dashboard is None:
            raise InvalidRuntimeFormula("The dashboard filter reference is invalid.")

        cache_key = ("dashboard_filters", dispatch_context.dashboard.id)
        if cache_key not in dispatch_context.cache:
            dispatch_context.cache[cache_key] = {
                str(item.id): item
                for item in DashboardFilter.objects.filter(
                    dashboard=dispatch_context.dashboard
                )
            }
        configuration = dispatch_context.cache[cache_key].get(filter_id)
        if configuration is None:
            if (
                DashboardFilter.objects_and_trash.filter(id=filter_id)
                .exclude(dashboard=dispatch_context.dashboard)
                .exists()
            ):
                raise InvalidRuntimeFormula(
                    "The dashboard filter belongs to another dashboard."
                )
            # A removed control has no value, just like an unselected control.
            # Keep its source formula intact so restoring the control reconnects it.
            return None

        return configuration

    def import_path(self, path, id_mapping, **kwargs):
        filter_id, *rest = path
        mapped_id = id_mapping.get("dashboard_filters", {}).get(
            int(filter_id), filter_id
        )
        return [str(mapped_id), *rest]


class DashboardTableDataProviderType(DataProviderType):
    type = "table"

    def is_valid(self, path):
        if not (
            path
            and re.fullmatch(r"[1-9][0-9]*", path[0])
            and (len(path) == 1 or path[1] == "*" or re.fullmatch(r"[0-9]+", path[1]))
            and (
                len(path) < 3
                or path[2] == "id"
                or re.fullmatch(r"field_[1-9][0-9]*", path[2])
            )
        ):
            raise BaserowFormulaSyntaxError("The table reference is invalid.")

    def get_data_chunk(
        self, dispatch_context: "DashboardFilterOptionsContext", path: list[str]
    ):
        from baserow.contrib.dashboard.data_sources.records import (
            DashboardTableRecordsHandler,
            DashboardTableRecordsService,
        )

        self.is_valid(path)
        if dispatch_context.dashboard is None:
            raise InvalidRuntimeFormula("The table reference is invalid.")
        table_id = int(path[0])
        field_name = path[2] if len(path) > 2 else None
        row_index = int(path[1]) if len(path) > 1 and path[1].isdigit() else None
        cache_key = ("dashboard_table_records", table_id, field_name, row_index)
        if cache_key not in dispatch_context.cache:
            table = DashboardTableRecordsService().get_table(
                dispatch_context.request.user, dispatch_context.dashboard, table_id
            )
            dispatch_context.table_ids_read.add(table_id)
            records = []
            with closing(
                DashboardTableRecordsHandler().iter_records(
                    table, field_name, row_index=row_index
                )
            ) as record_iterator:
                for record in record_iterator:
                    dispatch_context.consume_record(record)
                    records.append(record)
            dispatch_context.cache[cache_key] = records
        if row_index is not None:
            record = next(iter(dispatch_context.cache[cache_key]), None)
            return get_value_at_path(record, path[2:])
        records = dispatch_context.cache[cache_key]
        if len(path) > 1 and path[1] == "*":
            # Preserve row positions when formulas project multiple fields.
            return [get_value_at_path(record, path[2:]) for record in records]
        return get_value_at_path(records, path[1:])

    def import_path(self, path, id_mapping, **kwargs):
        from baserow.contrib.integrations.local_baserow.service_types import (
            LocalBaserowListRowsUserServiceType,
        )

        table_id, *rest = path
        mapped_id = id_mapping.get("database_tables", {}).get(int(table_id), table_id)
        return [
            str(mapped_id),
            *LocalBaserowListRowsUserServiceType().import_path(rest, id_mapping),
        ]


dashboard_data_provider_type_registry = DataProviderTypeRegistry()
dashboard_data_provider_type_registry.register(DashboardFilterDataProviderType())

# Table projections are available only while evaluating option formulas.
dashboard_filter_options_data_provider_type_registry = DataProviderTypeRegistry()
dashboard_filter_options_data_provider_type_registry.register(
    DashboardTableDataProviderType()
)

# Copy/import remaps both kinds of formula without granting runtime capabilities.
dashboard_formula_import_data_provider_type_registry = DataProviderTypeRegistry()
dashboard_formula_import_data_provider_type_registry.register(
    DashboardFilterDataProviderType()
)
dashboard_formula_import_data_provider_type_registry.register(
    DashboardTableDataProviderType()
)
