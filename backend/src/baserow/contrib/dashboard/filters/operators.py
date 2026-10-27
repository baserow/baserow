from baserow.contrib.database.fields.field_types import (
    DateFieldType,
    NumberFieldType,
    TextFieldType,
)
from baserow.contrib.database.views.registries import view_filter_type_registry

FILTER_FIELD_TYPES = {
    "text": TextFieldType.type,
    "number": NumberFieldType.type,
    "date": DateFieldType.type,
}


def get_filter_operators(filter_type=None):
    """Read Builder operator metadata without querying field content types.

    With no filter type, return the union used by API schema validation. Concrete
    controls are validated against their own type before being saved.
    """

    if filter_type is None:
        field_types = set(FILTER_FIELD_TYPES.values())
    else:
        field_type = FILTER_FIELD_TYPES.get(filter_type)
        field_types = {field_type} if field_type else set()

    return {
        operator.type: operator
        for operator in view_filter_type_registry.get_all()
        if any(
            field_type in operator.compatible_field_types for field_type in field_types
        )
    }


def get_default_filter_operator(filter_type):
    return "date_is" if filter_type == "date" else "equal"
