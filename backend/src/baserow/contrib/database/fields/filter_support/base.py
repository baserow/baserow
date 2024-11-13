import re
import typing

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import BooleanField, F, Q, Value

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    OptionallyAnnotatedQ,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArrayContainsValueExpr,
    JSONArrayContainsValueLengthLowerThanExpr,
    JSONArrayContainsValueSimilarToExpr,
)

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class HasValueEmptyFilterSupport:
    def get_in_array_empty_query(
        self, field_name: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter empty values contained in an array.

        :param field_name: The name of the field.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        return Q(**{f"{field_name}__contains": Value([{"value": ""}], JSONField())})


class HasValueFilterSupport:
    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter exact values contained in an array.

        :param field_name: The name of the field.
        :param value: The value to check if it is contained in array.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        if not value:
            return Q()

        return Q(**{f"{field_name}__contains": Value([{"value": value}], JSONField())})


class HasValueContainsFilterSupport:
    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter values in an array that contain a
        specific value.

        :param field_name: The name of the field.
        :param value: The value to check if it is contained in array.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        if not value:
            return Q()
        annotation_query = JSONArrayContainsValueExpr(
            F(field_name), Value(f"%{value}%"), output_field=BooleanField()
        )
        hashed_value = hash(value)
        return AnnotatedQ(
            annotation={
                f"{field_name}_has_value_contains_{hashed_value}": annotation_query
            },
            q={f"{field_name}_has_value_contains_{hashed_value}": True},
        )


class HasValueContainsWordFilterSupport:
    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter values in an array that contain a
        specific word.

        :param field_name: The name of the field.
        :param value: The value to check if it is contained in array.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        value = value.strip()
        if not value:
            return Q()
        value = re.escape(value.upper())
        annotation_query = JSONArrayContainsValueSimilarToExpr(
            F(field_name), Value(f"%\\m{value}\\M%"), output_field=BooleanField()
        )
        hashed_value = hash(value)
        return AnnotatedQ(
            annotation={
                f"{field_name}_has_value_contains_word_{hashed_value}": annotation_query
            },
            q={f"{field_name}_has_value_contains_word_{hashed_value}": True},
        )


class HasValueLengthIsLowerThanFilterSupport:
    def get_in_array_length_is_lower_than_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter values in an array that has lower
        than length.

        :param field_name: The name of the field.
        :param value: The value representing the length to use for the check.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        value = value.strip()
        if not value:
            return Q()
        converted_value = int(value)
        annotation_query = JSONArrayContainsValueLengthLowerThanExpr(
            F(field_name), Value(converted_value), output_field=BooleanField()
        )
        hashed_value = hash(value)
        return AnnotatedQ(
            annotation={
                f"{field_name}_has_value_length_is_lower_than_{hashed_value}": annotation_query
            },
            q={f"{field_name}_has_value_length_is_lower_than_{hashed_value}": True},
        )
