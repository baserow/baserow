import re

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.integrations.core.models import (
    HTTPFormData,
    HTTPHeader,
    HTTPQueryParam,
)
from baserow.core.formula.serializers import FormulaSerializerField


def validate_form_data_key(value):
    valid_key_regex = re.compile(r"^[a-zA-Z0-9\-_.]+$")

    if not valid_key_regex.match(value):
        raise ValidationError(
            "The name must contain only alphanumeric characters, dashes, point, "
            "or underscores."
        )
    return value


def validate_param_or_header_name(value):
    valid_name_regex = re.compile(r"^[a-zA-Z0-9-_]+$")

    if not valid_name_regex.match(value):
        raise ValidationError(
            "The name must contain only alphanumeric characters, dashes, or underscores."
        )

    if value[0] == "-" or value[0] == "_":
        raise ValidationError("The name must not start with a dash or an underscore.")

    return value


class HTTPFormDataSerializer(serializers.ModelSerializer):
    """
    Serializer for the Form data model.
    """

    key = serializers.CharField(
        allow_blank=True, max_length=255, validators=[validate_form_data_key]
    )
    value = FormulaSerializerField()

    class Meta:
        model = HTTPFormData
        fields = ["id", "key", "value"]


class HTTPHeaderSerializer(serializers.ModelSerializer):
    """
    Serializer for the HTTPHeader model.
    """

    key = serializers.CharField(
        allow_blank=True, max_length=255, validators=[validate_param_or_header_name]
    )
    value = FormulaSerializerField()

    class Meta:
        model = HTTPHeader
        fields = ["id", "key", "value"]


class HTTPQueryParamSerializer(serializers.ModelSerializer):
    """
    Serializer for the HTTPQueryParam model.
    """

    key = serializers.CharField(
        allow_blank=True, max_length=255, validators=[validate_param_or_header_name]
    )
    value = FormulaSerializerField()

    class Meta:
        model = HTTPQueryParam
        fields = ["id", "key", "value"]
