from typing import TYPE_CHECKING, Optional

from django.http import HttpRequest

from baserow.core.services.dispatch_context import DispatchContext

if TYPE_CHECKING:
    from baserow.contrib.dashboard.widgets.models import Widget
    from baserow.core.models import Workspace


class DashboardDispatchContext(DispatchContext):
    own_properties = [
        "request",
        "widget",
        "workspace",
        "dashboard",
        "data",
    ]

    def __init__(
        self,
        request: HttpRequest,
        workspace: Optional["Workspace"] = None,
        widget: Optional["Widget"] = None,
        dashboard=None,
        data=None,
    ):
        """Create a context for dispatching a dashboard data source."""

        # Before dashboard data sources needed their workspace directly, the second
        # positional argument was the widget. Keep accepting that shape while callers
        # move to passing the workspace.
        if widget is None and workspace is not None and hasattr(workspace, "dashboard"):
            widget = workspace
            workspace = widget.dashboard.workspace

        from baserow.contrib.dashboard.data_providers import (
            dashboard_data_provider_type_registry,
        )

        self.dashboard = dashboard or (widget.dashboard if widget else None)
        self.data = data or {}
        self.data_provider_registry = dashboard_data_provider_type_registry
        self.request = request
        self.widget = widget

        super().__init__(workspace)

    def get_runtime_filter(self, service):
        """Return the complete configured filter for this display widget."""
        from baserow.contrib.dashboard.widgets.handler import WidgetHandler

        widgets = [
            (widget, widget.get_type())
            for widget in WidgetHandler().get_widgets(self.dashboard)
        ]
        target = next(
            (
                widget
                for widget, widget_type in widgets
                if widget_type.is_display_widget
                and (source := widget_type.get_data_source(widget)) is not None
                and source.service_id == service.id
            ),
            None,
        )
        if target is None:
            return None
        from baserow.contrib.integrations.local_baserow.service_filter_groups import (
            build_runtime_filter,
        )

        groups = [
            group
            for widget, widget_type in widgets
            if widget_type.is_filter_widget
            if (group := widget_type.get_runtime_filter(widget, target, self))
            is not None
        ]
        return build_runtime_filter(service, groups)
