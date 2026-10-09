class ServiceDoesNotExist(Exception):
    """Raised when trying to get a service that doesn't exist."""


class ServiceTypeDoesNotExist(Exception):
    """Raised when trying to use non-existing service type."""


class DispatchException(Exception):
    """Base class for all dispatch exception"""


class UnexpectedDispatchException(DispatchException):
    """Raised when trying to dispatch a service and an unexpected error happens."""


class RuntimeDispatchException(UnexpectedDispatchException):
    """
    Raised when the dispatch failed for a reason outside its configuration and
    a later attempt may succeed: the remote could not be reached, dropped the
    connection, or answered that it was busy. The automation runner retries
    these when the node's error policy says so; every other dispatch exception
    is final. Raised only where the failure is known to be transient, never
    from a catch-all branch.
    """


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
    Raised when the service reached the server it is pointed at and that
    server refused the exchange: an API answering with a refusal, or an SMTP
    server that will not start TLS or rejects the credentials. Unlike its
    parent it is raised once the request has gone out, so a caller counting
    outbound traffic still counts it. Its message is written for whoever
    clicked, and names neither the address nor the credential it carried.
    """


class RemoteBusyDispatchException(
    RemoteRefusedDispatchException, RuntimeDispatchException
):
    """
    The server was reached and asked for the request to be repeated later, a
    rate limit. Keeps the refused semantics (the request went out, the message
    is safe to show) and is retryable, the way requests' ConnectTimeout is both
    a ConnectionError and a Timeout.
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
