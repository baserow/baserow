from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

ERROR_ROW_DOES_NOT_EXIST = (
    "ERROR_ROW_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The rows {e.ids} do not exist.",
)

ERROR_ROW_IDS_NOT_UNIQUE = (
    "ERROR_ROW_IDS_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The provided row ids {e.ids} are not unique.",
)

ERROR_INVALID_JOIN_PARAMETER = (
    "ERROR_INVALID_JOIN_PARAMETER",
    HTTP_400_BAD_REQUEST,
    "The provided __join query parameter wasn't used correctly.",
)
ERROR_CANNOT_CREATE_ROWS_IN_TABLE = (
    "ERROR_CANNOT_CREATE_ROWS_IN_TABLE",
    HTTP_400_BAD_REQUEST,
    "It is not possible to create a row in the provided table.",
)
ERROR_CANNOT_DELETE_ROWS_IN_TABLE = (
    "ERROR_CANNOT_DELETE_ROWS_IN_TABLE",
    HTTP_400_BAD_REQUEST,
    "It is not possible to delete a row in the provided table.",
)

ERROR_FAILED_TO_LOCK_ROWS_DUE_TO_CONFLICT = (
    "ERROR_FAILED_TO_LOCK_ROWS_DUE_TO_CONFLICT",
    HTTP_409_CONFLICT,
    "Failed to lock rows due to a conflict. Please try again later.",
)
