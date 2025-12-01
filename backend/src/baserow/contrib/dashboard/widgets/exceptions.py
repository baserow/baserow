class WidgetDoesNotExist(Exception):
    """Raised when a widget does not exist."""


class WidgetTypeDoesNotExist(Exception):
    """Raised when a widget type does not exist."""


class WidgetImproperlyConfigured(Exception):
    """Raised when the widget settings is not allowed."""
