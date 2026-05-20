from django.conf import settings

from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

ERROR_TABLE_DOES_NOT_EXIST = (
    "ERROR_TABLE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested table does not exist.",
)
ERROR_TABLE_NOT_IN_DATABASE = (
    "ERROR_TABLE_NOT_IN_DATABASE",
    HTTP_400_BAD_REQUEST,
    "The table id {e.table_id} does not belong to the database.",
)
ERROR_CANNOT_DELETE_LOCKED_TABLE = (
    "ERROR_CANNOT_DELETE_LOCKED_TABLE",
    HTTP_400_BAD_REQUEST,
    "This table is locked and can only be deleted by an admin.",
)
ERROR_INVALID_INITIAL_TABLE_DATA = (
    "ERROR_INVALID_INITIAL_TABLE_DATA",
    HTTP_400_BAD_REQUEST,
    "The provided table data must at least contain one row and one column.",
)
ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP = (
    "ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP",
    HTTP_400_BAD_REQUEST,
    "The provided table does not belong to the related group.",
)
ERROR_INITIAL_SYNC_TABLE_DATA_LIMIT_EXCEEDED = (
    "ERROR_INITIAL_SYNC_TABLE_DATA_LIMIT_EXCEEDED",
    HTTP_400_BAD_REQUEST,
    "The initial table data limit for synchronous table creation has been exceeded. "
    "You can provide a maximum of "
    f"{settings.BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT} rows."
    "Please use asynchronous alternative for more rows.",
)
ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED = (
    "ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED",
    HTTP_400_BAD_REQUEST,
    f"The initial table data limit has been exceeded. You can provide a maximum of "
    f"{settings.INITIAL_TABLE_DATA_LIMIT} rows.",
)
ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES = (
    "ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES",
    HTTP_400_BAD_REQUEST,
    "Field names must be unique in Baserow per table however the initial table data "
    "provided contains duplicate field names, please make them unique and try again.",
)
ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT = (
    "ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT",
    HTTP_409_CONFLICT,
    "The requested table is already being updated or used by another operation, "
    "please try again after other concurrent operations have finished.",
)
