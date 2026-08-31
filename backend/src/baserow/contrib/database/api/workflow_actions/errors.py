from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
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

# `{e.reason}` is written for the person configuring the button, never from a
# service's own error, so it carries nothing server side.
ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED = (
    "ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED",
    HTTP_403_FORBIDDEN,
    "{e.reason}",
)

ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS = (
    "ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS",
    HTTP_409_CONFLICT,
    "A click is already running for this button and row.",
)

# `{e.message}` is rendered verbatim, so only messages written for the clicker
# may reach it. `DatabaseWorkflowActionService` is what guarantees that.
# The position rather than the id, since that is what the clicker can count.
ERROR_WORKFLOW_ACTION_DISPATCH_FAILED = (
    "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED",
    HTTP_400_BAD_REQUEST,
    "Action {e.position} failed: {e.message}",
)
