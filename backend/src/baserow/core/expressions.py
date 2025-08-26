from django.db.models import DateTimeField, Expression, Field, Func, Lookup, Value


class Timezone(Expression):
    """
    This expression can convert an existing datetime value to another timezone. It
    can for example by used like this:

    ```
    SomeModel.objects.all().annotate(
        created_on_in_amsterdam=Timezone("created_on", "Europe/Amsterdam")
    ).filter(created_on_in_amsterdam__day=1)
    ```

    It will eventually result in `created_on at time zone 'Europe/Amsterdam'`
    """

    def __init__(self, expression, timezone):
        super().__init__(output_field=DateTimeField())
        self.source_expression = self._parse_expressions(expression)[0]
        self.timezone = timezone

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        c = self.copy()
        c.is_summary = summarize
        c.source_expression = self.source_expression.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        return c

    def __repr__(self):
        return "{}({}, {})".format(
            self.__class__.__name__,
            self.source_expression,
            self.timezone,
        )

    def as_sql(self, compiler, connection):
        params = []
        field_sql, field_params = compiler.compile(self.source_expression)
        timezone_sql, timezone_params = compiler.compile(Value(self.timezone))
        params.extend(field_params)
        params.extend(timezone_params)
        return f"{field_sql} at time zone {timezone_sql}", params


class DateTrunc(Func):
    """
    Source: https://gist.github.com/vdboor/f3ebe5e20c0882d39053

    To support using DATE_TRUNC('text', "field") in SQL

    Example::

        order_totals = (orders
            .annotate(
                period=DateTrunc('month', 'date_placed'),
            )
            .values("period")  # Needs to be in between for a correct GROUP_BY
            .order_by('period')
            .annotate(
                order_count=Count('id'),
                shipping_excl_tax=Sum('shipping_excl_tax'),
                shipping_incl_tax=Sum('shipping_incl_tax'),
            ))
    """

    function = "DATE_TRUNC"

    def __init__(self, trunc_type, field_expression, **extra):
        super(DateTrunc, self).__init__(Value(trunc_type), field_expression, **extra)


@Field.register_lookup
class IsDistinctFrom(Lookup):
    lookup_name = "isdistinctfrom"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return "%s IS DISTINCT FROM %s" % (lhs, rhs), params
