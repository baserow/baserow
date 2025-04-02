from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_WORKFLOW_NAME_NOT_UNIQUE = (
    "ERROR_WORKFLOW_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The workflow name {e.name} already exists for your automation instance.",
)

ERROR_WORKFLOW_DOES_NOT_EXIST = (
    "ERROR_WORKFLOW_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested workflow does not exist.",
)