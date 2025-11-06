from typing import Dict, List, Type, Union

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaObject,
)
from baserow.core.registry import Registry


def collect_json_formula_field_properties(registry: Type[Registry]) -> List[str]:
    """
    Returns a list of all the properties in the serializers of the given registry that
    are of type FormulaSerializerField. This is used by the `JSONFormulaField` to
    know which properties to parse for formulas when writing or reading to/from the
    database.

    :param registry: The registry to get the serializers from.
    :return: A list of property names. If a property is nested, it will be in the
        format "property.child", otherwise just "property".
    """

    properties: List[str] = []
    for instance in registry.get_all():
        serializer = instance.get_serializer_class()
        for field_name, field in serializer().get_fields().items():
            child = getattr(field, "child", None)
            if isinstance(field, FormulaSerializerField):
                properties.append(field_name)
            elif child is not None:
                for child_name, child_field in child.get_fields().items():
                    if isinstance(child_field, FormulaSerializerField):
                        properties.append(f"{field_name}.{child_name}")

    return list(set(properties))


class BaserowFormulaObjectSerializer(serializers.Serializer):
    formula = serializers.CharField(required=True, allow_blank=True)
    version = serializers.CharField(
        required=False, default=BASEROW_FORMULA_VERSION_INITIAL
    )
    mode = serializers.ChoiceField(
        required=False,
        default=BASEROW_FORMULA_MODE_SIMPLE,
        choices=[
            BASEROW_FORMULA_MODE_SIMPLE,
            BASEROW_FORMULA_MODE_ADVANCED,
            BASEROW_FORMULA_MODE_RAW,
        ],
    )


@extend_schema_field(OpenApiTypes.OBJECT)
class FormulaSerializerField(serializers.JSONField):
    """
    This field can be used to store a formula in the database.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required = False
        self.default = BaserowFormulaObject(
            formula="",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        )

    def to_internal_value(self, data: Union[str, Dict[str, str]]):
        data = super().to_internal_value(data)

        # The formula serializer does not require a value, but if this
        # value is a blank string or object, we need to construct the
        # default value.
        if not data:
            data = self.default

        # For compatibility reasons: we have a value, but if it's not
        # a dict, we expect it to be a string. For example: if we receive
        # a `row_id` formula of 5, an integer, we need to convert it to
        # a string.
        if not isinstance(data, dict):
            data = str(data)
        else:
            # It's a dictionary, so validate its structure.
            bfo_serializer = BaserowFormulaObjectSerializer(data=data)
            bfo_serializer.is_valid(raise_exception=True)
            data = bfo_serializer.validated_data

        # For compatibility reasons: if we receive a string, we will
        # construct a BaserowFormulaObject with it, and assume the
        # mode is 'simple', and the version is the initial version.
        # TODO: we should infer the `mode` differently, once we know
        #   what an advanced/raw formula looks like. Or: just force the
        #   user to tell us?
        if isinstance(data, str):
            data = BaserowFormulaObject(
                formula=data,
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            )

        if not data["formula"] or data["mode"] == BASEROW_FORMULA_MODE_RAW:
            return data

        try:
            get_parse_tree_for_formula(data["formula"])
            return data
        except BaserowFormulaSyntaxError as e:
            raise ValidationError(f"The formula is invalid: {e}", code="invalid")
