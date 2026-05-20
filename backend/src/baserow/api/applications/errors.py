from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_APPLICATION_DOES_NOT_EXIST = (
    "ERROR_APPLICATION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested application does not exist.",
)
ERROR_CANNOT_DELETE_LOCKED_APPLICATION = (
    "ERROR_CANNOT_DELETE_LOCKED_APPLICATION",
    HTTP_400_BAD_REQUEST,
    "This application is locked and can only be deleted by an admin.",
)
ERROR_APPLICATION_NOT_IN_GROUP = (
    "ERROR_APPLICATION_NOT_IN_GROUP",
    HTTP_400_BAD_REQUEST,
    "The application id {e.application_id} does not belong to the group.",
)

ERROR_APPLICATION_OPERATION_NOT_SUPPORTED = (
    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The application does not support this operation.",
)

ERROR_APPLICATION_TYPE_DOES_NOT_EXIST = (
    "ERROR_APPLICATION_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "{e}",
)
