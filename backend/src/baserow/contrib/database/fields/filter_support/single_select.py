from functools import reduce
from typing import TYPE_CHECKING, List

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import BooleanField, F, Q, Value

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    OptionallyAnnotatedQ,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArrayContainsSelectOptionValueExpr,
    JSONArrayContainsSelectOptionValueSimilarToExpr,
    JSONArrayEqualSelectOptionIdExpr,
)

from .base import (
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueFilterSupport,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class SingleSelectFormulaTypeFilterSupport(
    HasValueEmptyFilterSupport,
    HasValueFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
):
    def get_in_array_empty_query(self, field_name, model_field, field: "Field"):
        return Q(**{f"{field_name}__contains": Value([{"value": None}], JSONField())})

    def get_in_array_is_query(
        self,
        field_name: str,
        value: str | List[str],
        model_field: models.Field,
        field: "Field",
    ) -> OptionallyAnnotatedQ:
        if not value:
            return Q()
        elif isinstance(value, str):
            try:
                # If the value is a single value it must be a valid ID.
                int(value)
            except ValueError:
                return Q()
            value = [value]

        annotations, q = {}, []
        for v in value:
            hashed_value = hash(v)
            annotation_key = f"{field_name}_has_value_{hashed_value}"
            annotation_query = JSONArrayEqualSelectOptionIdExpr(
                F(field_name), Value(f"{v}"), output_field=BooleanField()
            )
            annotations[annotation_key] = annotation_query
            q.append(Q(**{annotation_key: True}))

        return AnnotatedQ(
            annotation=annotations,
            q=reduce(lambda a, b: a | b, q),
        )

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        annotation_query = JSONArrayContainsSelectOptionValueExpr(
            F(field_name), Value(f"%{value}%"), output_field=BooleanField()
        )
        hashed_value = hash(value)
        return AnnotatedQ(
            annotation={
                f"{field_name}_has_value_contains_{hashed_value}": annotation_query
            },
            q={f"{field_name}_has_value_contains_{hashed_value}": True},
        )

    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        annotation_query = JSONArrayContainsSelectOptionValueSimilarToExpr(
            F(field_name), Value(f"{value}"), output_field=BooleanField()
        )
        hashed_value = hash(value)
        return AnnotatedQ(
            annotation={
                f"{field_name}_has_value_contains_word_{hashed_value}": annotation_query
            },
            q={f"{field_name}_has_value_contains_word_{hashed_value}": True},
        )
