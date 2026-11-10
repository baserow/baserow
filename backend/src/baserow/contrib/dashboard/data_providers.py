import re

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.utils import get_value_at_path

dashboard_data_provider_type_registry = DataProviderTypeRegistry()


class WidgetDataProviderType(DataProviderType):
    type = "widget_data"

    def is_valid(self, path):
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

    def get_data_chunk(self, dispatch_context, path):
        """Resolve only supported, untrashed widgets belonging to this dashboard."""
        self.is_valid(path)
        if dispatch_context.dashboard is None:
            raise InvalidFormulaContext("Invalid dashboard widget reference.")
        if "dashboard_filter_widgets" not in dispatch_context.cache:
            dispatch_context.cache["dashboard_filter_widgets"] = {
                str(w.id): w
                for w in WidgetHandler().get_widgets(dispatch_context.dashboard)
                if w.get_type().is_filter_widget
            }
        widgets = dispatch_context.cache["dashboard_filter_widgets"]
        widget = widgets.get(path[0])
        if widget is None:
            raise InvalidFormulaContext("The dashboard filter widget does not exist.")
        return get_value_at_path(
            widget.get_type().get_filter_value(
                widget, dispatch_context.data.get(self.type, {})
            ),
            path[1:],
        )

    def import_path(self, path, id_mapping, **kwargs):
        self.is_valid(path)
        return [
            str(id_mapping.get("dashboard_widgets", {}).get(int(path[0]), path[0])),
            *path[1:],
        ]


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
