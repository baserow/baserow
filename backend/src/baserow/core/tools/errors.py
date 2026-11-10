"""
Errors of the shared tools, as the messages their clients get.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError

from loguru import logger
from pydantic import ValidationError
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.exceptions import (
    InstanceTypeDoesNotExist,
    PermissionException,
    UserNotInWorkspace,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

PERMISSION_DENIED_MESSAGE = "You don't have permission to do this in this workspace."
NOT_FOUND_MESSAGE = "Not found in this workspace."
INTERNAL_ERROR_MESSAGE = "Internal error."
LICENCE_REQUIRED_MESSAGE = (
    "This needs a licence that this user doesn't have: a premium, advanced or "
    "enterprise plan, depending on the feature."
)


class ToolInputError(Exception):
    """A call the client can fix by changing its arguments."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        """
        :param message: What is wrong, written for people.
        :param hint: Advice for the model only, never shown to people.
        """

        super().__init__(message)
        self.hint = hint


def _detail_messages(detail) -> str:
    if isinstance(detail, dict):
        return " ".join(
            f"{field}: {_detail_messages(value)}" for field, value in detail.items()
        )
    if isinstance(detail, (list, tuple)):
        return " ".join(_detail_messages(value) for value in detail)
    return str(detail)


def validation_messages(exc: DRFValidationError) -> str:
    """The messages of a DRF ``ValidationError``, with the field they're on."""

    return _detail_messages(exc.detail)


def raise_if_permission_denied(error: Exception) -> None:
    """
    Let the mode router explain permission failures.

    :param error: The caught exception to inspect.
    :raises PermissionException: When the given error is one, so it reaches
        the mode router instead of being swallowed by a containment handler.
    """

    if isinstance(error, PermissionException):
        raise error


class ToolErrorCode(StrEnum):
    """Why a tool call or item failed, safe to show to users."""

    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_INPUT = "invalid_input"
    INVALID_FORMULA = "invalid_formula"
    CONFLICT = "conflict"
    FAILED = "failed"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class ToolError:
    code: ToolErrorCode
    message: str | None
    """The message for people, or None when the error is unexpected and must be
    logged and hidden behind a generic message."""
    hint: str | None = None
    """Advice for the model only, never shown to people."""

    def to_dict(self) -> dict[str, str]:
        """
        The error as tools return it.

        :return: The code, the message or the generic one, and the hint if any.
        """

        error = {
            "code": self.code.value,
            "message": self.message or INTERNAL_ERROR_MESSAGE,
        }
        if self.hint:
            error["hint"] = self.hint
        return error


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


def classify_tool_error(exc: Exception) -> ToolError:
    """
    Turns an exception raised by a tool into what the client calling the tool learns.

    :param exc: The exception raised while calling the tool.
    :return: The failure's code and the message for the client.
    """

    if isinstance(exc, ToolInputError):
        return ToolError(ToolErrorCode.INVALID_INPUT, str(exc), exc.hint)
    # UserNotInWorkspace is a PermissionException, but the user must not learn
    # whether the object exists in another workspace.
    if isinstance(exc, UserNotInWorkspace):
        return ToolError(ToolErrorCode.NOT_FOUND, NOT_FOUND_MESSAGE)
    if isinstance(exc, PermissionException):
        return ToolError(ToolErrorCode.PERMISSION_DENIED, PERMISSION_DENIED_MESSAGE)
    if isinstance(exc, DjangoValidationError):
        return ToolError(
            ToolErrorCode.INVALID_INPUT, "Invalid value. " + " ".join(exc.messages)
        )
    if isinstance(exc, RequestBodyValidationException):
        return ToolError(
            ToolErrorCode.INVALID_INPUT,
            "Invalid value. " + "; ".join(flatten_error_detail(exc.detail["detail"])),
        )
    # Raised with a reason, like a node type that is deactivated on this instance.
    if isinstance(exc, DRFPermissionDenied):
        return ToolError(ToolErrorCode.PERMISSION_DENIED, str(exc.detail))
    if isinstance(exc, DRFValidationError):
        return ToolError(
            ToolErrorCode.INVALID_INPUT,
            "Invalid value. " + "; ".join(flatten_error_detail(exc.detail)),
        )
    # Any other client error. Those come as an error code and a message.
    if isinstance(exc, APIException) and exc.status_code < 500:
        detail = exc.detail
        if isinstance(detail, dict) and "detail" in detail:
            # The REST message doesn't say a licence is what's missing.
            if detail.get("error") == "ERROR_FEATURE_NOT_AVAILABLE":
                return ToolError(ToolErrorCode.FAILED, LICENCE_REQUIRED_MESSAGE)
            detail = detail["detail"]
        return ToolError(ToolErrorCode.FAILED, "; ".join(flatten_error_detail(detail)))
    if isinstance(exc, ServiceImproperlyConfiguredDispatchException):
        return ToolError(ToolErrorCode.INVALID_INPUT, "Invalid value. " + str(exc))
    # Before the generic rule. `Registry.get` passes the client's type name and a
    # message, while `Registry.get_by_model` passes only a message for a server bug.
    if isinstance(exc, InstanceTypeDoesNotExist):
        if not exc.args:
            return ToolError(ToolErrorCode.FAILED, None)
        return ToolError(
            ToolErrorCode.INVALID_INPUT, f"'{exc.type_name}' is not a valid type."
        )
    if _is_does_not_exist(exc):
        logger.warning(
            "Tool referenced a missing resource: {}: {}", type(exc).__name__, exc
        )
        return ToolError(ToolErrorCode.NOT_FOUND, NOT_FOUND_MESSAGE)
    return ToolError(ToolErrorCode.FAILED, None)


