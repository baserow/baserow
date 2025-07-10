from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from baserow.contrib.database.fields.constants import RESERVED_BASEROW_FIELD_NAMES

ERROR_FIELD_DOES_NOT_EXIST = (
    "ERROR_FIELD_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested field does not exist.",
)
ERROR_CANNOT_DELETE_PRIMARY_FIELD = "ERROR_CANNOT_DELETE_PRIMARY_FIELD"
ERROR_CANNOT_CHANGE_FIELD_TYPE = "ERROR_CANNOT_CHANGE_FIELD_TYPE"
ERROR_CANNOT_CREATE_FIELD_TYPE = "ERROR_CANNOT_CREATE_FIELD_TYPE"
ERROR_LINK_ROW_TABLE_NOT_PROVIDED = (
    "ERROR_LINK_ROW_TABLE_NOT_PROVIDED",
    HTTP_400_BAD_REQUEST,
    "The `link_row_table_id` must be provided.",
)
ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE = "ERROR_LINK_ROW_TABLE_NOT_IN_SAME_DATABASE"
ERROR_FIELD_NOT_IN_TABLE = (
    "ERROR_FIELD_NOT_IN_TABLE",
    HTTP_400_BAD_REQUEST,
    "The provided field does not belong in the related table.",
)
ERROR_INCOMPATIBLE_FIELD = (
    "ERROR_INCOMPATIBLE_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided field is not compatible.",
)
ERROR_ORDER_BY_FIELD_NOT_FOUND = (
    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
    HTTP_400_BAD_REQUEST,
    "The field {e.field_name} was not found in the table.",
)
ERROR_ORDER_BY_FIELD_NOT_POSSIBLE = (
    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
    HTTP_400_BAD_REQUEST,
    "It is not possible to order by {e.field_name} using sort type {e.sort_type} "
    "because the field type {e.field_type} does not support it.",
)
ERROR_FILTER_FIELD_NOT_FOUND = (
    "ERROR_FILTER_FIELD_NOT_FOUND",
    HTTP_400_BAD_REQUEST,
    "The field {e.field_name} was not found in the table.",
)
ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE = (
    "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE",
    HTTP_400_BAD_REQUEST,
    "The field type {e.field_type} is not compatible with the primary field.",
)
ERROR_DB_INDEX_NOT_SUPPORTED = (
    "ERROR_DB_INDEX_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The field type {e.field_type} does not support database indexes. Explicitly set "
    "`db_index` to `false` to fix this error.",
)
ERROR_SELF_REFERENCING_LINK_ROW_CANNOT_HAVE_RELATED_FIELD = (
    "ERROR_SELF_REFERENCING_LINK_ROW_CANNOT_HAVE_RELATED_FIELD",
    HTTP_400_BAD_REQUEST,
    "A self referencing link row field cannot have a related field.",
)
ERROR_MAX_FIELD_COUNT_EXCEEDED = "ERROR_MAX_FIELD_COUNT_EXCEEDED"
ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED = (
    "ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED",
    HTTP_400_BAD_REQUEST,
    "You cannot set a field name longer than {e.max_field_name_length} characters.",
)
ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS = (
    "ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS",
    HTTP_400_BAD_REQUEST,
    "You cannot have two fields with the same name in the same table, please choose a "
    "unique name for each field.",
)
ERROR_RESERVED_BASEROW_FIELD_NAME = (
    "ERROR_RESERVED_BASEROW_FIELD_NAME",
    HTTP_400_BAD_REQUEST,
    f"The field names {','.join(RESERVED_BASEROW_FIELD_NAMES)} are reserved and cannot "
    f"and cannot be used for a user created field, please choose different field name.",
)
ERROR_INVALID_BASEROW_FIELD_NAME = (
    "ERROR_INVALID_BASEROW_FIELD_NAME",
    HTTP_400_BAD_REQUEST,
    "Fields must not be blank or only consist of whitespace.",
)
ERROR_WITH_FORMULA = (
    "ERROR_WITH_FORMULA",
    HTTP_400_BAD_REQUEST,
    "Error with formula: {e}.",
)
ERROR_TOO_DEEPLY_NESTED_FORMULA = (
    "ERROR_TOO_DEEPLY_NESTED_FORMULA",
    HTTP_400_BAD_REQUEST,
    "The formula is too deeply nested.",
)
ERROR_FIELD_SELF_REFERENCE = (
    "ERROR_FIELD_SELF_REFERENCE",
    HTTP_400_BAD_REQUEST,
    "Fields cannot reference themselves.",
)
ERROR_FIELD_CIRCULAR_REFERENCE = (
    "ERROR_FIELD_CIRCULAR_REFERENCE",
    HTTP_400_BAD_REQUEST,
    "Fields cannot reference each other resulting in a circular chain of references.",
)
ERROR_INVALID_COUNT_THROUGH_FIELD = (
    "ERROR_INVALID_COUNT_THROUGH_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided through field does not exist, is in a different table or is not a "
    "link row field.",
)
ERROR_INVALID_ROLLUP_THROUGH_FIELD = (
    "ERROR_INVALID_ROLLUP_THROUGH_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided through field does not exist, is in a different table or is not a "
    "link row field.",
)
ERROR_INVALID_ROLLUP_TARGET_FIELD = (
    "ERROR_INVALID_ROLLUP_TARGET_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided target field does not exist or is in a different table to the table"
    " linked to by the through field.",
)
ERROR_INVALID_ROLLUP_FORMULA_FUNCTION = (
    "ERROR_INVALID_ROLLUP_FORMULA_FUNCTION",
    HTTP_400_BAD_REQUEST,
    "The provided rollup formula function does not exist.",
)
ERROR_INVALID_LOOKUP_THROUGH_FIELD = (
    "ERROR_INVALID_LOOKUP_THROUGH_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided through field does not exist, is in a different table or is not a "
    "link row field.",
)
ERROR_INVALID_LOOKUP_TARGET_FIELD = (
    "ERROR_INVALID_LOOKUP_TARGET_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided target field does not exist or is in a different table to the table"
    " linked to by the through field.",
)
ERROR_INCOMPATIBLE_FIELD_TYPE = (
    "ERROR_INCOMPATIBLE_FIELD_TYPE",
    HTTP_400_BAD_REQUEST,
    "The field type is not compatible with the action.",
)
ERROR_INCOMPATIBLE_FIELD_TYPE_FOR_UNIQUE_VALUES = (
    "ERROR_INCOMPATIBLE_FIELD_TYPE_FOR_UNIQUE_VALUES",
    HTTP_400_BAD_REQUEST,
    "The requested field type is not compatible with generating unique values.",
)
ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT = (
    "ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT",
    HTTP_409_CONFLICT,
    "The requested field is already being updated or used by another operation, "
    "please try again after other concurrent operations have finished.",
)
ERROR_DATE_FORCE_TIMEZONE_OFFSET_ERROR = (
    "ERROR_DATE_FORCE_TIMEZONE_OFFSET_ERROR",
    HTTP_400_BAD_REQUEST,
    "The field date should already exists and date_include_time  "
    "must be set to True on the field to convert values with "
    "the utc_offset provided in date_force_timezone_offset.",
)
ERROR_FIELD_IS_ALREADY_PRIMARY = (
    "ERROR_FIELD_IS_ALREADY_PRIMARY",
    HTTP_400_BAD_REQUEST,
    "The provided field is already the primary field.",
)
ERROR_TABLE_HAS_NO_PRIMARY_FIELD = (
    "ERROR_TABLE_HAS_NO_PRIMARY_FIELD",
    HTTP_400_BAD_REQUEST,
    "The provided table does not have a primary field.",
)
ERROR_IMMUTABLE_FIELD_TYPE = (
    "ERROR_IMMUTABLE_FIELD_TYPE",
    HTTP_400_BAD_REQUEST,
    "The field type is immutable.",
)
ERROR_IMMUTABLE_FIELD_PROPERTIES = (
    "ERROR_IMMUTABLE_FIELD_PROPERTIES",
    HTTP_400_BAD_REQUEST,
    "The field properties are immutable.",
)
ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD = (
    "ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD",
    HTTP_400_BAD_REQUEST,
    "Select option {e.select_option_id} does not belong to field {e.field_id}",
)
ERROR_FIELD_CONSTRAINT = (
    "ERROR_FIELD_CONSTRAINT",
    HTTP_400_BAD_REQUEST,
    "Cannot apply field constraint due to existing data conflicts.",
)
ERROR_FIELD_DATA_CONSTRAINT = (
    "ERROR_FIELD_DATA_CONSTRAINT",
    HTTP_400_BAD_REQUEST,
    "The operation violates a field constraint",
)
ERROR_INVALID_FIELD_CONSTRAINT = (
    "ERROR_INVALID_FIELD_CONSTRAINT",
    HTTP_400_BAD_REQUEST,
    "The field constraint {e.constraint_type} is not supported for field {e.field_type}.",
)
ERROR_INVALID_PASSWORD_FIELD_PASSWORD = (
    "ERROR_INVALID_PASSWORD_FIELD_PASSWORD",
    HTTP_401_UNAUTHORIZED,
    "The provided password in incorrect.",
)
ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE = (
    "ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE",
    HTTP_400_BAD_REQUEST,
    "Cannot set this constraint when default value is set.",
)
