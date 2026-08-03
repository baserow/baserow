import pytest
from rest_framework import serializers

from baserow.contrib.database.api.fields.serializers import (
    FileFieldRequestSerializer,
    LinkRowRequestSerializer,
    ListOrStringField,
)

MALFORMED_CSV = '[\n  {\n    "name": ""\n  }\n]'


def test_file_field_request_serializer_newline_returns_validation_error():
    field = FileFieldRequestSerializer()
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(MALFORMED_CSV)


def test_link_row_request_serializer_newline_returns_validation_error():
    field = LinkRowRequestSerializer()
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(MALFORMED_CSV)


def test_list_or_string_field_newline_returns_validation_error():
    field = ListOrStringField()
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(MALFORMED_CSV)
