"""
Messages for the Baserow errors a client causes with its input, shared by the
tools and MCP so they read like the REST API's.
"""

from typing import Any

from baserow.api.utils import apply_exception_mapping


def _user_error_mapping() -> dict[type[Exception], Any]:
    """
    Baserow exceptions that a client causes with its input, mapped to the REST API's
    error, so REST and MCP give the same message.
    """

    from baserow.contrib.database.api.fields import errors as fe
    from baserow.contrib.database.api.rows import errors as re
    from baserow.contrib.database.fields import exceptions as f
    from baserow.contrib.database.rows import exceptions as r

    return {
        f.FieldWithSameNameAlreadyExists: fe.ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS,
        f.ReservedBaserowFieldNameException: fe.ERROR_RESERVED_BASEROW_FIELD_NAME,
        f.InvalidBaserowFieldName: fe.ERROR_INVALID_BASEROW_FIELD_NAME,
        f.MaxFieldNameLengthExceeded: fe.ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED,
        f.MaxFieldLimitExceeded: fe.ERROR_MAX_FIELD_COUNT_EXCEEDED,
        f.CannotCreateFieldType: fe.ERROR_CANNOT_CREATE_FIELD_TYPE,
        f.CannotChangeFieldType: fe.ERROR_CANNOT_CHANGE_FIELD_TYPE,
        f.IncompatibleField: fe.ERROR_INCOMPATIBLE_FIELD_TYPE,
        f.IncompatiblePrimaryFieldTypeError: fe.ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE,
        f.LinkRowTableNotProvided: fe.ERROR_LINK_ROW_TABLE_NOT_PROVIDED,
        f.LinkRowTableNotInSameDatabase: fe.ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE,
        f.SelfReferencingLinkRowCannotHaveRelatedField: (
            fe.ERROR_SELF_REFERENCING_LINK_ROW_CANNOT_HAVE_RELATED_FIELD
        ),
        f.FieldNotInTable: fe.ERROR_FIELD_NOT_IN_TABLE,
        f.InvalidLookupThroughField: fe.ERROR_INVALID_LOOKUP_THROUGH_FIELD,
        f.InvalidLookupTargetField: fe.ERROR_INVALID_LOOKUP_TARGET_FIELD,
        f.FieldIsAlreadyPrimary: fe.ERROR_FIELD_IS_ALREADY_PRIMARY,
        f.CannotDeletePrimaryField: fe.ERROR_CANNOT_DELETE_PRIMARY_FIELD,
        f.PrimaryFieldAlreadyExists: fe.ERROR_PRIMARY_FIELD_ALREADY_EXISTS,
        f.SelectOptionDoesNotBelongToField: (
            fe.ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD
        ),
        f.InvalidFieldConstraint: fe.ERROR_INVALID_FIELD_CONSTRAINT,
        f.InvalidDefaultValueFunction: fe.ERROR_INVALID_DEFAULT_VALUE_FUNCTION,
        f.DbIndexNotSupportedError: fe.ERROR_DB_INDEX_NOT_SUPPORTED,
        f.FieldConstraintDoesNotSupportDefaultValueError: (
            fe.ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE
        ),
        f.FieldDataConstraintException: fe.ERROR_FIELD_DATA_CONSTRAINT,
        f.FailedToLockFieldDueToConflict: (
            fe.ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT
        ),
        r.CannotCreateRowsInTable: re.ERROR_CANNOT_CREATE_ROWS_IN_TABLE,
        r.CannotDeleteRowsInTable: re.ERROR_CANNOT_DELETE_ROWS_IN_TABLE,
        r.RowIdsNotUnique: re.ERROR_ROW_IDS_NOT_UNIQUE,
    }


def user_error_message(exc: Exception) -> str | None:
    """The REST API's message for a client error, or None for other exceptions."""

    _, error, detail = apply_exception_mapping(_user_error_mapping(), exc)
    if error is None:
        return None
    return detail or str(exc) or error.removeprefix("ERROR_").replace("_", " ").lower()


def conflict_errors() -> tuple[type[Exception], ...]:
    """
    Database exceptions meaning an item clashes with existing data.

    :return: The exception classes.
    """

    from baserow.contrib.database.fields import exceptions as f

    return (
        f.FieldWithSameNameAlreadyExists,
        f.FailedToLockFieldDueToConflict,
        f.PrimaryFieldAlreadyExists,
        f.FieldIsAlreadyPrimary,
    )
