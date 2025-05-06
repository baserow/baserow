from typing import TYPE_CHECKING, List

from django.db.models import Field, JSONField, Q, Value

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    OptionallyAnnotatedQ,
)

from .base import (
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    get_jsonb_contains_filter_expr,
    get_jsonb_contains_word_filter_expr,
    get_jsonb_has_any_in_value_filter_expr,
    get_jsonb_has_exact_value_filter_expr,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field as BaserowField


class MultipleSelectFormulaTypeFilterSupport(
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
):
    def get_all_empty_query(
        self,
        field_name: str,
        model_field: Field,
        field: "BaserowField",
        in_array: bool = True,
    ) -> OptionallyAnnotatedQ:
        any_not_empty = get_jsonb_has_any_in_value_filter_expr(
            model_field,
            [0],
            query_path="$[*].value.size()",
            comparison_operator=">",
            join_operator="&&",
        )
        return AnnotatedQ(
            annotation=any_not_empty.annotation,
            q=~any_not_empty.q | Q(**{f"{field_name}": Value([], JSONField())}),
        )

    def get_in_array_empty_query(
        self, field_name, model_field, field: "BaserowField"
    ) -> OptionallyAnnotatedQ:
        # Use get_jsonb_has_any_in_value_filter_expr with size() to check if the array
        # is empty.
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [0], query_path="$[*].value.size()"
        )

    def get_in_array_is_query(
        self,
        field_name: str,
        value: List[int],
        model_field: Field,
        field: "BaserowField",
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_exact_value_filter_expr(model_field, value)

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: Field, field: "BaserowField"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_filter_expr(
            model_field, value, query_path="$[*].value.value"
        )

    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: Field, field: "BaserowField"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_word_filter_expr(
            model_field, value, query_path="$[*].value.value"
        )
