from typing import Any, Callable, Dict, Optional, Union

from drf_spectacular.types import OPENAPI_TYPE_MAPPING
from rest_framework.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    SerializerMethodField,
    TimeField,
    UUIDField,
)
from rest_framework.serializers import ListSerializer, Serializer

from baserow.contrib.builder.date import FormattedDate, FormattedDateTime
from baserow.contrib.database.api.fields.serializers import DurationFieldSerializer
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_integer,
    ensure_string,
)


def guess_json_type_from_response_serializer_field(
    serializer_field: Union[Field, Serializer]
) -> Dict[str, Any]:
    """
    Responsible for taking a serializer field, and guessing what its JSON
    type will be. If the field is a ListSerializer, and it has a child serializer,
    we add the child's type as well.

    :param serializer_field: The serializer field.
    :return: A dictionary to add to our schema.
    """

    if isinstance(serializer_field, (UUIDField, CharField, DecimalField, FloatField)):
        # DecimalField/FloatField values are returned as strings from the API.
        base_type = "string"
    elif isinstance(serializer_field, DateField):
        return {"type": "string", "format": "date"}
    elif isinstance(serializer_field, DateTimeField):
        return {"type": "string", "format": "date-time"}
    elif isinstance(serializer_field, (TimeField, DurationFieldSerializer)):
        base_type = "string"
    elif isinstance(serializer_field, ChoiceField):
        base_type = "string"
    elif isinstance(serializer_field, IntegerField):
        base_type = "number"
    elif isinstance(serializer_field, BooleanField):
        base_type = "boolean"
    elif isinstance(serializer_field, ListSerializer):
        # ListSerializer.child is required, so add its subtype.
        sub_type = guess_json_type_from_response_serializer_field(
            serializer_field.child
        )
        return {"type": "array", "items": sub_type}
    elif isinstance(serializer_field, SerializerMethodField):
        # Try to guess the json type of SerializerMethodField based on the
        # OpenAPI annotations.
        #
        # When a method serializer uses @extend_schema_field decorator it will
        # include a dictionary called "_spectacular_annotation" that contains
        # the type of the field to return.
        #
        # NOTE: This only works for primitive types (e.g, string, boolean, etc.)
        # and not for composite ones (e.g, object, lists, etc.).
        base_type = None
        method = getattr(serializer_field.parent, serializer_field.method_name)
        if hasattr(method, "_spectacular_annotation"):
            field = method._spectacular_annotation.get("field")
            mapping = OPENAPI_TYPE_MAPPING.get(field)
            if isinstance(mapping, dict):
                base_type = mapping.get("type", None)

    elif issubclass(serializer_field.__class__, Serializer):
        properties = {}
        for name, child_serializer in serializer_field.fields.items():
            guessed_type = guess_json_type_from_response_serializer_field(
                child_serializer
            )
            if guessed_type["type"] is not None:
                properties[name] = {
                    "title": name,
                    **guessed_type,
                }

        return {"type": "object", "properties": properties}
    else:
        base_type = None

    return {"type": base_type}


def guess_cast_function_from_response_serializer_field(
    serializer_field: Union[Field, Serializer]
) -> Optional[Callable]:
    """
    Return the appropriate cast function for a serializer type.

    :param serializer_field: The serializer field.
    :return: A function that can be used to cast a value to this serializer field type.
    """

    json_type = guess_json_type_from_response_serializer_field(serializer_field)
    ensure_map = {
        "string": ensure_string,
        "integer": ensure_integer,
        "boolean": ensure_boolean,
        "array": ensure_array,
    }
    # Date and datetime are represented as strings in JSON schema with format property
    # We still need to
    if json_type == {"type": "string", "format": "date"}:
        return lambda value: FormattedDate(value).date if value else None
    elif json_type == {"type": "string", "format": "date-time"}:
        return lambda value: FormattedDateTime(value).datetime if value else None
    else:
        return ensure_map.get(json_type.get("type"))
