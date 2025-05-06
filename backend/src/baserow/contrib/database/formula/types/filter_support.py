import typing

from django.db import models

from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasNumericValueComparableToFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    ComparisonOperator,
)

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
    from baserow.contrib.database.fields.models import Field


class BaserowFormulaArrayFilterSupportMixin(
    HasAllValuesEqualFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    HasNumericValueComparableToFilterSupport,
):
    """
    This mixin proxies all the array formula filters methods to the formula subtype.
    """

    def empty_query(self, field_name, model_field, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_all_empty_query(
            field_name=field_name,
            model_field=model_field,
            field=field_instance,
            in_array=True,
        )

    def get_in_array_empty_value(self, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_empty_value(field_instance)

    def get_in_array_empty_query(self, field_name, model_field, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_empty_query(
            field_name, model_field, field_instance
        )

    def get_in_array_is_query(self, field_name, value, model_field, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_is_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_contains_query(self, field_name, value, model_field, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_contains_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_contains_word_query(self, field_name, value, model_field, field):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_contains_word_query(
            field_name, value, model_field, field_instance
        )

    def get_in_array_length_is_lower_than_query(
        self, field_name, value, model_field, field
    ):
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_in_array_length_is_lower_than_query(
            field_name, value, model_field, field_instance
        )

    def get_has_all_values_equal_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_has_all_values_equal_query(
            field_name, value, model_field, field_instance
        )

    def get_has_numeric_value_comparable_to_filter_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "Field",
        comparison_op: ComparisonOperator,
    ) -> "OptionallyAnnotatedQ":
        field_instance, _ = self.sub_type.get_baserow_field_instance_and_type()
        return self.sub_type.get_has_numeric_value_comparable_to_filter_query(
            field_name, value, model_field, field_instance, comparison_op
        )
