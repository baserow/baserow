import typing
from enum import Enum

from django.contrib.postgres.aggregates.mixins import OrderableAggMixin
from django.db import NotSupportedError
from django.db.models import (
    Aggregate,
    Expression,
    F,
    Field,
    Func,
    JSONField,
    Transform,
    Value,
)


# noinspection PyAbstractClass
class BinaryOpExpr(Transform):
    template = "(%(expressions)s)"
    arity = 2


class IsNullExpr(Transform):
    template = "(%(expressions)s) IS NOT DISTINCT FROM NULL"
    arity = 1


# Django provides no way of doing a SQL equals expression with an arbitrary Django
# expression on both the LHS and RHS. Instead we have to define our own simple transform
# which joins two expressions together with a single =.
# noinspection PyAbstractClass
class EqualsExpr(BinaryOpExpr):
    arg_joiner = "="


# noinspection PyAbstractClass
class NotEqualsExpr(BinaryOpExpr):
    arg_joiner = "!="


# noinspection PyAbstractClass
class GreaterThanExpr(BinaryOpExpr):
    arg_joiner = ">"


# noinspection PyAbstractClass
class GreaterThanOrEqualExpr(BinaryOpExpr):
    arg_joiner = ">="


# noinspection PyAbstractClass
class LessThanExpr(BinaryOpExpr):
    arg_joiner = "<"


# noinspection PyAbstractClass
class LessThanEqualOrExpr(BinaryOpExpr):
    arg_joiner = "<="


# noinspection PyAbstractClass
class AndExpr(BinaryOpExpr):
    arg_joiner = " AND "


# noinspection PyAbstractClass
class OrExpr(BinaryOpExpr):
    arg_joiner = " OR "


# noinspection PyAbstractClass
class NotExpr(Transform):
    template = "(not %(expressions)s)"
    arity = 1


class TimezoneExpr(BinaryOpExpr):
    arg_joiner = " at time zone "


class BaserowStringAgg(OrderableAggMixin, Aggregate):
    function = "STRING_AGG"
    template = "%(function)s(%(distinct)s%(expressions)s %(order_by)s)"
    allow_distinct = True

    def __init__(self, expression, delimiter, **extra):
        super().__init__(expression, delimiter, **extra)

    def convert_value(self, value, expression, connection):
        if not value:
            return ""
        return value


class JSONArray(Func):
    function = "JSON_ARRAY"
    output_field = JSONField()

    def __init__(self, *items):
        expressions = []
        for item in items:
            expressions.extend(item)
        super().__init__(*expressions)

    def as_sql(self, compiler, connection, **extra_context):
        if not connection.features.has_json_object_function:
            raise NotSupportedError(
                "JSONObject() is not supported on this database backend."
            )
        return super().as_sql(compiler, connection, **extra_context)

    def as_postgresql(self, compiler, connection, **extra_context):
        return self.as_sql(
            compiler,
            connection,
            function="JSONB_BUILD_ARRAY",
            **extra_context,
        )


class JSONBArrayUniqueByValue(Func):
    """
    Dedup a JSONB array by the 'value' key of each element, preserving
    first-occurrence order. For arrays with elements like
    {"id": row_id, "value": actual_value}.
    """

    template = (
        "(SELECT COALESCE(jsonb_agg(sub.elem ORDER BY sub.rn), '[]'::jsonb) "
        "FROM (SELECT DISTINCT ON (t.elem -> 'value') t.elem, t.rn "
        "FROM jsonb_array_elements(%(expressions)s) WITH ORDINALITY AS t(elem, rn) "
        "ORDER BY t.elem -> 'value', t.rn) sub)"
    )
    output_field = JSONField()


