"""Collect context references in dashboard option formulas."""

from baserow.contrib.dashboard.data_providers import (
    DashboardDataSourceContextDataProviderType,
)
from baserow.core.formula.registries import DataProviderTypeRegistry


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
