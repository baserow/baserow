class WidgetDoesNotExist(Exception):
    """Raised when a widget does not exist."""


class WidgetTypeDoesNotExist(Exception):
    """Raised when a widget type does not exist."""


class WidgetImproperlyConfigured(Exception):
    """Raised when the widget settings is not allowed."""


class WidgetNotInDashboard(Exception):
    """Raised when the widget does not belong to the dashboard."""

    def __init__(self, widget_id=None, *args, **kwargs):
        self.widget_id = widget_id
        super().__init__(
            f"The widget {widget_id} does not belong to the dashboard.",
            *args,
            **kwargs,
        )
