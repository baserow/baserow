from typing import TYPE_CHECKING, List

from django.db import models

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.fields.filter_support.multiple_select import (
    get_jsonb_has_any_in_value_filter_expr,
)

from .base import (
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    get_jsonb_contains_filter_expr,
    get_jsonb_contains_word_filter_expr,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class SingleSelectFormulaTypeFilterSupport(
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
):
    def get_in_array_empty_value(self, field: "Field") -> any:
        return None

    def get_in_array_is_query(
        self,
        field_name: str,
        value: List[int],
        model_field: models.Field,
        field: "Field",
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, value, query_path="$[*].value.id"
        )

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_filter_expr(
            model_field, value, query_path="$[*].value.value"
        )

    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_word_filter_expr(
            model_field, value, query_path="$[*].value.value"
        )
