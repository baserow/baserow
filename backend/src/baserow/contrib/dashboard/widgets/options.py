"""Resolve saved dropdown formulas against tables used by this dashboard."""

import json
import re
from contextlib import closing
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from baserow.contrib.dashboard.data_sources.records import DashboardTableRecordsHandler
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.table.service import TableService
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowTableServiceType,
)
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaException, resolve_formula
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import (
    DataProviderType,
    DataProviderTypeRegistry,
    formula_runtime_function_registry,
)
from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.handler import CoreHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.utils import get_value_at_path


class DashboardTableDataProviderType(DataProviderType):
    type = "table"

    def is_valid(self, path):
        if not (
            len(path) >= 3
            and re.fullmatch(r"[1-9][0-9]{0,18}", path[0])
            and (path[1] == "*" or re.fullmatch(r"[0-9]{1,9}", path[1]))
            and (path[2] == "id" or re.fullmatch(r"field_[1-9][0-9]{0,18}", path[2]))
        ):
            raise BaserowFormulaSyntaxError("Choose a field from a dashboard table.")
        return True

    def get_data_chunk(self, context, path):
        self.is_valid(path)
        table_id, selector, field_name, *rest = path
        key = tuple(path)
        if key in context.cache:
            return context.cache[key]
        table = context.get_table(int(table_id))
        handler = DashboardTableRecordsHandler()
        scalar_values = (
            handler.iter_scalar_field_values(table, field_name)
            if selector == "*" and not rest
            else None
        )
        values = []
        if scalar_values is not None:
            with closing(scalar_values) as iterator:
                for value in iterator:
                    context.consume(value)
                    values.append(value)
        else:
            with closing(
                handler.iter_records(
                    table,
                    field_name,
                    row_index=int(selector) if selector != "*" else None,
                )
            ) as iterator:
                for record in iterator:
                    context.consume(record)
                    values.append(get_value_at_path(record, [field_name, *rest]))
        result = values if selector == "*" else next(iter(values), None)
        context.cache[key] = result
        return result

    def import_path(self, path, id_mapping, **kwargs):
        from baserow.contrib.integrations.local_baserow.service_types import (
            LocalBaserowListRowsUserServiceType,
        )

        self.is_valid(path)
        table_id, *rest = path
        return [
            str(id_mapping.get("database_tables", {}).get(int(table_id), table_id)),
            *LocalBaserowListRowsUserServiceType().import_path(rest, id_mapping),
        ]


dashboard_options_data_provider_registry = DataProviderTypeRegistry()
dashboard_options_data_provider_registry.register(DashboardTableDataProviderType())


class DashboardOptionsContext(RuntimeFormulaContext):
    data_provider_registry = dashboard_options_data_provider_registry
    max_values = 10000
    max_bytes = 1024 * 1024

    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard
        self.cache = {}
        self.count = self.size = 0

    def consume(self, value):
        self.count += 1
        self.size += len(json.dumps(value, default=str).encode())
        if self.count > self.max_values or self.size > self.max_bytes:
            raise InvalidRuntimeFormula(
                "The filter options are too large. Choose a smaller source."
            )

    def get_table(self, table_id):
        # The integration grants access, just as it does for widget dispatch.
        # A saved formula cannot read arbitrary tables or supply an actor.
        for widget in WidgetHandler().get_widgets(self.dashboard):
            widget_type = widget.get_type()
            if not widget_type.is_display_widget:
                continue
            source = widget_type.get_data_source(widget)
            if not source or not source.service_id or source.trashed:
                continue
            service = source.service.specific
            if (
                not isinstance(service.get_type(), LocalBaserowTableServiceType)
                or service.table_id != table_id
            ):
                continue
            if not service.integration_id:
                continue
            user = service.get_type().get_acting_user(service, self)
            table = TableService().get_table(user, table_id)
            CoreHandler().check_permissions(
                user,
                ListRowsDatabaseTableOperationType.type,
                workspace=table.database.workspace,
                context=table,
            )
            return table
        raise InvalidRuntimeFormula("The table is not used by this dashboard.")


class DashboardWidgetOptionsService:
    def get_options(self, widget):
        if widget.get_type().type != "text_filter" or widget.mode != "dropdown":
            raise ValidationError("This widget is not a dropdown filter.")
        context = DashboardOptionsContext(widget.dashboard)
        try:
            result = resolve_formula(
                widget.options, formula_runtime_function_registry, context
            )
            candidates = (
                [value.strip() for value in result.split(",")]
                if isinstance(result, str)
                else result
            )
            if candidates is None:
                candidates = []
            if not isinstance(candidates, list):
                raise InvalidRuntimeFormula(
                    "Filter values must resolve to text or a list."
                )
            values = {}
            for value in candidates:
                if value is None:
                    continue
                if not isinstance(value, (str, int, float, Decimal, bool)):
                    raise InvalidRuntimeFormula(
                        "Choose a field containing individual values."
                    )
                value = str(value)
                if value.strip():
                    values.setdefault(value, None)
            # Check resolved output as well as records read during evaluation.
            context.count = context.size = 0
            for value in values:
                context.consume(value)
            return list(values)
        except (
            BaserowFormulaException,
            InstanceTypeDoesNotExist,
            RecursionError,
            ServiceImproperlyConfiguredDispatchException,
        ) as exc:
            raise ValidationError(
                "The filter values could not be resolved. Check the selected source or formula."
            ) from exc
