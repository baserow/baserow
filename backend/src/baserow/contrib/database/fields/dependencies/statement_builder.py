from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import EmptyResultSet
from django.db import connections
from django.db.models import (
    Aggregate,
    Expression,
    ExpressionWrapper,
    F,
    Q,
    QuerySet,
    Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast

from baserow.contrib.database.formula.expression_generator.django_expressions import (
    AggregateSubquery,
)


def execute_update_statements_returning_ids(
    model,
    update_statements: Dict[str, Optional[Expression]],
    querysets: List[Optional[QuerySet]],
    update_changes_only: bool = False,
) -> List[int]:
    """
    Executes the provided update statements as one UPDATE per queryset and
    returns the ids of the updated rows. When any statement aggregates over a
    joined table the statements are executed as a merged grouped scan (see
    MergedAggregateUpdateStatement), otherwise as a regular ORM update.

    :param model: The generated table model to update rows of.
    :param update_statements: A dict of the column names to update mapped to
        the expression calculating their new value, or None to set NULL.
    :param querysets: The querysets matching the rows to update, executed as
        one UPDATE statement each. A None entry updates the whole table.
    :param update_changes_only: If True then only rows for which at least one
        of the calculated values differs from the stored value are written,
        and only those rows are returned.
    :return: The ids of the rows that were actually updated.
    """

    if not update_statements:
        return []

    update_statements = _inline_same_statement_column_references(
        model, update_statements
    )

    updated_row_ids: List[int] = []
    merged_statement = MergedAggregateUpdateStatement(
        model, update_statements, update_changes_only=update_changes_only
    )
    if merged_statement.has_merged_aggregates:
        # At least one field aggregates over a joined table, so the aggregates
        # are merged into shared grouped scans instead of running one
        # correlated subquery per aggregate per row.
        for queryset in querysets:
            updated_row_ids += merged_statement.execute(queryset)
        return updated_row_ids

    annotations, filters = {}, Q()

    # If we are only updating changes, we need to filter out rows that don't
    # need to be updated. Because of how postgres works, this could save a lot
    # of disk space and IO, at the cost of a more complex query and a longer
    # execution time.
    if update_changes_only:
        connection = connections[model.objects_and_trash.db]
        for field, expr in update_statements.items():
            if expr is None or not field.startswith("field_"):
                continue

            target_field = model._meta.get_field(field)
            if not _same_db_type(expr, target_field, connection):
                # A type conversion is in flight, so the stored values can't
                # be compared against the calculated ones and every row must
                # be rewritten, which the conversion makes true anyway.
                annotations, filters = {}, Q()
                break

            # The stored value went through the column type on write (e.g. a
            # numeric column rounded it to its scale), so the calculated value
            # must be cast to the column type or the comparison would report
            # unrounded values as changed on every recalculation.
            cast_expr = Cast(expr, output_field=target_field)
            annotated_field = f"{field}_expr"
            annotations[annotated_field] = cast_expr
            # Because the expression can evaluate to null and because of how the
            # comparison with null should be handle in SQL
            # (https://www.postgresql.org/docs/15/functions-comparison.html), we
            # need to properly filter rows to correctly update only the ones
            # that need to be updated. The three clauses together behave like
            # `field IS DISTINCT FROM expr`.
            filters |= (
                Q(
                    **{
                        f"{field}__isnull": False,
                        f"{annotated_field}__isnull": True,
                    }
                )
                | Q(
                    **{
                        f"{field}__isnull": True,
                        f"{annotated_field}__isnull": False,
                    }
                )
                # The extra isnull clause is needed because Django compiles
                # the negated equality as NOT (field = expr AND field IS NOT
                # NULL), which would report every NULL stored value as
                # changed even when the calculated value is NULL too.
                | (Q(**{f"{field}__isnull": False}) & ~Q(**{field: cast_expr}))
            )

    for queryset in querysets:
        if queryset is None:
            queryset = model.objects_and_trash.all()
        updated_row_ids += (
            queryset.annotate(**annotations)
            .filter(filters)
            .update_returning_ids(**update_statements)
        )
    return updated_row_ids


def _inline_same_statement_column_references(
    model, update_statements: Dict[str, Optional[Expression]]
) -> Dict[str, Optional[Expression]]:
    """
    An UPDATE statement reads the pre-statement value of every column, so when
    multiple dependency levels are coalesced into one statement, a column
    reference to another column updated by the same statement would calculate
    from the old value. This substitutes such references with the referenced
    column's own update expression, cast to the column type to mirror the
    store-then-read roundtrip (e.g. numeric columns round to their scale), so
    chained formulas stay consistent within a single statement.

    Statements are added in topological order, so a reference can only point
    at a column that appears earlier in the dict.

    :param model: The generated table model the statements update.
    :param update_statements: A dict of the column names to update mapped to
        the expression calculating their new value, or None to set NULL.
    :return: The update statements with same-statement references inlined.
    """

    connection = connections[model.objects_and_trash.db]
    inlined: Dict[str, Optional[Expression]] = {}
    for column, expression in update_statements.items():
        if expression is not None:
            expression = _substitute_column_references(
                expression, inlined, model, connection
            )
        inlined[column] = expression
    return inlined


def _substitute_column_references(expression, inlined, model, connection):
    if isinstance(expression, F):
        if expression.name in inlined:
            replacement = inlined[expression.name]
            if replacement is None:
                return Value(None)
            replacement = deepcopy(replacement)
            target_field = model._meta.get_field(expression.name)
            if _same_db_type(replacement, target_field, connection):
                # Cast to the column type to mirror the store-then-read
                # roundtrip (e.g. numeric columns round to their scale).
                return Cast(replacement, output_field=target_field)
            # The model field no longer matches the expression because a type
            # conversion is in flight; the freshly calculated value is used
            # as-is.
            return replacement
        return expression
    if hasattr(expression, "get_source_expressions"):
        sources = expression.get_source_expressions()
        new_sources = [
            _substitute_column_references(child, inlined, model, connection)
            if child is not None
            and (isinstance(child, F) or hasattr(child, "get_source_expressions"))
            else child
            for child in sources
        ]
        if any(
            new_child is not child for child, new_child in zip(sources, new_sources)
        ):
            expression = expression.copy()
            expression.set_source_expressions(new_sources)
    return expression


# Postgres types (without any modifiers) that can safely be compared with
# each other after casting one side to the other's type.
_DB_TYPE_CATEGORIES = {
    "numeric": "number",
    "integer": "number",
    "bigint": "number",
    "smallint": "number",
    "double precision": "number",
    "real": "number",
    "text": "text",
    "varchar": "text",
    "character varying": "text",
    "character": "text",
    "char": "text",
    "boolean": "boolean",
    "jsonb": "json",
    "json": "json",
    "date": "date",
    "timestamp with time zone": "timestamp",
    "timestamp": "timestamp",
    "time": "time",
    "interval": "interval",
    "uuid": "uuid",
}


def _same_db_type(expression, target_field, connection) -> bool:
    """
    Returns whether the expression's output type is comparable with the
    database type of the targeted column, meaning the calculated value can
    safely be cast to the column type for an exact stored-value comparison.
    A mismatch signals a field type conversion in flight, during which the
    physical column no longer matches the model field.
    """

    try:
        expression_db_type = expression.output_field.db_type(connection)
        column_db_type = target_field.db_type(connection)
    except Exception:
        return False
    if expression_db_type == column_db_type:
        return True

    def category(db_type):
        if db_type is None:
            return None
        return _DB_TYPE_CATEGORIES.get(db_type.split("(")[0].strip())

    expression_category = category(expression_db_type)
    return expression_category is not None and expression_category == category(
        column_db_type
    )


class MergedAggregateUpdateStatement:
    """
    Compiles the pending update statements of a single table into one
    ``UPDATE .. SET .. FROM (SELECT id, agg_1, agg_2, .. GROUP BY id) ..``
    statement in which every aggregate over the same joins is calculated by a
    single grouped scan, instead of by one correlated subquery per aggregate
    per row.

    Every lookup/rollup/count style formula compiles to an
    :class:`AggregateSubquery`, which retains the raw aggregate expression and
    the ``FilteredRelation`` joins it aggregates over. Aggregates whose join
    signature matches are annotated onto one shared subquery, and their
    occurrences in the SET expressions are replaced by references to the
    subquery columns. A SET expression without any mergeable aggregate is
    compiled as-is, so plain correlated subqueries built outside of
    ``aggregate_wrapper`` keep working unchanged inside the same statement.

    The original correlated subqueries enforce inner joins by filtering the
    joined relations on not-null in the WHERE clause. In the merged form the
    joins are left joins so that every row of the table stays present in the
    grouped result (a row that just lost its last connection must still be
    rewritten), and the not-null conditions move into a per-aggregate FILTER
    clause instead, which aggregates the exact same set of joined rows.
    """

    def __init__(
        self,
        model,
        update_statements: Dict[str, Optional[Expression]],
        update_changes_only: bool = False,
    ):
        self._model = model
        self._update_statements = update_statements
        self._update_changes_only = update_changes_only
        # Group alias -> {"pre_annotations": .., "aggregates": {agg alias: expr}}
        self._groups: Dict[str, Dict[str, Any]] = {}
        # id(node) -> RawSQL replacement referencing the group subquery column.
        self._replacements: Dict[int, RawSQL] = {}
        self._signature_to_group_alias: Dict[Tuple[str, ...], str] = {}
        self._collect_mergeable_aggregates()

    @property
    def has_merged_aggregates(self) -> bool:
        return len(self._groups) > 0

    def _collect_mergeable_aggregates(self):
        for expression in self._update_statements.values():
            if expression is not None:
                self._visit(expression)

    def _visit(self, node):
        if isinstance(node, AggregateSubquery) and self._is_mergeable(node):
            self._assign_to_group(node)
            # The retained aggregate and its filters are evaluated inside the
            # group subquery, so there is no need to visit them here.
            return
        if isinstance(node, Q):
            for child in node.children:
                if isinstance(child, Q):
                    self._visit(child)
                elif isinstance(child, tuple) and len(child) == 2:
                    self._visit_if_expression(child[1])
            return
        if hasattr(node, "get_source_expressions"):
            for child in node.get_source_expressions():
                self._visit_if_expression(child)

    def _visit_if_expression(self, child):
        if child is not None and (
            hasattr(child, "get_source_expressions") or isinstance(child, Q)
        ):
            self._visit(child)

    def _is_mergeable(self, node: AggregateSubquery) -> bool:
        aggregate = self._find_aggregate(node.wrapped_aggregate)
        return (
            aggregate is not None
            and len(node.pre_annotations) > 0
            # The FILTER clause replacing the aggregate filters must not be
            # combined with an already set one in an unknown way.
            and aggregate.filter is None
        )

    def _find_aggregate(self, expression) -> Optional[Aggregate]:
        """
        Returns the single Aggregate the expression consists of, looking
        through output-typing ExpressionWrappers, or None when the expression
        has any other shape.
        """

        if isinstance(expression, Aggregate):
            return expression
        if isinstance(expression, ExpressionWrapper):
            sources = expression.get_source_expressions()
            if len(sources) == 1:
                return self._find_aggregate(sources[0])
        return None

    def _assign_to_group(self, node: AggregateSubquery):
        if id(node) in self._replacements:
            return
        signature = tuple(sorted(node.pre_annotations.keys()))
        group_alias = self._signature_to_group_alias.get(signature)
        if group_alias is None:
            group_alias = f"agg_sub_{len(self._groups)}"
            self._signature_to_group_alias[signature] = group_alias
            self._groups[group_alias] = {
                # Annotating mutates FilteredRelation objects in place, so
                # never share them with the original expression tree.
                "pre_annotations": deepcopy(node.pre_annotations),
                "aggregates": {},
            }
        group = self._groups[group_alias]
        agg_alias = f"agg_{len(group['aggregates'])}"
        group["aggregates"][agg_alias] = self._aggregate_with_join_filters(node)
        self._replacements[id(node)] = RawSQL(
            f'"{group_alias}"."{agg_alias}"', [], output_field=node.output_field
        )

    def _aggregate_with_join_filters(self, node: AggregateSubquery) -> Aggregate:
        """
        Returns a copy of the retained aggregate with the conditions that used
        to live in the WHERE clause of the correlated subquery (the not-null
        conditions forcing inner joins plus any formula filter() conditions)
        applied as the aggregate's FILTER clause instead.
        """

        not_null_filters = {
            f"{key}__isnull": False for key in node.pre_annotations.keys()
        }
        expression = deepcopy(node.wrapped_aggregate)
        aggregate = self._find_aggregate(expression)
        aggregate.filter = Q(*deepcopy(node.aggregate_filters), **not_null_filters)
        return expression

    def _substitute(self, node):
        replacement = self._replacements.get(id(node))
        if replacement is not None:
            return replacement
        if isinstance(node, Q):
            copied = node.__class__(
                *[
                    self._substitute(child)
                    if isinstance(child, Q)
                    else (
                        (child[0], self._substitute_if_expression(child[1]))
                        if isinstance(child, tuple) and len(child) == 2
                        else child
                    )
                    for child in node.children
                ]
            )
            copied.connector = node.connector
            copied.negated = node.negated
            return copied
        if hasattr(node, "get_source_expressions"):
            sources = node.get_source_expressions()
            if any(self._contains_replacement(child) for child in sources):
                node = node.copy()
                node.set_source_expressions(
                    [self._substitute_if_expression(child) for child in sources]
                )
        return node

    def _substitute_if_expression(self, child):
        if child is not None and (
            hasattr(child, "get_source_expressions") or isinstance(child, Q)
        ):
            return self._substitute(child)
        return child

    def _contains_replacement(self, node) -> bool:
        if node is None:
            return False
        if id(node) in self._replacements:
            return True
        if isinstance(node, Q):
            return any(
                self._contains_replacement(child)
                if isinstance(child, Q)
                else (
                    self._contains_replacement(child[1])
                    if isinstance(child, tuple) and len(child) == 2
                    else False
                )
                for child in node.children
            )
        if hasattr(node, "get_source_expressions"):
            return any(
                self._contains_replacement(child)
                for child in node.get_source_expressions()
            )
        return False

    def execute(self, row_filter_queryset: Optional[QuerySet]) -> List[int]:
        """
        Builds and runs the merged UPDATE statement, restricted to the rows
        matched by the provided queryset, or over the whole table when it is
        None. Returns the ids of the updated rows.

        :param row_filter_queryset: A queryset of this statement's model
            matching the rows to update, or None to update every row.
        :return: The ids of the rows that were actually updated.
        """

        try:
            sql, params = self._build_sql(row_filter_queryset)
        except EmptyResultSet:
            # The row filter is provably empty (e.g. an empty id list), so
            # there is nothing to update, matching Django's behaviour for
            # normal updates.
            return []
        using = self._model.objects_and_trash.db
        with connections[using].cursor() as cursor:
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]

    def _build_sql(self, row_filter_queryset: Optional[QuerySet]):
        using = self._model.objects_and_trash.db
        connection = connections[using]
        quote_name = connection.ops.quote_name
        table_name = quote_name(self._model._meta.db_table)

        group_sqls: List[str] = []
        group_params: List[Any] = []
        for group_alias, group in self._groups.items():
            queryset = self._model.objects_and_trash.all()
            if row_filter_queryset is not None:
                queryset = queryset.filter(
                    id__in=row_filter_queryset.values("id").order_by()
                )
            queryset = (
                # Annotating mutates the FilteredRelation objects passed in,
                # so annotate with copies to keep this statement re-executable
                # (e.g. once per row filter).
                queryset.annotate(**deepcopy(group["pre_annotations"]))
                .values("id")
                .annotate(**deepcopy(group["aggregates"]))
                .order_by()
            )
            sub_sql, sub_params = queryset.query.sql_with_params()
            group_sqls.append(f"({sub_sql}) {quote_name(group_alias)}")
            group_params.extend(sub_params)

        fragment_query = self._model.objects_and_trash.all().query
        compiler = fragment_query.get_compiler(connection=connection)
        # Resolving refs requires the initial table alias to exist.
        fragment_query.get_initial_alias()

        set_sqls: List[str] = []
        set_params: List[Any] = []
        guard_sqls: List[str] = []
        guard_params: List[Any] = []
        for db_column, expression in self._update_statements.items():
            column_sql = quote_name(db_column)
            if expression is None:
                fragment_sql, fragment_params = "NULL", []
            else:
                substituted = self._substitute(expression)
                resolved = substituted.resolve_expression(fragment_query)
                fragment_sql, fragment_params = compiler.compile(resolved)
            set_sqls.append(f"{column_sql} = {fragment_sql}")
            set_params.extend(fragment_params)
            if (
                self._update_changes_only
                and expression is not None
                and db_column.startswith("field_")
            ):
                # The stored value went through the column type on write (e.g.
                # a numeric column rounded it to its scale), so the calculated
                # value must be cast to the column type or the comparison
                # would report unrounded values as changed on every
                # recalculation. During a type conversion the model field no
                # longer matches the physical column, in which case both sides
                # are compared as text: at worst that reports the row as
                # changed, which a conversion makes true anyway.
                target_field = self._model._meta.get_field(db_column)
                if _same_db_type(expression, target_field, connection):
                    column_db_type = target_field.db_type(connection)
                    guard_sqls.append(
                        f"{table_name}.{column_sql} IS DISTINCT FROM "
                        f"(({fragment_sql}))::{column_db_type}"
                    )
                else:
                    guard_sqls.append(
                        f"({table_name}.{column_sql})::text IS DISTINCT FROM "
                        f"(({fragment_sql}))::text"
                    )
                guard_params.extend(fragment_params)

        where_sqls = [
            f"{table_name}.{quote_name('id')} = {quote_name(group_alias)}."
            f"{quote_name('id')}"
            for group_alias in self._groups.keys()
        ]
        if guard_sqls:
            where_sqls.append("(" + " OR ".join(guard_sqls) + ")")

        # All identifiers are quoted via connection.ops.quote_name and all
        # values are passed as query parameters.
        sql = (
            f"UPDATE {table_name} SET "  # noqa: S608
            + ", ".join(set_sqls)
            + " FROM "
            + ", ".join(group_sqls)
            + " WHERE "
            + " AND ".join(where_sqls)
            + f" RETURNING {table_name}.{quote_name('id')}"
        )
        return sql, [*set_params, *group_params, *guard_params]
