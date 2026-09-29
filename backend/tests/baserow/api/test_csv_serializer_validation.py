import pytest
from rest_framework import serializers

from baserow.api.serializers import CommaSeparatedIntegerValuesField

MALFORMED_CSV = '[\n  {\n    "name": ""\n  }\n]'


def test_comma_separated_integer_field_newline_returns_validation_error():
    field = CommaSeparatedIntegerValuesField()
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(MALFORMED_CSV)
