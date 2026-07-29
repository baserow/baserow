from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST = (
    "ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested workflow action does not exist.",
)

ERROR_WORKFLOW_ACTION_NOT_IN_FIELD = (
    "ERROR_WORKFLOW_ACTION_NOT_IN_FIELD",
    HTTP_400_BAD_REQUEST,
    "The workflow action id {e.workflow_action_id} does not belong to the field.",
)

ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS = (
    "ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS",
    HTTP_409_CONFLICT,
    "A click is already running for this button and row.",
)

ERROR_WORKFLOW_ACTION_DISPATCH_FAILED = (
    "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED",
    HTTP_400_BAD_REQUEST,
    "The workflow action {e.workflow_action_id} failed: {e.message}",
)
