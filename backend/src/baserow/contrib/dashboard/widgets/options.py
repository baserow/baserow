"""Resolve dropdown formulas against dashboard data source metadata."""

import json
import re
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
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
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.utils import get_value_at_path


class DashboardDataSourceContextDataProviderType(DataProviderType):
    type = "data_source_context"

    def is_valid(self, path):
        if len(path) < 2 or not re.fullmatch(r"[1-9][0-9]{0,18}", path[0]):
            raise BaserowFormulaSyntaxError(
                "Choose dashboard data source context data."
            )
        return True

    def get_data_chunk(self, context, path):
        """Resolve server-owned metadata only for sources in this dashboard."""
        self.is_valid(path)
        source_id, *rest = path
        if source_id not in context.cache:
            source = (
                DashboardDataSource.objects.filter(
                    id=int(source_id),
                    dashboard=context.dashboard,
                    trashed=False,
                    service__isnull=False,
                )
                .select_related("service")
                .first()
            )
            if source is None:
                raise InvalidRuntimeFormula("The dashboard data source does not exist.")
            service = source.service.specific
            context.cache[source_id] = service.get_type().get_context_data(service)
        return get_value_at_path(context.cache[source_id], rest)

    def import_path(self, path, id_mapping, **kwargs):
        """Remap the source and let its service remap metadata properties."""
        self.is_valid(path)
        source_id, *rest = path
        mapped_id = id_mapping.get("dashboard_data_sources", {}).get(int(source_id))
        if mapped_id is not None:
            source_id = mapped_id
            source = DashboardDataSource.objects.filter(id=source_id).first()
            if source and source.service_id:
                service = source.service.specific
                rest = service.get_type().import_context_path(rest, id_mapping)
        return [str(source_id), *rest]


dashboard_options_data_provider_registry = DataProviderTypeRegistry()
dashboard_options_data_provider_registry.register(
    DashboardDataSourceContextDataProviderType()
)


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
            # Bound the resolved option list.
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
