from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_INTEGRATION_DOES_NOT_EXIST = (
    "ERROR_INTEGRATION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested integration does not exist.",
)

ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION = (
    "ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION",
    HTTP_400_BAD_REQUEST,
    "The given integrations do not belong to the same application.",
)

ERROR_INTEGRATION_CREDENTIAL_REQUIRED = (
    "ERROR_INTEGRATION_CREDENTIAL_REQUIRED",
    HTTP_400_BAD_REQUEST,
    "The credential must be provided again when the connection target changes.",
)
