from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.parser.parser import get_parse_tree_for_formula


@extend_schema_field(OpenApiTypes.STR)
class FormulaSerializerField(serializers.CharField):
    """
    This field can be used to store a formula in the database.
    """

    def to_representation(self, value):
        if isinstance(value, dict):
            return value
        return super().to_representation(value)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)

        if not data:
            return data

        print("Validating formula:", data)

        try:
            get_parse_tree_for_formula(data)
            return data
        except BaserowFormulaSyntaxError as e:
            raise ValidationError(f"The formula is invalid: {e}", code="invalid")


@extend_schema_field(OpenApiTypes.STR)
class OptionalFormulaSerializerField(FormulaSerializerField):
    """
    This field can be used to store a formula, or plain text, in the database. If
    `value_is_formula` is `True`, then the value will be treated as a formula and
    `FormulaSerializerField` will be used to validate it. Otherwise, the value
    will be treated as plain text.
    """

    def __init__(self, *args, is_formula_field_name=None, **kwargs):
        self.is_formula_field_name = is_formula_field_name
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        is_formula = self.parent.data.get(self.is_formula_field_name, False)
        if not is_formula:
            return data

        return super().to_internal_value(data)
