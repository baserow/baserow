import typing

from django.db import models
from django.db.models import Q

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ

from .base import (
    HasAllValuesEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueHigherOrEqualThanFilterSupport,
    HasValueHigherThanFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    HasValueLowerOrEqualThanFilterSupport,
    HasValueLowerThanFilterSupport,
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
    HasValueLowerOrEqualThanFilterSupport,
    HasValueLowerThanFilterSupport,
    HasValueHigherThanFilterSupport,
    HasValueHigherOrEqualThanFilterSupport,
):
    """
    A mixin that acts as a proxy between the formula field and the specific array
    formula function to call. Every method needs to be implemented here and forwarded
    to the right array formula subtype method.
    """

    def get_in_array_empty_value(self, field: "Field") -> typing.Any:
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

    def get_in_array_is_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "FormulaField",
    ) -> Q | OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_in_array_is_query(
            field_name, value, model_field, field_instance
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

    def get_has_value_higher_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_value_higher_filter_query(
            field_name, value, model_field, field_instance
        )

    def get_has_value_higher_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_value_higher_or_equal_filter_query(
            field_name, value, model_field, field_instance
        )

    def get_has_value_lower_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_value_lower_filter_query(
            field_name, value, model_field, field_instance
        )

    def get_has_value_lower_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        (
            field_instance,
            field_type,
        ) = self.get_field_instance_and_type_from_formula_field(field)

        return field_type.get_has_value_lower_or_equal_filter_query(
            field_name, value, model_field, field_instance
        )
