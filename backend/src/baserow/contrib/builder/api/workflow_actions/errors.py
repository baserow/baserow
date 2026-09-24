from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST = (
    "ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested workflow action does not exist.",
)

ERROR_WORKFLOW_ACTION_NOT_IN_ELEMENT = (
    "ERROR_WORKFLOW_ACTION_NOT_IN_ELEMENT",
    HTTP_404_NOT_FOUND,
    "The requested workflow action does not belong to the element",
)

ERROR_WORKFLOW_ACTION_CANNOT_BE_DISPATCHED = (
    "ERROR_WORKFLOW_ACTION_CANNOT_BE_DISPATCHED",
    HTTP_400_BAD_REQUEST,
    "The requested workflow action cannot be dispatched.",
)

ERROR_INVALID_WORKFLOW_ACTION_EVENT = (
    "ERROR_INVALID_WORKFLOW_ACTION_EVENT",
    HTTP_400_BAD_REQUEST,
    "The event is not valid for the element the workflow action is attached to.",
)


ERROR_DATA_DOES_NOT_EXIST = (
    "ERROR_DATA_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested data does not exist.",
)