class JSONBArrayJoinValues(Func):
    """
    Extract the 'value' text from each element of a JSONB array and join them
    with a separator, preserving the original array order.
    """

    function = "jsonb_array_join_values"
    template = (
        "(SELECT COALESCE(string_agg(t.elem->>'value', %(separator)s ORDER BY t.rn), '') "
        "FROM jsonb_array_elements(%(expressions)s) WITH ORDINALITY AS t(elem, rn))"
    )
    output_field: typing.ClassVar[Field] = None  # set in __init__

    def __init__(self, expression, separator, **extra):
        from django.db.models import fields as model_fields

        super().__init__(expression, output_field=model_fields.TextField(), **extra)
        self.separator = separator

    def as_sql(self, compiler, connection, **extra_context):
        separator_sql, separator_params = compiler.compile(self.separator)
        extra_context["separator"] = separator_sql
        sql, params = super().as_sql(compiler, connection, **extra_context)
        # separator appears before %(expressions)s in the template,
        # so its params must come first
        return sql, (*separator_params, *params)


class JSONBArrayGetElement(Expression):
    """
    Extract a single element from a JSONB array by 0-based index (negative
    counts from end) and optionally unwrap / cast the ``value`` key.

    *value_sql* is a SQL template with an ``{elem}`` placeholder that controls
    how the element is extracted (e.g. ``({elem} ->> 'value')::numeric``).
    Each formula type provides its own template via ``array_index_sql``.

    PostgreSQL's ``->`` operator natively handles negative indices and returns
    NULL for out-of-bounds, so no CASE expression is needed.
    """

    def __init__(self, array_expr, index_expr, value_sql, output_field):
        super().__init__(output_field=output_field)
        self.array_expr = array_expr
        self.index_expr = index_expr
        self.value_sql = value_sql

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        clone = self.copy()
        clone.is_summary = summarize
        clone.array_expr = self.array_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        clone.index_expr = self.index_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        return clone

    def as_sql(self, compiler, connection):
        arr_sql, arr_params = compiler.compile(self.array_expr)
        idx_sql, idx_params = compiler.compile(self.index_expr)

        elem_sql = f"({arr_sql}) -> ({idx_sql})::int"
        sql = f"({self.value_sql.format(elem=elem_sql)})"
        return sql, list(arr_params) + list(idx_params)


class JSONBArraySlice(Expression):
    """
    Slice a JSONB array with offset, limit, and optional reverse.

    All parameters should be pre-computed Django expressions:
    - offset_expr / limit_expr: the forward window (limit may be NULL for "all")
    - reverse_expr: boolean — when true, output order is reversed
    """

    def __init__(self, array_expr, offset_expr, limit_expr, reverse_expr):
        super().__init__(output_field=JSONField())
        self.array_expr = array_expr
        self.offset_expr = offset_expr
        self.limit_expr = limit_expr
        self.reverse_expr = reverse_expr

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        c = self.copy()
        c.is_summary = summarize
        c.array_expr = self.array_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        c.offset_expr = self.offset_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        c.limit_expr = self.limit_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        c.reverse_expr = self.reverse_expr.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        return c

    def as_sql(self, compiler, connection):
        array_sql, array_params = compiler.compile(self.array_expr)
        offset_sql, offset_params = compiler.compile(self.offset_expr)
        limit_sql, limit_params = compiler.compile(self.limit_expr)
        reverse_sql, reverse_params = compiler.compile(self.reverse_expr)

        sql = (
            "(SELECT COALESCE(jsonb_agg(sub.elem ORDER BY "  # noqa: S608
            f"CASE WHEN {reverse_sql} THEN -sub.rn ELSE sub.rn END"
            "), '[]'::jsonb) "
            "FROM (SELECT t.elem, t.rn "
            f"FROM jsonb_array_elements({array_sql}) WITH ORDINALITY AS t(elem, rn) "
            "ORDER BY t.rn "
            f"OFFSET {offset_sql} "
            f"LIMIT {limit_sql}) sub)"
        )
        return sql, (
            list(reverse_params)
            + list(array_params)
            + list(offset_params)
            + list(limit_params)
        )


