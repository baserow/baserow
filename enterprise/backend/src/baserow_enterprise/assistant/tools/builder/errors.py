"""
Messages for the builder errors a client causes with its input, worded like the REST
API's.
"""

from typing import Any

from baserow.api.utils import apply_exception_mapping


def _user_error_mapping() -> dict[type[Exception], Any]:
    """
    Builder exceptions that a client causes with its input, mapped to the REST API's
    error, so both give the same message.
    """

    from baserow.contrib.builder.api.data_sources import errors as dse
    from baserow.contrib.builder.api.elements import errors as ee
    from baserow.contrib.builder.api.pages import errors as pe
    from baserow.contrib.builder.api.workflow_actions import errors as wae
    from baserow.contrib.builder.data_sources import exceptions as ds
    from baserow.contrib.builder.elements import exceptions as e
    from baserow.contrib.builder.pages import exceptions as p
    from baserow.contrib.builder.workflow_actions import exceptions as wa

    return {
        p.PagePathNotUnique: pe.ERROR_PAGE_PATH_NOT_UNIQUE,
        p.PathParamNotInPath: pe.ERROR_PATH_PARAM_NOT_IN_PATH,
        p.PathParamNotDefined: pe.ERROR_PATH_PARAM_NOT_DEFINED,
        p.DuplicatePathParamsInPath: pe.ERROR_DUPLICATE_PATH_PARAMS_IN_PATH,
        p.InvalidQueryParamName: pe.ERROR_INVALID_QUERY_PARAM_NAME,
        p.DuplicatePageParams: pe.ERROR_DUPLICATE_QUERY_PARAMS,
        p.SharedPageIsReadOnly: pe.ERROR_SHARED_PAGE_READ_ONLY,
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

    return user_error_message(exc) or str(exc)
