import re
import zoneinfo
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Type

from django.contrib.postgres.fields import JSONField
from django.db.models import BooleanField, F
from django.db.models import Field as DjangoField
from django.db.models import Q, Value
from django.db.models.expressions import RawSQL

from loguru import logger

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    OptionallyAnnotatedQ,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    BaserowFilterExpression,
    ComparisonOperator,
    JSONArrayAllAreExpr,
    JSONArrayCompareNumericValueExpr,
    JSONArrayContainsValueLengthLowerThanExpr,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field


class HasValueEmptyFilterSupport:
    def get_in_array_empty_value(self, field: "Field") -> Any:
        """
        Returns a single value or a list of values to use for filtering empty values in
        an arrays with the `get_jsonb_has_any_in_value_filter_expr`. See
        `get_in_array_empty_query` and `get_all_empty_query` for more details
        on how this value is used.

        :param field: The related field's instance.
        :return: A list of values to use in  get_jsonb_has_any_in_value_filter_expr for
            filtering empty values in an array.
        """

        return ""

    def empty_query(self, field_name, model_field, field) -> Q:
        return self.get_all_empty_query(
            field_name=field_name, model_field=model_field, field=field, in_array=False
        )

    def get_in_array_empty_query(
        self, field_name: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter empty values contained in an array.

        :param field_name: The name of the field.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        empty_value = self.get_in_array_empty_value(field)
        return get_jsonb_has_any_in_value_filter_expr(
            model_field,
            empty_value,
            query_path="$[*].value",
            comparison_operator="==",
            join_operator="||",
        )

    def get_all_empty_query(
        self,
        field_name: str,
        model_field: DjangoField,
        field: "Field",
        in_array: bool = True,
    ) -> OptionallyAnnotatedQ:
        empty_value = self.get_in_array_empty_value(field)
        any_not_empty = get_jsonb_has_any_in_value_filter_expr(
            model_field,
            empty_value,
            query_path="$[*].value",
            comparison_operator="!=",
            join_operator="&&",
        )
        return AnnotatedQ(
            annotation=any_not_empty.annotation,
            q=~any_not_empty.q | Q(**{f"{field_name}": Value([], JSONField())}),
        )


class HasValueEqualFilterSupport:
    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter exact values contained in an array.

        :param field_name: The name of the field.
        :param value: The value to check if it is contained in array.
        :param model_field: The field's actual django field model instance.
        :param field: The related field's instance.
        :return: A Q or AnnotatedQ filter given value.
        """

        return Q(**{f"{field_name}__contains": Value([{"value": value}], JSONField())})


class HasValueContainsFilterSupport:
    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
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

        return get_jsonb_contains_filter_expr(model_field, value)


class HasValueContainsWordFilterSupport:
    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter values in an array that contain a specific
        word.

        :param field_name: The name of the field.
        :param value: The value to check if it is contained in array.
        :param model_field: Django model field instance.
        :param field: The related Baserow field's instance containing field's metadata.
        :return: A Q or AnnotatedQ filter given value.
        """

        return get_jsonb_contains_word_filter_expr(model_field, value)


class HasValueLengthIsLowerThanFilterSupport:
    def get_in_array_length_is_lower_than_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        """
        Specifies a Q expression to filter values in an array that has lower
        than length.

        :param field_name: The name of the field.
        :param value: The value representing the length to use for the check.
        :param model_field: Django model field instance.
        :param field: The related Baserow field's instance containing field's metadata.
        :return: A Q or AnnotatedQ filter given value.
        """

        try:
            converted_value = int(value)
        except (TypeError, ValueError):
            return Q()
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


class HasAllValuesEqualFilterSupport:
    def get_has_all_values_equal_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> "OptionallyAnnotatedQ":
        """
         Creates a query expression to filter rows where all values of an array in
         the specified field are equal to a specific value

         :param field_name: The name of the field
         :param value: The value that should be present in all array elements
             in the field
        :param model_field: Django model field instance.
         :param field: The related Baserow field's instance containing field's metadata.
         :return: A Q or AnnotatedQ filter given value.
        """

        try:
            return get_array_json_filter_expression(
                JSONArrayAllAreExpr, field_name, Value(value)
            )

        except Exception as err:
            logger.error(
                f"Error when creating {self.type} filter expression "
                f"for {field_name} field with {value} value: {err}"
            )
            return self.default_filter_on_exception()


class HasNumericValueComparableToFilterSupport:
    def get_has_numeric_value_comparable_to_filter_query(
        self,
        field_name: str,
        value: str,
        model_field: DjangoField,
        field: "Field",
        comparison_op: ComparisonOperator,
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr,
            field_name,
            Value(value),
            comparison_op=comparison_op,
        )


def get_array_json_filter_expression(
    json_expression: Type[BaserowFilterExpression],
    field_name: str,
    value: Value,
    **extra: Dict[str, Any],
) -> AnnotatedQ:
    """
    Helper function to generate an AnnotatedQ for the given field and filtering
    expression. This function ensure a consistent way to name the annotations so they
    don't clash when combined with similar filters for different fields or values.


    :param json_expression: BaserowFilterExpression to use for filtering.
    :param field_name: the name of the field
    :param value: Value expression containing the filter value with the proper type.
    :param extra: extra arguments for the json_expression.
    :return: the annotated query for the filter.
    """

    annotation_query = json_expression(
        F(field_name), value, output_field=BooleanField(), **extra
    )
    expr_name = json_expression.__name__.lower()
    hashed_value = hash(value)
    annotation_name = f"{field_name}_{expr_name}_{hashed_value}"
    return AnnotatedQ(
        annotation={annotation_name: annotation_query},
        q={annotation_name: True},
    )


def get_jsonb_contains_filter_expr(
    model_field: DjangoField, value: str, query_path: str = "$[*].value"
) -> OptionallyAnnotatedQ:
    """
    Returns an AnnotatedQ that will filter rows where the JSON field contains the
    specified value or an empty filter if the value provided is an emtpy string. The
    value is matched using a case-insensitive LIKE query. Providing a query_path allows
    for filtering on a specific path in the JSON field.

    :param model_field: The django model field to filter on. The field is used to get
        the model for the subquery and the field name.
    :param value: The value to use to create the contains filter, case-insensitive.
    :param query_path: The path in the JSON field to filter on. Defaults to
        "$[*].value".
    :return: An AnnotatedQ that will filter rows where the JSON field contains the
    """

    # If an empty value has been provided we do not want to filter at all.
    if value == "":
        return Q()

    field_name = model_field.name
    raw_sql = f"""
        EXISTS(
            SELECT 1
            FROM jsonb_path_query("{field_name}", %s) elem
            WHERE UPPER(elem::text) LIKE UPPER(%s)
        )
    """  # nosec B608 {field_name}
    expr = RawSQL(raw_sql, (query_path, f"%{value}%"))  # nosec B611
    annotation_name = f"{field_name}_contains_{hash(value)}"
    return AnnotatedQ(
        annotation={annotation_name: expr},
        q=Q(**{annotation_name: True}),
    )


def get_jsonb_contains_word_filter_expr(
    model_field: DjangoField, value: str, query_path: str = "$[*].value"
) -> OptionallyAnnotatedQ:
    """
    Returns an AnnotatedQ that will filter rows where the JSON field contains the
    specified word or an empty filter if the value provided is an emtpy string. The
    value is matched using a case-insensitive LIKE query. Providing a query_path allows
    for filtering on a specific path in the JSON field.

    :param model_field: The django model field to filter on. The field is used to get
        the model for the subquery and the field name.
    :param value: The value to use to create the contains word filter, case-insensitive.
    :param query_path: The path in the JSON field to filter on. Defaults to
        "$[*].value".
    :return: An AnnotatedQ that will filter rows where the JSON field contains the
        specified word.
    """

    # If an empty value has been provided we do not want to filter at all.
    if value == "":
        return Q()

    field_name = model_field.name
    re_value = re.escape(value.upper())
    raw_sql = f"""
        EXISTS(
            SELECT 1
            FROM jsonb_path_query("{field_name}", %s) elem
            WHERE UPPER(elem::text) ~ %s
        )
    """  # nosec B608 {field_name}
    expr = RawSQL(raw_sql, (query_path, rf"\m{re_value}\M"))  # nosec B611

    annotation_name = f"{field_name}_contains_word_{hash(value)}"
    return AnnotatedQ(
        annotation={annotation_name: expr},
        q=Q(**{annotation_name: True}),
    )


VALUE_TO_JSON_PATH_MAP = {
    None: "null",
    "": '""',
}


def get_jsonb_has_any_in_value_filter_expr(
    model_field: DjangoField,
    value: Any,
    query_path: str = "$[*].id",
    comparison_operator: str = "==",
    join_operator: str = "||",
) -> OptionallyAnnotatedQ:
    """
    Returns an AnnotatedQ that will filter rows where the JSON field contains any of the
    IDs provided in value. Providing a query_path allows for filtering on a specific
    path in the JSON field.

    :param model_field: The django model field to filter on. The field is used to get
        the model for the subquery and the field name.
    :param value: A single value or a list of values to filter on. If a list is
        provided, it cannot be empty.
    :param query_path: The path in the JSON field to filter on. Defaults to "$[*].id".
    :return: An AnnotatedQ that will filter rows where the JSON field contains any of
        the select option IDs provided in the value.
    """

    if not isinstance(value, (list, tuple)):
        value = [value]

    mapped_values = [VALUE_TO_JSON_PATH_MAP.get(v, v) for v in value]

    sql_ids = f"{join_operator}".join(
        [f"(@ {comparison_operator} {v})" for v in mapped_values]
    )
    field_name = model_field.name

    raw_sql = f"""
        EXISTS(
            SELECT 1
            FROM jsonb_path_exists("{field_name}", %s) elem
            WHERE elem = true
        )
    """  # nosec B608 {field_name}
    expr = RawSQL(raw_sql, (f"{query_path} ? ({sql_ids})",))  # nosec B611

    annotation_name = f"{field_name}_has_any_of_{hash(sql_ids)}"
    return AnnotatedQ(
        annotation={annotation_name: expr},
        q=Q(**{annotation_name: True}),
    )


def get_jsonb_has_exact_value_filter_expr(
    model_field: DjangoField, value: List[int]
) -> OptionallyAnnotatedQ:
    """
    Returns an AnnotatedQ that filters rows where the JSON field exactly matches the
    provided IDs. The JSON field must be an array of objects, each containing a 'value'
    key, which is an array of objects with 'id' keys.
    For example: [{"value": [{"id":1}, {"id": 2}]}, {"value": [{"id": 3}]}, ...]

    :param model_field: The Django model field to filter on.
    :param value: A list of IDs to match. The list cannot be empty.
    :return: An AnnotatedQ that filters rows with the exact IDs in the JSON field.
    """

    field_name = model_field.name
    sql_ids = sorted(set(value))

    raw_sql = f"""
        EXISTS(
            SELECT 1
            FROM jsonb_array_elements("{field_name}") top_obj
            WHERE (
                SELECT array_agg((inner_el->>'id')::int ORDER BY (inner_el->>'id')::int)
                FROM jsonb_array_elements(top_obj->'value') inner_el
            ) = %s::int[]
        )
    """  # nosec B608 {field_name}
    expr = RawSQL(raw_sql, (sql_ids,))  # nosec B611

    annotation_name = f"{field_name}_has_any_of_{hash(tuple(sql_ids))}"
    return AnnotatedQ(
        annotation={annotation_name: expr},
        q=Q(**{annotation_name: True}),
    )


def get_jsonb_has_date_value_filter_expr(
    model_field: DjangoField,
    timezone: zoneinfo.ZoneInfo,
    gte_of: date | datetime | None = None,
    lt_of: date | datetime | None = None,
) -> OptionallyAnnotatedQ:
    """
    Returns an AnnotatedQ that filters rows where the JSON field contains a date or
    datetime value that is within the provided bounds. The JSON field must be an array
    of objects, each containing a 'value' key, which is a date or datetime. For example:
    [{"value": "2022-01-01T00:00:00Z"}, {"value": "2022-01-02T00:00:00Z"}, ...]

    :param model_field: The Django model field to filter on.
    :param timezone: The timezone to use when comparing the date or datetime values.
    :param gte_of: The lower bound of the date or datetime values to filter on. If
        provided, the date or datetime values must be greater than or equal to this
        value.
    :param lt_of: The upper bound of the date or datetime values to filter on. If
        provided, the date or datetime values must be less than this value.
    :return: An AnnotatedQ that filters rows with date or datetime values within the
        provided bounds.
    """

    if lt_of is None and gte_of is None:
        raise ValueError("At least one of the bounds must be provided.")

    where_clauses, where_params = [], []

    if gte_of:
        data_type = "date" if isinstance(gte_of, date) else "timestamptz"
        where_clauses.append(
            f"((elem->>'value')::timestamptz AT time zone %s)::{data_type} >= %s::{data_type}"
        )
        where_params.extend([str(timezone), gte_of.isoformat()])

    if lt_of:
        data_type = "date" if isinstance(lt_of, date) else "timestamptz"
        where_clauses.append(
            f"((elem->>'value')::timestamptz AT time zone %s)::{data_type} < %s::{data_type}"
        )
        where_params.extend([str(timezone), lt_of.isoformat()])

    field_name = model_field.name
    raw_sql = f"""
        EXISTS(
            SELECT 1
            FROM jsonb_array_elements("{field_name}") elem
            WHERE ({' AND '.join(where_clauses)})
        )
    """  # nosec B608 {field_name}
    expr = RawSQL(raw_sql, where_params)  # nosec B611

    annotation_name = f"{field_name}_has_date_gte_{hash(gte_of)}_lt_{hash(lt_of)}"
    return AnnotatedQ(
        annotation={annotation_name: expr},
        q=Q(**{annotation_name: True}),
    )
