class DashboardDataSourceDoesNotExist(Exception):
    """Raised when trying to get a data source that doesn't exist."""


class DashboardDataSourceImproperlyConfigured(Exception):
    """Raised when trying to dispatch a data source that is not fully configured."""


class ServiceConfigurationNotAllowed(Exception):
    """Raised when certain service properties are not allowed to be changed."""
