from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.exceptions import PermissionException

_Params = ParamSpec("_Params")
_Result = TypeVar("_Result")


class ToolInputError(Exception):
    """Raised when tool input is invalid."""


def _detail_messages(detail: Any) -> str:
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


def permission_denied_result(tool_name: str) -> dict[str, str]:
    """
    Describe a mutation blocked by permissions.

    :param tool_name: The tool that was denied.
    :return: An error and next_steps dict for the model.
    """

    return {
        "error": f"{tool_name} stopped because permission was denied.",
        "next_steps": (
            "Do not retry or claim the entire change succeeded. Explain that the "
            "current user lacks permission for the denied operation. Earlier "
            "changes may have been applied; inspect the current state before "
            "describing what remains."
        ),
    }


def return_permission_error(
    tool_name: str,
) -> Callable[
    [Callable[_Params, _Result]],
    Callable[_Params, _Result | dict[str, str]],
]:
    """
    Turn permission exceptions from a runtime tool into factual results.

    :param tool_name: The tool name reported in the denial result.
    :return: A decorator returning permission_denied_result on
        PermissionException instead of raising.
    """

    def decorate(function: Callable[_Params, _Result]):
        @wraps(function)
        def wrapped(*args: _Params.args, **kwargs: _Params.kwargs):
            try:
                return function(*args, **kwargs)
            except PermissionException:
                return permission_denied_result(tool_name)

        return wrapped

    return decorate
