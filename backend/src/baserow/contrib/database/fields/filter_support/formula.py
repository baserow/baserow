import typing

from django.db import models

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    ComparisonOperator,
)

from .base import (
    HasAllValuesEqualFilterSupport,
    HasNumericValueComparableToFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
)

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field, FormulaField


class FormulaFieldTypeArrayFilterSupport(
    HasAllValuesEqualFilterSupport,
    HasValueEqualFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    HasNumericValueComparableToFilterSupport,
):
    """
    A mixin that acts as a proxy between the formula field and the specific array
    formula function to call. Every method needs to be implemented here and forwarded
    to the right array formula subtype method.
    """

    def get_in_array_is_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "FormulaField",
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_is_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_empty_value(self, field: "Field") -> any:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_empty_value(field_instance)

    def get_in_array_empty_query(self, field_name, model_field, field: "FormulaField"):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_empty_query(
            field_name, model_field, field_instance
        )

    def get_in_array_contains_query(
        self, field_name, value, model_field, field: "FormulaField"
    ):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_contains_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_contains_word_query(
        self, field_name, value, model_field, field: "FormulaField"
    ):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_contains_word_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_length_is_lower_than_query(
        self, field_name, value, model_field, field: "FormulaField"
    ):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_length_is_lower_than_query(
            field_name, value, model_field, field_instance
        )

    def get_has_all_values_equal_query(
        self, field_name, value, model_field, field: "FormulaField"
    ):
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_all_values_equal_query(
            field_name, value, model_field, field_instance
        )

    def get_has_numeric_value_comparable_to_filter_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "Field",
        comparison_op: ComparisonOperator,
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_numeric_value_comparable_to_filter_query(
            field_name, value, model_field, field_instance, comparison_op
        )
