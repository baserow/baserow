import pytest
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    FloatField,
    IntegerField,
    SerializerMethodField,
    UUIDField,
)
from rest_framework.serializers import ListSerializer, Serializer

from baserow.contrib.integrations.local_baserow.utils import (
    guess_cast_function_from_response_serializer_field,
    guess_json_type_from_response_serializer_field,
)
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_date,
    ensure_datetime,
    ensure_integer,
    ensure_string,
)


def test_guess_type_for_response_serialize_field_permutations():
    TYPE_NULL = {"type": None}
    TYPE_OBJECT = {"type": "object", "properties": {}}
    TYPE_STRING = {"type": "string"}
    TYPE_NUMBER = {"type": "number"}
    TYPE_BOOLEAN = {"type": "boolean"}
    TYPE_DATE = {"type": "string", "format": "date"}
    TYPE_DATE_TIME = {"type": "string", "format": "date-time"}
    TYPE_ARRAY_CHILD_OBJECT = {
        "type": "array",
        "items": TYPE_OBJECT,
    }
    TYPE_OBJECT_FROM_METHOD_SERIALIZER = {
        "type": "object",
        "properties": {
            "answer": {"title": "answer", "type": "number"},
            "url": {"title": "url", "type": "string"},
        },
    }

    class FakeSerializer(Serializer):
        """Dummy serializer for testing method serializers that use OpenAPI types."""

        answer = SerializerMethodField()
        url = SerializerMethodField()

        @extend_schema_field(OpenApiTypes.NUMBER)
        def get_answer(self, instance):
            return 42

        @extend_schema_field(OpenApiTypes.URI)
        def get_url(self, instance):
            return "https://baserow.io"

    assert guess_json_type_from_response_serializer_field(UUIDField()) == TYPE_STRING
    assert guess_json_type_from_response_serializer_field(CharField()) == TYPE_STRING
    assert (
        guess_json_type_from_response_serializer_field(
            DecimalField(decimal_places=2, max_digits=4)
        )
        == TYPE_STRING
    )
    assert guess_json_type_from_response_serializer_field(FloatField()) == TYPE_STRING
    assert (
        guess_json_type_from_response_serializer_field(ChoiceField(choices=("a", "b")))
        == TYPE_STRING
    )
    assert guess_json_type_from_response_serializer_field(IntegerField()) == TYPE_NUMBER
    assert (
        guess_json_type_from_response_serializer_field(BooleanField()) == TYPE_BOOLEAN
    )
    assert guess_json_type_from_response_serializer_field(DateField()) == TYPE_DATE
    assert (
        guess_json_type_from_response_serializer_field(DateTimeField())
        == TYPE_DATE_TIME
    )
    assert (
        guess_json_type_from_response_serializer_field(
            ListSerializer(child=Serializer())
        )
        == TYPE_ARRAY_CHILD_OBJECT
    )
    assert guess_json_type_from_response_serializer_field(Serializer()) == TYPE_OBJECT
    assert (
        guess_json_type_from_response_serializer_field("unknown")  # type: ignore
        == TYPE_NULL
    )
    assert (
        guess_json_type_from_response_serializer_field((FakeSerializer()))
    ) == TYPE_OBJECT_FROM_METHOD_SERIALIZER


@pytest.mark.parametrize(
    "serializer,expected",
    [
        (CharField(), ensure_string),
        (UUIDField(), ensure_string),
        (EmailField(), ensure_string),
        (IntegerField(), ensure_integer),
        (DecimalField(decimal_places=2, max_digits=4), ensure_string),
        (BooleanField(), ensure_boolean),
        (DateField(), ensure_date),
        (DateTimeField(), ensure_datetime),
        (ListSerializer(child=Serializer()), ensure_array),
        ("unknown", None),
        (None, None),
    ],
)
def test_guess_cast_function_from_response_serialize_field(serializer, expected):
    assert guess_cast_function_from_response_serializer_field(serializer) == expected
