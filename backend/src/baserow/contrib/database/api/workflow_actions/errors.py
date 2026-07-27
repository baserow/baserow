from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

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
