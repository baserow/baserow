from abc import ABC
from typing import TYPE_CHECKING, Self

from django.contrib.postgres.search import SearchQuery
from django.db.models import BooleanField, F, Q, QuerySet
from django.db.models.expressions import RawSQL
from django.db.models.sql.constants import LOUTER

from django_cte import CTEQuerySet, With

from baserow.contrib.database.search.models import AbstractSearchValue

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel, Table


class BaseSearchTerm(ABC):
    term: str

    def get_table_name(self) -> str:
        ...

    def get_query(self) -> QuerySet:
        ...

    def add_to_queryset(
        self, queryset: CTEQuerySet, alias: str | None = None
    ) -> CTEQuerySet:
        ...

    def get_cte(self, alias: str | None = None) -> With:
        # We use "raw" as we can't use XXX, so if someone had a cell for "cheese" and
        # searches for "chee", we need to be able to match it with "$$chee$$:*"

        cte = With(
            self.get_query(),
            name=alias,
        )
        return cte


class TextSearchTerm(BaseSearchTerm):
    """
    A helper class to construct search query filters for a searched term.
    """

    def __init__(
        self,
        search_model: "AbstractSearchValue",
        term: str,
        field_ids: list[int],
    ):
        self.search_model = search_model
        self.term = term
        self.field_ids = field_ids

    def get_cte(self, alias: str | None = None) -> With:
        cte = With(
            self.get_query(),
            name=alias,
        )
        return cte

    def get_query(self) -> QuerySet:
        from .handler import SearchHandler

        sanitized_search = SearchHandler.escape_postgres_query(self.term)

        # We use "raw" as we can't use XXX, so if someone had a cell for "cheese" and
        # searches for "chee", we need to be able to match it with "$$chee$$:*"
        search_query = SearchQuery(
            sanitized_search,
            search_type="raw",
            config=SearchHandler.search_config(),
        )

        return (
            self.search_model.objects.filter(
                value=search_query, field_id__in=self.field_ids
            )
            .only("row_id")
            .order_by("row_id", "-updated_on")
            .distinct("row_id")
        )

    def add_to_queryset(
        self, queryset: CTEQuerySet, alias: str | None = None
    ) -> CTEQuerySet:
        cte = self.get_cte(alias)
        return cte.join(queryset, id=cte.col.row_id, _join_type=LOUTER).with_cte(cte)


class IDSearchTerm(BaseSearchTerm):
    def __init__(self, table: "Table", term: int):
        self.table = table
        self.model = table.get_model()
        self.term = term

    def get_table_name(self):
        return f"{self.model._meta.db_table}_with_id"

    def get_query(self) -> QuerySet:
        return (
            self.model.objects.filter(id=self.term).annotate(row_id=F("id")).only("id")
        )

    def add_to_queryset(
        self, queryset: CTEQuerySet, alias: str | None = None
    ) -> CTEQuerySet:
        cte = self.get_cte(alias)
        return cte.join(queryset, id=F("row_id"), _join_type=LOUTER).with_cte(cte)


class SearchBuilder:
    """
    Helper class to create a proper search query. It should be used as an entry point
    in building a query:

    # create a search builder to search a table
    >>> sb = SearchBuilder(table)
    # add term to be searched for
    >>> sb.add_term('some term')
    # generate queryset
    >>> queryset = sb.get_queryset()
    """

    def __init__(
        self,
        table: "Table",
        search_model: "AbstractSearchValue" = None,
        model: "GeneratedTableModel|None" = None,
    ):
        from .handler import SearchHandler

        self.table = table
        self.model = model or table.get_model()
        self.search_model = search_model or SearchHandler.get_search_table_model(
            table.database.workspace_id
        )
        self.fields = list(self.model.get_field_objects())
        self.row_id = None

        # search model to fields search
        self.related_searches: list[BaseSearchTerm] = []

    def add_row_id_search(self, potential_id_value: str):
        """
        Adds optional search by row id. Sometimes a search string consists of a number,
        which may point to a specific row id. Row IDs are not part of ts vectors, so
        we need to add additional query to get that row (without whole CTE overhead).

        :param potential_id_value: search string that may contain a number.
        :return:
        """

        try:
            if potential_id_value and not potential_id_value.startswith("0"):
                row_id = int(potential_id_value)
                id_term = IDSearchTerm(self.table, row_id)
                self._add_term(id_term)

        except (TypeError, ValueError):
            pass

    def add_term(self, term, field_ids: list[int] | None = None) -> Self:
        """
        Adds a term to search for fields requested.

        Search can be for all fields in the table, or to selected fields only.
        """

        sterm = self._build_term(term, field_ids)
        self._add_term(sterm)
        return self

    def _build_term(self, term: str, field_ids: list[int] | None = None):
        if not field_ids:
            field_ids = [f["field"].id for f in self.fields]
        return TextSearchTerm(self.search_model, term, field_ids)

    def _add_term(self, sterm: BaseSearchTerm):
        self.related_searches.append(sterm)

    def get_queryset(self, queryset: QuerySet | None = None) -> CTEQuerySet:
        """
        Returns a queryset that filters with search data table using fields
        that are used by the table.
        """

        from baserow.contrib.database.table.models import TableModelQuerySet

        if queryset is None:
            queryset = TableModelQuerySet(model=self.model)

        filter_queryset = []

        # queryset may contains some CTEs already
        try:
            existing_ctes_count = len(queryset.query._with_ctes)
        except AttributeError:
            existing_ctes_count = 0

        with_query = queryset.order_by("id")
        for idx, term in enumerate(self.related_searches):
            alias = f"cte_{idx + existing_ctes_count}"
            cte = term.get_cte(alias)
            filter_q = Q(id=cte.col.row_id)
            with_query = cte.join(with_query, filter_q, _join_type=LOUTER).with_cte(cte)
            filter_queryset.append(
                RawSQL(
                    f"{cte.name}.row_id IS NOT NULL",  # nosec B611
                    [],
                    output_field=BooleanField(),
                )
            )

        # this is outer join, so we need to remove empty row_id values
        if filter_queryset:
            with_query = with_query.filter(Q(*filter_queryset, _connector=Q.OR))

        return with_query
