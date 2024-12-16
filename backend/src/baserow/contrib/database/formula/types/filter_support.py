import typing

from django.db import models

from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
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
):
    """
    This mixin provides filter interface for array formula type, which basically
    delegates the call to a subtype formula type.
    """

    def get_in_array_is_query(self, field_name, value, model_field, field):
        return self.sub_type.get_in_array_is_query(
            field_name, value, model_field, field
        )

    def get_in_array_empty_query(self, field_name, model_field, field):
        return self.sub_type.get_in_array_empty_query(field_name, model_field, field)

    def get_in_array_contains_query(self, field_name, value, model_field, field):
        return self.sub_type.get_in_array_contains_query(
            field_name, value, model_field, field
        )

    def get_in_array_contains_word_query(self, field_name, value, model_field, field):
        return self.sub_type.get_in_array_contains_word_query(
            field_name, value, model_field, field
        )

    def get_in_array_length_is_lower_than_query(
        self, field_name, value, model_field, field
    ):
        return self.sub_type.get_in_array_length_is_lower_than_query(
            field_name, value, model_field, field
        )

    def get_has_all_values_equal_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.sub_type.get_has_all_values_equal_query(
            field_name, value, model_field, field
        )

    def get_has_value_higher_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.sub_type.get_has_value_higher_filter_query(
            field_name, value, model_field, field
        )

    def get_has_value_higher_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.sub_type.get_has_value_higher_or_equal_filter_query(
            field_name, value, model_field, field
        )

    def get_has_value_lower_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.sub_type.get_has_value_lower_filter_query(
            field_name, value, model_field, field
        )

    def get_has_value_lower_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.sub_type.get_has_value_lower_or_equal_filter_query(
            field_name, value, model_field, field
        )
