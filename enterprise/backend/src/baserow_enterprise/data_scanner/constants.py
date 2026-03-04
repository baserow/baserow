from datetime import timedelta

from baserow.contrib.database.fields.models import (
    AutonumberField,
    EmailField,
    LongTextField,
    NumberField,
    PhoneNumberField,
    TextField,
    URLField,
    UUIDField,
)

# Contains the field types that can be used in the Baserow source table.
SCANNABLE_FIELD_TYPES = [
    TextField,
    LongTextField,
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

STALE_SCAN_THRESHOLD_HOURS = 2

FREQUENCY_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}
