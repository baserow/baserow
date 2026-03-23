from datetime import timedelta

from baserow.contrib.database.fields.models import (
    AutonumberField,
    EmailField,
    NumberField,
    PhoneNumberField,
    TextField,
    URLField,
    UUIDField,
)

# Contains the field types that can be used in the Baserow source table.
SCANNABLE_FIELD_TYPES = [
    TextField,
    URLField,
    EmailField,
    NumberField,
    AutonumberField,
    PhoneNumberField,
    UUIDField,
]

SCANNABLE_FIELD_CONTENT_TYPES = [
    field._meta.model_name for field in SCANNABLE_FIELD_TYPES
]

SCAN_TYPE_PATTERN = "pattern"
SCAN_TYPE_LIST_OF_VALUES = "list_of_values"
SCAN_TYPE_LIST_TABLE = "list_table"

STALE_SCAN_THRESHOLD_HOURS = 2

FREQUENCY_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}
