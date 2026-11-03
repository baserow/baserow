"""
Messages for the builder errors a client causes with its input, worded like the REST
API's.
"""

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.utils import apply_exception_mapping
from baserow.core.tools.errors import ToolInputError, validation_messages


def _user_error_mapping() -> dict[type[Exception], Any]:
    """
    Builder exceptions that a client causes with its input, mapped to the REST API's
    error, so both give the same message.
    """

    from baserow.contrib.builder.api.data_sources import errors as dse
    from baserow.contrib.builder.api.elements import errors as ee
    from baserow.contrib.builder.api.workflow_actions import errors as wae
    from baserow.contrib.builder.data_sources import exceptions as ds
    from baserow.contrib.builder.elements import exceptions as e
    from baserow.contrib.builder.workflow_actions import exceptions as wa

    return {
        e.ElementNotInSamePage: ee.ERROR_ELEMENT_NOT_IN_SAME_PAGE,
        e.ElementMoveNotAllowed: ee.ERROR_ELEMENT_MOVE_NOT_ALLOWED,
        e.ElementTypeDeactivated: ee.ERROR_ELEMENT_TYPE_DEACTIVATED,
        ds.DataSourceNotInSamePage: dse.ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE,
        # The exception names the event and the valid ones; the REST message doesn't.
        wa.InvalidWorkflowActionEvent: (
            wae.ERROR_INVALID_WORKFLOW_ACTION_EVENT[0],
            wae.ERROR_INVALID_WORKFLOW_ACTION_EVENT[1],
            "{e}",
        ),
        wa.WorkflowActionNotInElement: wae.ERROR_WORKFLOW_ACTION_NOT_IN_ELEMENT,
    }


def user_error_message(exc: Exception) -> str | None:
    """The REST API's message for a builder client error, or None for others."""

    _, error, detail = apply_exception_mapping(_user_error_mapping(), exc)
    if error is None:
        return None
    return detail or str(exc) or error.removeprefix("ERROR_").replace("_", " ").lower()


def item_error(exc: Exception) -> str:
    """The message reported for one item of a batch that failed with ``exc``."""

    if isinstance(exc, DRFValidationError):
        return validation_messages(exc)
    return user_error_message(exc) or str(exc)


def is_input_error(exc: Exception) -> bool:
    """
    Whether ``exc`` comes from an item's input, so it is reported with the item.
    Anything else is a bug and is raised.
    """

    return (
        isinstance(
            exc,
            (
                ToolInputError,
                DRFValidationError,
                DjangoValidationError,
                ObjectDoesNotExist,
            ),
        )
        or user_error_message(exc) is not None
    )
