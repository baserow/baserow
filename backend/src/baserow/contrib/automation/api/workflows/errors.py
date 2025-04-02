from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_WORKFLOW_NAME_NOT_UNIQUE = (
    "ERROR_WORKFLOW_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The workflow name {e.name} already exists for your automation instance.",
)
