from dataclasses import dataclass
from datetime import datetime

from django.db.models import BooleanField, Expression, F, Func, Value


class RowLessThan(Func):
    """
    Compares two rows of values, like `(a, b) < (c, d)`. PostgreSQL turns a row
    comparison into an index condition on an index over those columns, so it reads
    from that position onwards. The equivalent `a < c OR (a = c AND b < d)` only
    filters what the index returns, which reads every row before the position too.
    """

    output_field = BooleanField()

    def __init__(self, lhs, rhs):
        if len(lhs) != len(rhs):
            raise ValueError("Both rows must have the same number of values.")
        super().__init__(*lhs, *rhs)

    def as_sql(self, compiler, connection, **extra_context):
        sqls, params = [], []
        for expression in self.get_source_expressions():
            sql, expression_params = compiler.compile(expression)
            sqls.append(sql)
            params.extend(expression_params)
        half = len(sqls) // 2
        return f"({', '.join(sqls[:half])}) < ({', '.join(sqls[half:])})", params


@dataclass(frozen=True)
class KeysetCursor:
    """
    The position of the last item of a page in a listing ordered by a moment and
    the id, both descending. The next page continues strictly after it, so items
    added, moved or removed in between neither repeat nor skip an item the way
    counting an offset would.
    """

    value: datetime
    id: int

    def get_filter(self, field_name: str) -> Expression:
        """
        :param field_name: The moment the listing is ordered by, before the id. An
            index on it followed by the id serves the filter as a range.
        :return: The filter keeping only what follows the cursor.
        """

        return RowLessThan(
            (F(field_name), F("id")), (Value(self.value), Value(self.id))
        )
