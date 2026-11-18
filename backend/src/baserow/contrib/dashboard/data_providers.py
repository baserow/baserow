import re

from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.core.cache import local_cache
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.utils import get_value_at_path

dashboard_data_provider_type_registry = DataProviderTypeRegistry()


class WidgetDataProviderType(DataProviderType):
    type = "widget_data"

    def is_valid(self, path, validation_context=None):
        if not (
            1 <= len(path) <= 2
            and path[0].isascii()
            and path[0].isdigit()
            and len(path[0]) <= 19
            and path[0][0] != "0"
            and (
                len(path) == 1
                or path[1] == "*"
                or (path[1].isascii() and path[1].isdigit() and len(path[1]) <= 9)
            )
        ):
            raise BaserowFormulaSyntaxError("Expected a dashboard widget ID.")
        return True

    def get_widgets(self, dispatch_context):
        """Load only active widgets belonging to the dispatched dashboard."""
        if dispatch_context.dashboard is None:
            raise InvalidFormulaContext("Invalid dashboard widget reference.")
        return {
            str(widget.id): widget
            for widget in WidgetHandler().get_widgets(
                dispatch_context.dashboard, with_cache=True
            )
        }

    def validate_data_chunk(self, widget_id, value, dispatch_context):
        """Delegate each widget value to its type's runtime validation hook."""
        widget = self.get_widgets(dispatch_context).get(str(widget_id))
        if widget is None:
            raise InvalidFormulaContext("The dashboard widget does not exist.")
        return widget.get_type().validate_dispatch_data(widget, value)

    def validate_data(self, dispatch_context):
        """Share validated widget values within the request's dashboard payload."""
        if dispatch_context.dashboard is None:
            raise InvalidFormulaContext("Invalid dashboard widget reference.")
        return local_cache.get(
            f"dashboard_validated_widget_data_{dispatch_context.dashboard.id}",
            lambda: self._validate_data(dispatch_context),
        )

    def _validate_data(self, dispatch_context):
        """Validate the request payload through each referenced widget type."""
        from rest_framework.exceptions import ValidationError

        values = dispatch_context.data.get(self.type, {})
        if not isinstance(values, dict):
            raise ValidationError("Expected widget data keyed by widget IDs.")
        widgets = self.get_widgets(dispatch_context)
        validated = {}
        for key, value in values.items():
            try:
                if not isinstance(key, str):
                    raise BaserowFormulaSyntaxError("Expected a dashboard widget ID.")
                self.is_valid([key])
                if key not in widgets:
                    # A visitor whose page predates a widget's deletion still
                    # sends its value. No formula can resolve it, so drop it
                    # rather than failing every widget of the dashboard.
                    continue
                validated[key] = self.validate_data_chunk(key, value, dispatch_context)
            except (BaserowFormulaSyntaxError, InvalidFormulaContext) as exc:
                raise ValidationError(str(exc)) from exc
        return validated

    def get_data_chunk(self, dispatch_context, path):
        """Resolve validated widget input, falling back to its type's default."""
        self.is_valid(path)
        values = self.validate_data(dispatch_context)
        widget = self.get_widgets(dispatch_context).get(path[0])
        if widget is None:
            raise InvalidFormulaContext("The dashboard widget does not exist.")
        value = widget.get_type().get_dispatch_data(widget, values)
        if path[0] not in values:
            value = self.validate_data_chunk(widget.id, value, dispatch_context)
        return get_value_at_path(value, path[1:])

    def import_path(self, path, id_mapping, **kwargs):
        self.is_valid(path)
        return [
            str(id_mapping.get("dashboard_widgets", {}).get(int(path[0]), path[0])),
            *path[1:],
        ]


class DashboardDataSourceContextDataProviderType(DataProviderType):
    type = "data_source_context"

    def is_valid(self, path, validation_context=None):
        if len(path) < 2 or not re.fullmatch(r"[1-9][0-9]{0,18}", path[0]):
            raise BaserowFormulaSyntaxError(
                "Choose dashboard data source context data."
            )
        dashboard_id = (validation_context or {}).get("dashboard_id")
        if dashboard_id is not None:
            source = self._get_data_source(path[0])
            if source is None or source.dashboard_id != dashboard_id:
                raise BaserowFormulaSyntaxError(
                    "Choose a data source belonging to this dashboard."
                )
        return True

    def get_data_chunk(self, dispatch_context, path):
        raise NotImplementedError("Dashboard option formulas resolve in the frontend.")

    def _get_data_source(self, source_id):
        """Resolve through the handler, tolerating references to deleted sources."""
        try:
            return DashboardDataSourceHandler().get_data_source(int(source_id))
        except DashboardDataSourceDoesNotExist:
            return None

    def extract_properties(self, path, **kwargs):
        """Resolve a context reference to properties of its owning service."""
        self.is_valid(path)
        source_id, *rest = path
        source = self._get_data_source(source_id)
        if source is None or not source.service_id:
            return {}
        service = source.service.specific
        return {
            service.id: service.get_type().extract_properties(service, rest, **kwargs)
        }

    def import_path(self, path, id_mapping, **kwargs):
        """Remap the source and let its service remap metadata properties."""
        self.is_valid(path)
        source_id, *rest = path
        mapped_id = id_mapping.get("dashboard_data_sources", {}).get(int(source_id))
        if mapped_id is not None:
            source_id = mapped_id
            source = self._get_data_source(source_id)
            if source and source.service_id:
                service = source.service.specific
                rest = service.get_type().import_context_path(rest, id_mapping)
        return [str(source_id), *rest]


dashboard_options_data_provider_registry = DataProviderTypeRegistry()
dashboard_options_data_provider_registry.register(
    DashboardDataSourceContextDataProviderType()
)

# Extraction handles references from both runtime and option formulas without
# changing which providers those two formula contexts permit.
dashboard_property_data_provider_registry = DataProviderTypeRegistry()
dashboard_property_data_provider_registry.register(WidgetDataProviderType())
dashboard_property_data_provider_registry.register(
    DashboardDataSourceContextDataProviderType()
)
