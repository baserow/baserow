class ServiceDoesNotExist(Exception):
    """Raised when trying to get a service that doesn't exist."""


class ServiceTypeDoesNotExist(Exception):
    """Raised when trying to use non-existing service type."""


class ServiceImproperlyConfigured(Exception):
    """Raised when trying to dispatch a service that is not fully configured."""


class DoesNotExist(Exception):
    """Raised when calling a service dispatch method and nothing is found."""


class InvalidServiceTypeDispatchSource(Exception):
    """
    Raised when a `DataSource` or `BuilderWorkflowAction` is created or updated,
    and the `ServiceType` that is referenced is not valid for that dispatch-able source.
    """