class BaserowFilterExpression(Expression):
    """
    Baserow expression that works with field_name and value
    to provide expressions for filters. To use, subclass and
    define the template.
    """

    template: typing.ClassVar[str]

    def __init__(self, field_name: F, value: Value, output_field: Field):
        super().__init__(output_field=output_field)
        self.field_name = field_name
        self.value = value

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        c = self.copy()
        c.is_summary = summarize

        c.field_name = self.field_name.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )

        c.value = self.value.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )

        return c

    def get_template_data(self, sql_value) -> dict:
        return {
            "field_name": f'"{self.field_name.field.column}"',
            "value": sql_value,
        }

    def render_template_as_sql(
        self, filter_value: str, template: str | None = None
    ) -> str:
        """
        Renders the template with the given sql_value and returns the result. If a
        custom template is provided, it will be used instead of the default one.

        :param filter_value: The value that will be used in the template.
        :param template: The custom template to use. If not provided, the default one
            will be used.
        :return: The rendered template with data that will be used as SQL.
        """

        template = template or self.template
        data = self.get_template_data(filter_value)
        return template % data

    def as_sql(self, compiler, connection, template=None):
        sql_value, sql_params = compiler.compile(self.value)
        sql_query = self.render_template_as_sql(sql_value, template)
        return sql_query, sql_params


class FileNameContainsExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT 1
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as attached_files
            WHERE UPPER(attached_files ->> 'visible_name') LIKE UPPER(%(value)s)
        )
        """  # noqa: S608
    )
    # fmt: on


class JSONArrayContainsValueLengthLowerThanExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT 1
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE LENGTH(filtered_field ->> 'value') < %(value)s
        )
        """  # noqa: S608
    )
    # fmt: on


class JSONArrayAllAreExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        upper(%(value)s::text) = ALL(
            SELECT upper(filtered_field ->> 'value')
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
        ) AND JSONB_ARRAY_LENGTH(%(field_name)s) > 0
        """  # noqa: S608
    )
    # fmt: on


class ComparisonOperator(Enum):
    """
    An enumeration of the comparison operators that can be used to compare a number
    field value.
    """

    EQUAL = "="
    LOWER_THAN = "<"
    LOWER_THAN_OR_EQUAL = "<="
    HIGHER_THAN = ">"
    HIGHER_THAN_OR_EQUAL = ">="


class JSONArrayCompareNumericValueExpr(BaserowFilterExpression):
    """
    Base class for expressions that compare a numeric value in a JSON array.
    Together with the field_name and value, a comparison operator must be provided to be
    used in the template.
    """

    def __init__(
        self,
        field_name: F,
        value: Value,
        comparison_op: ComparisonOperator,
        output_field: Field,
    ):
        super().__init__(field_name, value, output_field)
        if not isinstance(comparison_op, ComparisonOperator):
            raise ValueError(
                f"comparison_op must be a ComparisonOperator, not {type(comparison_op)}"
            )
        self.comparison_op = comparison_op

    # fmt: off
    template = (
        f"""
            EXISTS(
                SELECT 1
                FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
                WHERE (filtered_field ->> 'value')::numeric %(comparison_op)s %(value)s::numeric
            )
            """  # noqa: S608
    )
    # fmt: on

    def get_template_data(self, sql_value) -> dict:
        data = super().get_template_data(sql_value)
        data["comparison_op"] = self.comparison_op.value
        return data


class JSONArrayCompareIntervalValueExpr(BaserowFilterExpression):
    """
    Base class for expressions that compare an interval value in a JSON array.
    Together with the field_name and value, a comparison operator must be provided to be
    used in the template.
    """

    def __init__(
        self,
        field_name: F,
        value: Value,
        comparison_op: ComparisonOperator,
        output_field: Field,
    ):
        super().__init__(field_name, value, output_field)
        if not isinstance(comparison_op, ComparisonOperator):
            raise ValueError(
                f"comparison_op must be a ComparisonOperator, not {type(comparison_op)}"
            )
        self.comparison_op = comparison_op

    # fmt: off
    template = (
        f"""
            EXISTS(
                SELECT 1
                FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
                WHERE (filtered_field ->> 'value')::interval %(comparison_op)s make_interval(secs=>%(value)s)
            )
            """  # noqa: S608
    )
    # fmt: on

    def get_template_data(self, sql_value) -> dict:
        data = super().get_template_data(sql_value)
        data["comparison_op"] = self.comparison_op.value
        return data
