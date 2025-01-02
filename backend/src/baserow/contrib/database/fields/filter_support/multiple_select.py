from typing import TYPE_CHECKING

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, Value

from baserow.contrib.database.fields.field_filters import (
    OptionallyAnnotatedQ,
    parse_select_option_ids,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArrayNestedSelectOptionValueSimilarToExpr,
    JSONArrayNestedValueAnyOfValuesExpr,
    JSONArrayNestedValueContainsValueExpr,
    JSONArrayValueIsExpr,
)

from .base import (
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueFilterSupport,
    get_array_json_filter_expression,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class MultipleleSelectFormulaTypeFilterSupport(
    HasValueEmptyFilterSupport,
    HasValueFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
):
    def get_in_array_empty_query(
        self, field_name, model_field, field: "Field"
    ) -> Q | OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayValueIsExpr, field_name, Value([], models.JSONField())
        )

    def get_in_array_is_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "Field",
    ) -> OptionallyAnnotatedQ:
        if not value:
            return Q()

        option_ids = parse_select_option_ids(value)

        return get_array_json_filter_expression(
            JSONArrayNestedValueAnyOfValuesExpr,
            field_name,
            Value(option_ids, ArrayField(models.IntegerField())),
        )

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayNestedValueContainsValueExpr, field_name, f"%{value}%"
        )

    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayNestedSelectOptionValueSimilarToExpr, field_name, value
        )
