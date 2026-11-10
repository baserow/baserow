"""Validate, import, and collect references in dashboard option formulas."""

import re

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import (
    DataProviderType,
    DataProviderTypeRegistry,
)


class DashboardDataSourceContextDataProviderType(DataProviderType):
    type = "data_source_context"

    def is_valid(self, path):
        if len(path) < 2 or not re.fullmatch(r"[1-9][0-9]{0,18}", path[0]):
            raise BaserowFormulaSyntaxError(
                "Choose dashboard data source context data."
            )
        return True

    def get_data_chunk(self, dispatch_context, path):
        raise NotImplementedError("Dashboard option formulas resolve in the frontend.")

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


def get_option_context_fields(widgets):
    """Collect literal source/field references using the standard formula visitor."""
    from baserow.contrib.dashboard.formula_importer import import_formula

    fields = {}

    class ReferencedContextProvider(DashboardDataSourceContextDataProviderType):
        def import_path(self, path, id_mapping, **kwargs):
            self.is_valid(path)
            fields.setdefault(int(path[0]), set()).add(path[1])
            return path

    registry = DataProviderTypeRegistry()
    registry.register(ReferencedContextProvider())
    for widget in widgets:
        if widget.get_type().type == "text_filter" and widget.mode == "dropdown":
            import_formula(widget.options, {}, data_provider_type_registry=registry)
    return fields
