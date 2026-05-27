import re

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.formula.serializers import FormulaSerializerField
from baserow_enterprise.integrations.core.models import CoreCodeServiceInjection


def validate_injection_name(value):
    valid_name_regex = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    if not valid_name_regex.match(value):
        raise ValidationError(
            "The name must be a valid variable name containing only alphanumeric "
            "characters or underscores, and must not start with a number."
        )

    return value


class CoreCodeServiceInjectionSerializer(serializers.ModelSerializer):
    """
    Serializer for code service injections.
    """

    name = serializers.CharField(
        allow_blank=False, max_length=255, validators=[validate_injection_name]
    )
    formula = FormulaSerializerField()

    class Meta:
        model = CoreCodeServiceInjection
        fields = ["id", "name", "formula"]
