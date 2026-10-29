from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry

dashboard_data_provider_type_registry = DataProviderTypeRegistry()


class WidgetDataProviderType(DataProviderType):
    type = "widget_data"

    def is_valid(self, path):
        if not (
            len(path) == 1
            and path[0].isascii()
            and path[0].isdigit()
            and len(path[0]) <= 19
            and path[0][0] != "0"
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
        return widget.get_type().get_filter_value(
            widget, dispatch_context.data.get(self.type, {})
        )

    def import_path(self, path, id_mapping, **kwargs):
        self.is_valid(path)
        return [str(id_mapping.get("dashboard_widgets", {}).get(int(path[0]), path[0]))]
