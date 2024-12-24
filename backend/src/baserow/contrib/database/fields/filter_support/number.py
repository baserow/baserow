from typing import TYPE_CHECKING, Any

from django.db import models

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.fields.filter_support.base import (
    HasValueContainsFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueHigherOrEqualThanFilterSupport,
    HasValueHigherThanFilterSupport,
    HasValueLowerOrEqualThanFilterSupport,
    HasValueLowerThanFilterSupport,
    get_array_json_filter_expression,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArrayCompareNumericValueExpr,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class FormulaNumberTypeFilterSupport(
    HasValueEqualFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueContainsFilterSupport,
    HasValueLowerOrEqualThanFilterSupport,
    HasValueLowerThanFilterSupport,
    HasValueHigherThanFilterSupport,
    HasValueHigherOrEqualThanFilterSupport,
):
    """
    A mixin that provides filters methods for the number formula type.
    """

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return None

    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr, field_name, value, comparison_op="="
        )

    def get_has_value_higher_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr, field_name, value, comparison_op=">"
        )

    def get_has_value_higher_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr, field_name, value, comparison_op=">="
        )

    def get_has_value_lower_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr, field_name, value, comparison_op="<"
        )

    def get_has_value_lower_or_equal_filter_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr, field_name, value, comparison_op="<="
        )
