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
    template = "%(function)s(%(distinct)s%(expressions)s %(ordering)s)"
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
        """  # nosec B608
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
        """  # nosec B608 %(value)s
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
        """  # nosec B608 %(value)s
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
            """  # nosec B608 %(value)s %(comparison_op)s
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
            """  # nosec B608 %(value)s %(comparison_op)s
    )
    # fmt: on

    def get_template_data(self, sql_value) -> dict:
        data = super().get_template_data(sql_value)
        data["comparison_op"] = self.comparison_op.value
        return data
