from django.db.models.sql.compiler import SQLUpdateCompiler

from django_cte.cte import CTEQuery, CTEQuerySet
from django_cte.query import COMPILER_TYPES, CTECompiler, CTEUpdateQuery


class CTEUpdateReturningIdsQueryCompiler(SQLUpdateCompiler):
    """
    Extends the SQLUpdateCompiler to allow for returning ids after an update operation.
    This is useful when it's necessary to know which rows were updated without
    performing a separate query to fetch the updated rows.
    """

    def as_sql(self, *args, **kwargs):
        def _as_sql():
            sql, params = super(CTEUpdateReturningIdsQueryCompiler, self).as_sql(
                *args, **kwargs
            )
            return sql + " RETURNING id", params

        return CTECompiler.generate_sql(self.connection, self.query, _as_sql)

    def execute_sql(self, result_type):
        cursor = super(SQLUpdateCompiler, self).execute_sql(result_type)
        if cursor is None:
            return []
        return [res[0] for res in cursor.fetchall()]


class CTEUpdateRerurningQuery(CTEUpdateQuery, CTEQuery):
    pass


COMPILER_TYPES[CTEUpdateRerurningQuery] = CTEUpdateReturningIdsQueryCompiler


class BaserowCTEQuery(CTEQuery):
    """
    Extends the CTEQuery to allow for returning ids after an update operation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.returning_ids = False

    def chain(self, klass=None):
        if self.returning_ids:
            clone = super(CTEQuery, self).chain(CTEUpdateRerurningQuery)
        else:
            clone = super().chain(klass=klass)
        clone.returning_ids = self.returning_ids
        return clone


class BaserowCTEQuerySet(CTEQuerySet):
    """
    Extends the CTEQuerySet to use BaserowCTEQuery, which allows for returning ids after
    an update operation.
    """

    def __init__(self, model=None, query=None, using=None, hints=None):
        # Only create an instance of a Query if this is the first invocation in
        # a query chain.
        if query is None:
            query = BaserowCTEQuery(model)

        super().__init__(model, query, using, hints)

    def update_returning_ids(self, **kwargs):
        self.query.returning_ids = True
        return super().update(**kwargs)
