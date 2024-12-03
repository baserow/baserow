import typing

from django.db import models

from loguru import logger

from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    IHasValueEmptyFilterSupport,
    IHasValueHigherOrEqualThanFilterSupport,
    IHasValueHigherThanFilterSupport,
    IHasValueLowerOrEqualThanFilterSupport,
    IHasValueLowerThanFilterSupport, IHasValueEqualFilterSupport,
    IHasValueContainsFilterSupport,
)
from baserow.contrib.database.fields.filter_support.exceptions import (
    FilterNotSupportedException,
)


class SubTypeCallerMixin:
    """
    A shortcut to call delegate method on a subtype formula type.
    """

    def do_call_subtype_filter_method(
        self,
        field_name,
        value,
        model_field,
        field,
        subcls_or_proto: typing.Type,
        method_name: str,
    ):
        if not isinstance(self.sub_type, subcls_or_proto):
            logger.warning(f"field {field} is not from {subcls_or_proto} hierarchy")
            raise FilterNotSupportedException()
        return getattr(self.sub_type, method_name)(
            field_name, value, model_field, field
        )


class BaserowFormulaArrayEqualFilterSupportMixin(
    SubTypeCallerMixin,
    HasAllValuesEqualFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
):
    def get_in_array_is_query(self, field_name, value, model_field, field):
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueEqualFilterSupport,
            "get_in_array_is_query",
        )

    def get_in_array_empty_query(self, field_name, model_field, field):
        return self.do_call_subtype_filter_method(
            field_name,
            None,
            model_field,
            field,
            IHasValueEmptyFilterSupport,
            "get_in_array_empty_query",
        )

    def get_in_array_contains_query(self, field_name, value, model_field, field):
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueContainsFilterSupport,
            "get_in_array_contains_query",
        )

    def get_in_array_contains_word_query(self, field_name, value, model_field, field):
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            HasValueContainsWordFilterSupport,
            "get_in_array_contains_word_query",
        )

    def get_in_array_length_is_lower_than_query(
        self, field_name, value, model_field, field
    ):
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            HasValueLengthIsLowerThanFilterSupport,
            "get_in_array_length_is_lower_than_query",
        )

    def get_has_all_values_equal_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            HasAllValuesEqualFilterSupport,
            "get_has_all_values_equal_query",
        )

    def get_has_value_higher_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueHigherThanFilterSupport,
            "get_has_value_higher_filter_query",
        )

    def get_has_value_higher_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueHigherOrEqualThanFilterSupport,
            "get_has_value_higher_or_equal_filter_query",
        )

    def get_has_value_lower_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueLowerThanFilterSupport,
            "get_has_value_lower_filter_query",
        )

    def get_has_value_lower_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        return self.do_call_subtype_filter_method(
            field_name,
            value,
            model_field,
            field,
            IHasValueLowerOrEqualThanFilterSupport,
            "get_has_value_lower_or_equal_filter_query",
        )
