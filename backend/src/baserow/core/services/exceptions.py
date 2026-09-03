class ServiceDoesNotExist(Exception):
    """Raised when trying to get a service that doesn't exist."""


class ServiceTypeDoesNotExist(Exception):
    """Raised when trying to use non-existing service type."""


class DispatchException(Exception):
    """Base class for all dispatch exception"""


class UnexpectedDispatchException(DispatchException):
    """Raised when trying to dispatch a service and an unexpected error happens."""


class AddressNotAllowedDispatchException(UnexpectedDispatchException):
    """
    Raised when a service was refused the address it was pointed at, before
    anything was sent. Its message names that address, so it stays hidden from
    whoever triggered the dispatch, but no traffic left the instance and a
    caller counting outbound traffic does not count it.
    """


class ServiceImproperlyConfiguredDispatchException(DispatchException):
    """Raised when trying to dispatch a service that is not fully configured."""


class ResponseTooLargeDispatchException(ServiceImproperlyConfiguredDispatchException):
    """
    Raised when a service refused an answer for its size. Unlike its parent it
    is raised after the request has gone out, so a caller counting outbound
    traffic still counts it.
    """


class UnreachableAddressDispatchException(ServiceImproperlyConfiguredDispatchException):
    """
    Raised when a service could not reach the address it is pointed at. Its
    message names that address, so a caller showing it to someone who did not
    configure the service has to say something else instead.
    """


class RemoteRefusedDispatchException(ServiceImproperlyConfiguredDispatchException):
    """
    Raised when the service reached the server it is pointed at and that server
    refused the exchange, such as an SMTP server that will not start TLS or
    rejects the credentials. Unlike its parent it is raised once the instance
    has already reached out, so a caller counting outbound traffic still counts
    it. Its message is written for whoever clicked, and names neither the
    address nor the credential it carried.
    """


class InvalidContextDispatchException(DispatchException):
    """
    Raised when trying to dispatch a service and the dispatch context is invalid.
    """


class InvalidContextContentDispatchException(DispatchException):
    """
    Raised when trying to dispatch a service and the dispatch context payload
    is invalid.
    """


class PermissionDeniedDispatchException(DispatchException):
    """
    Raised when the acting user lacks a permission the dispatch needs, and the
    dispatch source wants that refusal reported rather than worked around. The
    message is written for that user, so it is safe to show them.
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
