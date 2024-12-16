import typing

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from loguru import logger

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArrayContainsValueExpr,
    JSONArrayContainsValueHigherThanNumericExpr,
    JSONArrayContainsValueHigherThanOrEqualNumericExpr,
    JSONArrayContainsValueLowerThanNumericExpr,
    JSONArrayContainsValueLowerThanOrEqualNumericExpr,
    JSONArrayEqualNumericValueExpr,
    JSONArrayHasEmptyValueExpr,
)

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
    get_array_json_filter_expression,
)
from .exceptions import FilterNotSupportedException

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field, FormulaField


class FormulaFieldPrepDbValueMixin:
    def _is_value_empty(self, value):
        return value is None or (isinstance(value, str) and value.strip() == "")

    def _get_prep_value(
        self, value: str, instance: typing.Any | None = None
    ) -> typing.Any:
        """
        Checks if filtering `value` is a correct value for a base field type that is
        used by the formula field.

        If value is empty, then this method will return `None`.

        if value is not empty, but is invalid for the type,
        `FilterNotSupportedException` will be raised.

        :param value: filter value string
        :param instance: any instance of a field, if needed
        :return: a value that is compatible with the field type
        """

        from baserow.contrib.database.fields.registries import field_type_registry

        if self._is_value_empty(value):
            return None
        baserow_field_type = field_type_registry.get(self.baserow_field_type)
        field_instance = baserow_field_type.get_model_field(self)
        try:
            # Note: get_prep_value can return None if the value is empty.
            # This should be handled in the caller.
            return field_instance.get_prep_value(value)
        except ValidationError as err:
            logger.warning(f"Cannot use {value} as {field_instance}: {err}")
            raise FilterNotSupportedException(f"invalid numeric value {value}: {err}")


class FormulaArrayFilterSupport(
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
    A mixin that provides various filters interface to formula field type. Filtering
    methods will delegate the call to formula type.
    """

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


class FormulaNumberFilterSupport(
    FormulaFieldPrepDbValueMixin,
    HasValueEqualFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueContainsFilterSupport,
    HasValueLowerOrEqualThanFilterSupport,
    HasValueLowerThanFilterSupport,
    HasValueHigherThanFilterSupport,
    HasValueHigherOrEqualThanFilterSupport,
):
    """
    A mixin that provides filters interface for numeric formula type.
    """

    def get_in_array_empty_query(
        self, field_name: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayHasEmptyValueExpr, field_name, None
        )

    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        # ensure value is numeric
        if self._get_prep_value(value, field) is None:
            return Q()
        return get_array_json_filter_expression(
            JSONArrayEqualNumericValueExpr, field_name, value
        )

    def get_has_value_higher_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        if (numval := self._get_prep_value(value, field)) is None:
            return Q()

        return get_array_json_filter_expression(
            JSONArrayContainsValueHigherThanNumericExpr, field_name, numval
        )

    def get_has_value_higher_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        if (numval := self._get_prep_value(value, field)) is None:
            return Q()

        return get_array_json_filter_expression(
            JSONArrayContainsValueHigherThanOrEqualNumericExpr, field_name, numval
        )

    def get_has_value_lower_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        if (numval := self._get_prep_value(value, field)) is None:
            return Q()
        return get_array_json_filter_expression(
            JSONArrayContainsValueLowerThanNumericExpr, field_name, numval
        )

    def get_has_value_lower_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        if (numval := self._get_prep_value(value, field)) is None:
            return Q()
        return get_array_json_filter_expression(
            JSONArrayContainsValueLowerThanOrEqualNumericExpr, field_name, numval
        )

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        if self._get_prep_value(value, field) is None:
            return Q()
        return get_array_json_filter_expression(
            JSONArrayContainsValueExpr, field_name, f"%{value}%"
        )
