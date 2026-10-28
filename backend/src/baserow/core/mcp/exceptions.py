from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError

from loguru import logger
from pydantic import ValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.exceptions import (
    InstanceTypeDoesNotExist,
    PermissionException,
    UserNotInWorkspace,
)


class MCPEndpointDoesNotExist(Exception):
    """Raised when trying to get an MCP endpoint that doesn't exist."""


class MCPEndpointDoesNotBelongToUser(Exception):
    """
    Raised when a user tries to access an MCP endpoint that doesn't belong to them.
    """


class MaximumUniqueEndpointTriesError(Exception):
    """
    Raised when the maximum amount of tries has been exceeded when generating a
    unique MCP endpoint key.
    """


class MCPToolsNotAvailable(Exception):
    """Raised when an endpoint is given tools it can't use."""

    def __init__(self, names: list[str]):
        self.names = names
        super().__init__(f"Tools not available: {', '.join(names)}.")


class MCPToolInputError(Exception):
    """A call the client can fix by changing its arguments."""


PERMISSION_DENIED_MESSAGE = "You don't have permission to do this in this workspace."
NOT_FOUND_MESSAGE = "Not found in this workspace."
INTERNAL_ERROR_MESSAGE = "Internal error."


def _is_does_not_exist(exc: Exception) -> bool:
    # Baserow's own `*DoesNotExist` exceptions (ApplicationDoesNotExist,
    # PageDoesNotExist, AutomationWorkflowDoesNotExist, ...) derive straight from
    # `Exception`, so there is no common base to test. Matching the name is the same
    # rule the assistant's mode router uses.
    # Django's RelatedObjectDoesNotExist (a missing one-to-one, like user.profile) is
    # also an AttributeError. It is a server bug, not a missing resource.
    if isinstance(exc, AttributeError):
        return False
    return isinstance(exc, ObjectDoesNotExist) or any(
        cls.__name__.endswith("DoesNotExist") for cls in type(exc).__mro__
    )


def format_validation_error(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors(include_url=False, include_context=False):
        name = ".".join(str(part) for part in error["loc"])
        problems.append(f"{name}: {error['msg']}" if name else error["msg"])
    return "Invalid arguments. " + "; ".join(problems)


def _is_error_leaf(detail) -> bool:
    # `validate_data` stores each error as {"error": message, "code": code}.
    return isinstance(detail, dict) and set(detail) == {"error", "code"}


def flatten_error_detail(detail, prefix: str = "") -> list[str]:
    """Flattens nested DRF error details into ``name: message`` strings."""

    if _is_error_leaf(detail):
        detail = detail["error"]
    elif isinstance(detail, dict):
        messages = []
        for key, value in detail.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            messages.extend(flatten_error_detail(value, child))
        return messages
    if isinstance(detail, (list, tuple)):
        messages = []
        for index, value in enumerate(detail):
            child = (
                prefix
                if _is_error_leaf(value) or not isinstance(value, (dict, list, tuple))
                else (f"{prefix}.{index}" if prefix else str(index))
            )
            messages.extend(flatten_error_detail(value, child))
        return messages
    return [f"{prefix}: {detail}" if prefix else str(detail)]


def to_mcp_error(exc: Exception) -> str | None:
    """
    Turns an exception raised by a tool into the message for an MCP error result.

    :param exc: The exception raised while calling the tool.
    :return: The message for the client, or None when the exception is unexpected
        and must be logged and hidden behind a generic message.
    """

    if isinstance(exc, MCPToolInputError):
        return str(exc)
    # UserNotInWorkspace is a PermissionException, but the user must not learn
    # whether the object exists in another workspace.
    if isinstance(exc, UserNotInWorkspace):
        return NOT_FOUND_MESSAGE
    if isinstance(exc, PermissionException):
        return PERMISSION_DENIED_MESSAGE
    if isinstance(exc, DjangoValidationError):
        return "Invalid value. " + " ".join(exc.messages)
    if isinstance(exc, RequestBodyValidationException):
        return "Invalid value. " + "; ".join(flatten_error_detail(exc.detail["detail"]))
    # Raised with a reason, like a node type that is deactivated on this instance.
    if isinstance(exc, DRFPermissionDenied):
        return str(exc.detail)
    if isinstance(exc, DRFValidationError):
        return "Invalid value. " + "; ".join(flatten_error_detail(exc.detail))
    # Before the generic rule. `Registry.get` passes the client's type name and a
    # message, while `Registry.get_by_model` passes only a message for a server bug.
    if isinstance(exc, InstanceTypeDoesNotExist):
        return f"'{exc.type_name}' is not a valid type." if exc.args else None
    if _is_does_not_exist(exc):
        logger.warning(
            "MCP tool referenced a missing resource: {}: {}", type(exc).__name__, exc
        )
        return NOT_FOUND_MESSAGE
    return None
