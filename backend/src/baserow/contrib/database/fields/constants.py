from enum import Enum

# Please keep in sync with the web-frontend version of this constant found in
# web-frontend/modules/database/utils/constants.js
RESERVED_BASEROW_FIELD_NAMES = {"id", "order"}
# This is an internal only field that allows upserting select options with a specific
# pk.
UPSERT_OPTION_DICT_KEY = "upsert_id"

# WARNING: these values are prone to SQL injection
# lowercase serializers.BooleanField.TRUE_VALUES + "checked" keyword
# fmt: off
BASEROW_BOOLEAN_FIELD_TRUE_VALUES = [
    't', 'T',
    'y', 'Y', 'yes', 'Yes', 'YES',
    'true', 'True', 'TRUE',
    'on', 'On', 'ON',
    '1', 1,
    "checked",
    True
]
# lowercase serializers.BooleanField.FALSE_VALUES + "unchecked" keyword
# fmt: off
BASEROW_BOOLEAN_FIELD_FALSE_VALUES = [
    'f', 'F',
    'n', 'N', 'no', 'No', 'NO',
    'false', 'False', 'FALSE',
    'off', 'Off', 'OFF',
    '0', 0, 0.0,
    "unchecked",
    False
]
SINGLE_SELECT_SORT_BY_ORDER = "order"

UNIQUE_WITH_EMPTY_CONSTRAINT_NAME = "unique_with_empty"


class DeleteFieldStrategyEnum(Enum):
    """
    This enum value can be passed into the `FieldHandler::delete_field`
    `delete_strategy` argument.
    """

    TRASH = "TRASH"  # default value that trashes the field.
    DELETE_OBJECT = "DELETE_OBJECT"  # just deletes the object in the database.
    PERMANENTLY_DELETE = "PERMANENTLY_DELETE"  # permanently deletes the object using the trash.
