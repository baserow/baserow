import typing

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
    template = "(%(expressions)s) IS NULL"
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

    def as_sql(self, compiler, connection, template=None):
        sql_value, params_value = compiler.compile(self.value)

        template = template or self.template
        data = {
            "field_name": f'"{self.field_name.field.column}"',
            "value": sql_value,
        }
        return template % data, params_value


class FileNameContainsExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT attached_files ->> 'visible_name'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as attached_files
            WHERE UPPER(attached_files ->> 'visible_name') LIKE UPPER(%(value)s)
        )
        """  # nosec B608
    )
    # fmt: on


class JSONArrayContainsValueExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT filtered_field ->> 'value'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE UPPER(filtered_field ->> 'value') LIKE UPPER(%(value)s::text)
        )
        """  # nosec B608
    )
    # fmt: on


class JSONArrayContainsValueSimilarToExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT filtered_field ->> 'value'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE UPPER(filtered_field ->> 'value') SIMILAR TO %(value)s
        )
        """  # nosec B608 %(value)s
    )
    # fmt: on


class JSONArrayContainsValueLengthLowerThanExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT filtered_field ->> 'value'
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
        upper(%(value)s::text) =ALL(
            SELECT upper(filtered_field ->> 'value')
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
        ) AND JSONB_ARRAY_LENGTH(%(field_name)s) > 0
                """  # nosec B608 %(value)s
    )
    # fmt: on


class JSONArrayEqualSelectOptionIdExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT filtered_field -> 'value' ->> 'id'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE (filtered_field -> 'value' ->> 'id') LIKE (%(value)s)
        )
        """  # nosec B608
    )
    # fmt: on


class JSONArrayContainsSelectOptionValueExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        f"""
        EXISTS(
            SELECT filtered_field -> 'value' ->> 'value'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE UPPER(filtered_field -> 'value' ->> 'value') LIKE UPPER(%(value)s)
        )
        """  # nosec B608
    )
    # fmt: on


class JSONArrayContainsSelectOptionValueSimilarToExpr(BaserowFilterExpression):
    # fmt: off
    template = (
        r"""
        EXISTS(
            SELECT filtered_field -> 'value' ->> 'value'
            FROM JSONB_ARRAY_ELEMENTS(%(field_name)s) as filtered_field
            WHERE filtered_field -> 'value' ->> 'value' ~* ('\y' || %(value)s || '\y')
        )
        """  # nosec B608 %(value)s
    )
    # fmt: on