def tool_error_message(exc: Exception) -> str | None:
    """
    Turns an exception raised by a tool into the message for the client calling the tool.

    :param exc: The exception raised while calling the tool.
    :return: The message for the client followed by its hint, or None when the
        exception is unexpected and must be logged and hidden behind a generic
        message.
    """

    error = classify_tool_error(exc)
    if error.message is None or not error.hint:
        return error.message
    return f"{error.message} {error.hint}"


def classify_item_error(
    exc: Exception, conflicts: tuple[type[Exception], ...] = ()
) -> ToolError:
    """
    Classify the error of one item that failed while the others go on. Call it from
    the ``except`` block, so an unexpected error is logged with its traceback.

    :param exc: The exception the item raised.
    :param conflicts: The tool's exceptions meaning the item clashes with existing
        data, like a name already in use.
    :return: The code and the message for people. The message is None for an
        unexpected error.
    """

    if isinstance(exc, conflicts):
        return ToolError(ToolErrorCode.CONFLICT, str(exc) or type(exc).__name__)
    error = classify_tool_error(exc)
    if error.message is not None:
        return error
    # Baserow's own errors say what the caller did; a bare type lookup is a server bug.
    if not isinstance(exc, (AttributeError, InstanceTypeDoesNotExist)) and type(
        exc
    ).__module__.startswith("baserow"):
        return ToolError(ToolErrorCode.INVALID_INPUT, str(exc) or type(exc).__name__)
    logger.exception("Unexpected error in a tool item: {}", exc)
    return ToolError(ToolErrorCode.FAILED, None)


def item_error_message(exc: Exception) -> str:
    """
    The message for one item that failed while the others go on. Call it from the
    ``except`` block, so an unexpected error is logged with its traceback.

    :param exc: The exception the item raised.
    :return: The message for the client.
    """

    return classify_item_error(exc).message or INTERNAL_ERROR_MESSAGE


def item_error(item: str | int, error: ToolError, **details: Any) -> dict[str, Any]:
    """
    One failed item of a batch tool.

    :param item: Which item failed, as the caller named it: a name, or an ID.
    :param error: Why it failed.
    :param details: What the tool's clients need to act on it, like a formula.
    :return: The item error as tools return it.
    """

    return {"item": item, **error.to_dict(), **details}


def finish_batch(
    result: dict[str, Any],
    changed: bool,
    errors: list[dict[str, Any]],
    nothing_done: str,
) -> dict[str, Any]:
    """
    Complete a batch tool's result so every client reads its outcome the same way:
    ``changed``, the failed items in ``errors``, and ``error`` only when nothing
    changed because items failed. Safe to call again after a client fixes items.

    :param result: The tool's result, changed in place.
    :param changed: Whether the call changed anything.
    :param errors: The failed items, from ``item_error``.
    :param nothing_done: The message when several items failed and none worked.
    :return: The result.
    """

    result.pop("error", None)
    result.pop("errors", None)
    result["changed"] = changed
    if errors:
        result["errors"] = errors
    if not changed and errors:
        codes = {error["code"] for error in errors}
        result["error"] = {
            "code": codes.pop() if len(codes) == 1 else ToolErrorCode.FAILED.value,
            "message": errors[0]["message"] if len(errors) == 1 else nothing_done,
        }
    return result
