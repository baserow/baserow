from contextlib import closing

from django.core.exceptions import ValidationError

from baserow.contrib.dashboard.data_providers import DashboardTableDataProviderType
from baserow.contrib.dashboard.data_sources.records import (
    DashboardTableRecordsHandler,
    DashboardTableRecordsService,
)
from baserow.contrib.dashboard.filters.option_context import (
    DashboardFilterOptionsContext,
)
from baserow.contrib.dashboard.filters.option_snapshots import (
    DashboardFilterOptionsSnapshot,
)
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.contrib.dashboard.formula_references import get_direct_reference_path
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormulaException,
    resolve_formula,
)
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.validator import ensure_array
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

MAX_OPTION_FORMULA_RECORDS = 10_000
MAX_OPTION_FORMULA_BYTES = 10 * 1024 * 1024


def get_table_field_path(formula):
    """Recognize a field projection without changing calculated formula semantics."""

    path = get_direct_reference_path(formula, DashboardTableDataProviderType())
    if path is None or len(path) != 3 or path[1] != "*":
        return None
    return int(path[0]), path[2]


class DashboardFilterOptionsService:
    def get_options(
        self, user, filter_id, request, *, after=None, limit=50, selected=None
    ):
        configuration = DashboardFilterService().get_filter(user, filter_id)
        selected = selected or []
        context = DashboardFilterOptionsContext(
            request,
            dashboard=configuration.dashboard,
            max_records=MAX_OPTION_FORMULA_RECORDS,
            max_bytes=MAX_OPTION_FORMULA_BYTES,
        )
        snapshot = DashboardFilterOptionsSnapshot(user, configuration)

        def validate_tables(table_ids):
            for table_id in table_ids:
                DashboardTableRecordsService().get_table(
                    user, configuration.dashboard, table_id
                )

        def get_values():
            path = get_table_field_path(configuration.formula_value)
            if path is not None:
                table_id, field_name = path
                table = DashboardTableRecordsService().get_table(
                    user, configuration.dashboard, table_id
                )
                context.table_ids_read.add(table_id)
                handler = DashboardTableRecordsHandler()
                scalar_values = handler.iter_scalar_field_values(table, field_name)
                if scalar_values is not None:
                    with closing(scalar_values):
                        yield from scalar_values
                else:
                    with closing(handler.iter_records(table, field_name)) as records:
                        for record in records:
                            yield record[field_name]
            else:
                yield from ensure_array(
                    resolve_formula(
                        configuration.formula_value,
                        formula_runtime_function_registry,
                        context,
                    )
                )

        try:
            cursor = (
                snapshot.create(get_values, context.table_ids_read)
                if after is None
                else after
            )
            return snapshot.page(
                cursor,
                limit=limit,
                selected=selected,
                validate_tables=validate_tables,
            )
        except (
            BaserowFormulaException,
            ValidationError,
            InstanceTypeDoesNotExist,
        ) as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                "The option formula could not be resolved."
            ) from exc
