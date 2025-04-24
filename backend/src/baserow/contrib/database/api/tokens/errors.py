from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_503_SERVICE_UNAVAILABLE,
)

ERROR_TOKEN_DOES_NOT_EXIST = (
    "ERROR_TOKEN_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The token does not exist.",
)
ERROR_NO_PERMISSION_TO_TABLE = (
    "ERROR_NO_PERMISSION_TO_TABLE",
    HTTP_401_UNAUTHORIZED,
    "The token does not have permissions to the table.",
)

ERROR_CANNOT_INCLUDE_ROW_METADATA = (
    "ERROR_CANNOT_INCLUDE_ROW_METADATA",
    HTTP_400_BAD_REQUEST,
    "The token cannot include row metadata.",
)

ERROR_DATABASE_DEADLOCK = (
    "ERROR_DATABASE_DEADLOCK",
    HTTP_503_SERVICE_UNAVAILABLE,
    "The database failed to commit the transaction due to a deadlock.",
)
