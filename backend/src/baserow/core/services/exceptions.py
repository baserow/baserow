class ServiceDoesNotExist(Exception):
    """Raised when trying to get a service that doesn't exist."""


class ServiceTypeDoesNotExist(Exception):
    """Raised when trying to use non-existing service type."""


class DispatchException(Exception):
    """Base class for all dispatch exception"""


class UnexpectedDispatchException(DispatchException):
    """Raised when trying to dispatch a service and an unexpected error happens."""


class ServiceImproperlyConfiguredDispatchException(DispatchException):
    """Raised when trying to dispatch a service that is not fully configured."""


class InvalidContextDispatchException(DispatchException):
    """
    Raised when trying to dispatch a service and the dispatch context is invalid.
    """


class InvalidContextContentDispatchException(DispatchException):
    """
    Raised when trying to dispatch a service and the dispatch context payload
    is invalid.
    """


class DoesNotExist(Exception):
    """Raised when calling a service dispatch method and nothing is found."""


class InvalidServiceTypeDispatchSource(Exception):
    """
    Raised when a `DataSource` or `BuilderWorkflowAction` is created or updated,
    and the `ServiceType` that is referenced is not valid for that dispatch-able source.
    """


class ServiceFilterPropertyDoesNotExist(Exception):
    """Raised when trying to dispatch a filter property that doesn't exist."""


class ServiceSortPropertyDoesNotExist(Exception):
    """Raised when trying to dispatch a sort property that doesn't exist."""


class TriggerServiceNotDispatchable(DispatchException):
    """When the trigger can't be immediately dispatched and needs an event to happens"""
