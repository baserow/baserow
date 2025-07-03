"""
Handler and utils for search data management.

Search data table aggregates per-row per-field search data within a workspace. While
new workspace/tables will use this by default, deployments that are running for some
time already, may still use old way of keeping search data by maintaining per-field tsv
columns in each user data table. Search data management must be aware of this, and
migrate each table when it's feasible, ideally before/during first modification.

This means some tables may be considered as 'legacy' in context of search, but this
state should be temporary, and they will be migrated to search data tables eventually.

"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Iterable, List
from uuid import uuid4

from django.conf import settings
from django.db import connection, router, transaction
from django.db.models import (
    Expression,
    F,
    Func,
    IntegerField,
    Model,
    Q,
    QuerySet,
    TextField,
    Value,
)
from django.db.models.functions import Now
from django.utils.encoding import force_str

from django_cte import With
from loguru import logger
from opentelemetry import trace

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.field_filters import FILTER_TYPE_OR, FilterBuilder
from baserow.contrib.database.search.expressions import LocalisedSearchVector
from baserow.contrib.database.search.models import (
    AbstractSearchValue,
    PendingSearchValueUpdate,
    get_search_indexes,
)
from baserow.contrib.database.search.regexes import (
    RE_ONE_OR_MORE_WHITESPACE,
    RE_REMOVE_ALL_PUNCTUATION_ALREADY_REMOVED_FROM_TSVS_FOR_QUERY,
    RE_REMOVE_NON_SEARCHABLE_PUNCTUATION_FROM_TSVECTOR_DATA,
)
from baserow.contrib.database.search.search_bulder import SearchQuery
from baserow.contrib.database.search.tasks import schedule_search_data_update
from baserow.core.psycopg import sql
from baserow.core.telemetry.utils import baserow_trace_methods

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.table.models import Table

tracer = trace.get_tracer(__name__)


class SearchMode(str, Enum):
    # Use this mode to search rows using LIKE operators against each
    # `FieldType`, and return an accurate `count` in the response.
    # This method is slow after a few thousand rows and dozens of fields.
    COMPAT = "compat"

    # Use this mode to search rows using Postgres full-text search against
    # each `FieldType`, and provide a `count` in the response. This
    # method is much faster as tables grow in size.
    FT_WITH_COUNT = "full-text-with-count"


ALL_SEARCH_MODES = [getattr(mode, "value") for mode in SearchMode]


class SearchHandler(
    metaclass=baserow_trace_methods(
        tracer, exclude=["full_text_enabled", "search_config"]
    )
):
    @classmethod
    def get_search_table_model(cls, workspace_id: int) -> "AbstractSearchValue":
        """
        Generates SearchTable model
        :param workspace_id: The ID of the workspace for which the search table
            model is being generated.
        :return: A dynamically generated model class that represents the search table
            for the specified workspace.
        """

        from baserow.contrib.database.table.models import GeneratedModelAppsProxy

        app_label = "database_search"
        table_name = f"search_data_workspace_{workspace_id}"
        model_name = f"SearchDataWorkspace{workspace_id}"

        baserow_models = {}
        apps = GeneratedModelAppsProxy(baserow_models, app_label)
        meta = type(
            "Meta",
            (),
            {
                "apps": apps,
                "managed": True,  # manually managed by Baserow
                "db_table": table_name,
                "app_label": app_label,
                "indexes": get_search_indexes(workspace_id),
            },
        )

        def __str__(self):
            return model_name

        attrs = {
            "Meta": meta,
            "__module__": "database.models",
            "_generated_table_model": True,
            "baserow_workspace_id": workspace_id,
            "baserow_models": baserow_models,
            "parent": workspace_id,
            "__str__": __str__,
        }

        model = type(
            model_name,
            (
                AbstractSearchValue,
                Model,
            ),
            attrs,
        )
        return model

    @classmethod
    def search_in_table(
        cls,
        queryset: QuerySet,
        sanitized_search: str,
        fields: List["Field"],
    ) -> QuerySet:
        """
        Searches in the provided queryset looking for the provided sanitized search
        string in the provided fields:

        If the field search version is V1, it uses the existing tsvector columns to
        filter the queryset. If the field search version is V2, it uses a CTE to filter
        the queryset based on the search values in the search table.

        :param queryset: The queryset to search in.
        :param sanitized_search: The sanitized search string to use for searching.
        :param fields: The list of fields to search in. All the fields must be
            searchable and be in the same table as the queryset.
        :return: A filtered queryset containing the rows that match the search criteria.
        """

        search_query = SearchQuery(
            sanitized_search,
            search_type="raw",
            config=SearchHandler.search_config(),
        )

        filter_builder = FilterBuilder(filter_type=FILTER_TYPE_OR)

        cls._add_exact_id_search(filter_builder, sanitized_search)
        filtered_queryset = filter_builder.apply_to_queryset(queryset)

        search_table = cls.get_search_table_model(fields[0].table.database.workspace_id)
        cte = With(
            search_table.objects.filter(
                field_id__in=[field.id for field in fields], value=search_query
            ),
            name=f"search_{uuid4().hex}",
        )
        filtered_queryset = cte.join(filtered_queryset, id=cte.col.row_id).with_cte(cte)

        return filtered_queryset

    @classmethod
    def _add_exact_id_search(cls, filter_builder, input_search):
        try:
            # Search for the row ID if the `input_search` can be cast to an integer.
            stripped_input = input_search.strip()
            # int('0006') will produce 6 but we don't want 0006 to match row 6!
            if not stripped_input.startswith("0"):
                filter_builder.filter(Q(id=int(stripped_input)))
        except ValueError:
            pass

    @classmethod
    def create_workspace_search_table(cls, workspace_id: int):
        search_table = cls.get_search_table_model(workspace_id)
        with safe_django_schema_editor() as se:
            se.create_model(search_table)

        return search_table

    @classmethod
    def delete_workspace_search_table(cls, workspace_id: int):
        search_table = cls.get_search_table_model(workspace_id)
        query = sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
            sql.Identifier(search_table._meta.db_table)
        )
        with connection.cursor() as c:
            c.execute(query)

    @classmethod
    def special_char_tokenizer(cls, expression: Expression) -> Func:
        """
        Due to the fact that we can't create custom postgres full text search
        dictionaries on behalf of our
        users (which would really super-user privileges), we will force some
        tokenization behaviour by changing certain specific characters to spaces.
        Emails:
          With input "peter@baserow.com" this will result in tokens:
          1. peter
          2. baserow.io
        URLs
          With input "https://baserow.io/jobs/" this will result in tokens:
          1. https
          2. baserow.io
          3. jobs
        Dates
          With input "06/13/2023" or "06-13-2023" this will result in tokens:
          1. 06
          2. 13
          3. 2023
        Text with hyphens
          Any text with a hyphen is split into tokens, whether the hyphen is
          in the beginning, middle or end of the string. This is to match
          Postgres' removal of hyphens in the simple dictionary.

        :param expression: The Expression which a `FieldType.get_search_expression`
            which has called this classmethod so that we convert the Expression's text
            into specific tokens.
        :return: Func
        """

        return Func(
            expression,
            Value(
                RE_REMOVE_NON_SEARCHABLE_PUNCTUATION_FROM_TSVECTOR_DATA.pattern,
            ),
            Value(" "),
            Value("g"),
            function="regexp_replace",
            output_field=TextField(),
        )

    @classmethod
    def full_text_enabled(cls) -> bool:
        return settings.USE_PG_FULLTEXT_SEARCH

    @classmethod
    def search_config(cls) -> str:
        return settings.PG_SEARCH_CONFIG

    @classmethod
    def get_default_search_mode_for_table(cls, table: "Table") -> str:
        # Template table indexes are not created to save space so we can only use compat
        # search here.
        if table.database.workspace.has_template():
            return SearchMode.COMPAT

        search_mode = settings.DEFAULT_SEARCH_MODE
        if table.tsvectors_are_supported:
            search_mode = SearchMode.FT_WITH_COUNT

        return search_mode

    @classmethod
    def escape_query(cls, text: str) -> str:
        """
        Responsible for sanitizing an individual token in an API consumer's query.

        This method should match the frontend equivalent
        convertStringToMatchBackendTsvectorData.

        The steps are as follows:
            1. The text is forced to a string with `force_str`.
            2. `RE_REMOVE_ALL_PUNCTUATION_ALREADY_REMOVED_FROM_TSVS_FOR_QUERY`
                strips characters which Postgres will natively throw away in
                `RE_REMOVE_NON_SEARCHABLE_PUNCTUATION_FROM_TSVECTOR_DATA`.
            3. `RE_ONE_OR_MORE_WHITESPACE` strips excess spaces.

        :param text: The raw unsanitized token in a larger API consumer's query.
        :return: str
        """

        text = force_str(text)
        text = RE_REMOVE_ALL_PUNCTUATION_ALREADY_REMOVED_FROM_TSVS_FOR_QUERY.sub(
            " ", text
        )
        text = RE_ONE_OR_MORE_WHITESPACE.sub(" ", text)
        text = text.strip()
        return text

    @classmethod
    def escape_postgres_query(cls, text, per_token_wildcard: bool = False) -> str:
        """
        Responsible for taking the raw query from the API consumer and
        sanitizing it for Postgres to consume.

        :param text: The raw unsanitized query from the API consumer.
        :param per_token_wildcard: Determines whether we add the `:*` wildcard to
            each token, or just at the end of the query. Per token is more flexible,
            but is problematic for Baserow's frontend, so we only add the wildcard at
            the end of the whole query.
        :return: str
        """

        per_token_suffix = ":*" if per_token_wildcard else ""

        escaped_query = " <-> ".join(
            "$${0}$${1}".format(word, per_token_suffix)
            for word in cls.escape_query(text).split()
        )
        if not per_token_wildcard and escaped_query:
            return f"{escaped_query}:*"
        else:
            return escaped_query

    @classmethod
    def after_field_created(cls, field: "Field", skip_search_updates: bool = False):
        """
        :param field: The Baserow field which was created in this table.
        :param skip_search_updates: Whether to update search data after.
        :return: None
        """

        cls.schedule_search_data_update(field.table, fields=[field])

    @classmethod
    def after_field_moved_between_tables(
        cls, moved_field: "Field", original_table_id: int
    ):
        cls.schedule_search_data_update(moved_field.table, fields=[moved_field])

    @classmethod
    def schedule_search_data_update(
        cls,
        table: "Table",
        fields: list["Field"] | None = None,
        row_ids: list[int] | None = None,
    ):
        """
        Called when field values for a table have been changed or created. Not called
        when a row is deleted as we don't care and don't want to do anything for the
        search indexes.

        :param table: The table a field value has been created or updated in.
        :param updated_fields: If only some fields have had values
            changed then the search vector update can be optimized by providing those
            here.
        """

        field_ids = None
        if fields:
            field_ids = [f.id for f in fields]

        schedule_search_data_update.delay(table.id, field_ids, row_ids)

    @classmethod
    def delete_search_data(
        cls, table: "Table", field_ids: List[int], row_ids: List[int] | None = None
    ):
        """
        Deletes search data for the given table, fields and row ids.
        If row_ids is None, all rows will be deleted for the given fields.
        """

        workspace_id = table.database.workspace_id
        search_model = cls.get_search_table_model(workspace_id)

        # Delete pending updates first
        q = Q(field_id__in=field_ids)
        if row_ids is not None:
            q &= Q(row_id__in=row_ids)
        cls._delete_pending_updates(q)

        # Now delete the actual search data
        qs = search_model.objects
        if row_ids is not None:
            qs = qs.filter(table_id=table.id, row_id__in=row_ids)

        qs.filter(field_id__in=field_ids).order_by("id")._raw_delete(
            using=router.db_for_write(search_model)
        )

    @classmethod
    def add_pending_search_update(
        cls,
        table: "Table",
        field_ids: List[int] | None = None,
        row_ids: List[int] | None = None,
    ):
        searchable_field_ids = {
            f.id for f in table.get_model().get_searchable_fields(include_trash=True)
        }
        if field_ids is None:
            field_ids = searchable_field_ids
        else:
            field_ids = [fid for fid in set(field_ids) if fid in searchable_field_ids]

        ordered_field_ids = sorted(field_ids)
        ordered_row_ids = sorted(set(row_ids or [None]))
        PendingSearchValueUpdate.objects.bulk_create(
            [
                PendingSearchValueUpdate(
                    table=table,
                    field_id=field_id,
                    row_id=row_id,
                )
                for field_id in ordered_field_ids
                for row_id in ordered_row_ids
            ],
            ignore_conflicts=True,
            batch_size=2500,
        )

    @classmethod
    def initialize_search_data_for_fields(cls, table: "Table"):
        """
        TODO
        """

        model = table.get_model()
        fields_to_initialze = [
            fo["field"]
            for fo in model.get_field_objects(include_trash=True)
            if fo["field"].search_data_initialized_at is None
        ]

        initialized_field_ids = []
        for field in fields_to_initialze:
            with transaction.atomic():
                # Process each field separately to ensure progress on large tables.
                cls.update_search_data(table, field_ids=[field.id])

                field.search_data_initialized_at = datetime.now(tz=timezone.utc)
                field.save(update_fields=["search_data_initialized_at"])
                initialized_field_ids.append(field.id)

        # Clean up any other pending updates for these fields, since we just
        # initialized the search data for it.
        cls._delete_pending_updates(Q(field_id__in=initialized_field_ids))

    @classmethod
    def update_search_data(
        cls,
        table: "Table",
        field_ids: Iterable[int] | None = None,
        row_ids: Iterable[int] | None = None,
    ):
        """
        TODO field_ids = None means all searchable fields (including trashed). row_ids =
        None means all rows (including trashed). If both are None, all rows for all
        fields will be updated, but be careful with big tables.
        """

        model = table.get_model()
        searchable_fields = {
            f.id: f for f in model.get_searchable_fields(include_trash=True)
        }
        qs: QuerySet = model.objects_and_trash.all()
        if row_ids is not None:
            qs = qs.filter(id__in=list(row_ids))

        if field_ids is None:
            field_ids = list(searchable_fields.keys())
        else:
            field_ids = [f_id for f_id in set(field_ids) if f_id in searchable_fields]

        if not field_ids:
            logger.debug(
                f"No searchable fields found for table {table.id} with fields "
                f"{field_ids}. No updates will be made."
            )
            return

        workspace_id = table.database.workspace_id
        search_model = cls.get_search_table_model(workspace_id)
        field_querysets = []

        for field_id in field_ids:
            field = searchable_fields[field_id]
            field_qs = qs.all()

            search_expr: Expression = field.get_type().get_search_expression(
                field, field_qs
            )
            field_querysets.append(
                field_qs.filter(**{f"{field.db_column}__isnull": False})
                .annotate(
                    row_id=F("id"),
                    field_id=Value(field_id, output_field=IntegerField()),
                    value=LocalisedSearchVector(search_expr),
                    timestamp=Now(),
                )
                .values("field_id", "row_id", "value", "timestamp")
            )

        union_qs, *rest = field_querysets
        if rest:
            union_qs = union_qs.union(*rest)

        sql, params = union_qs.order_by("field_id", "row_id").query.sql_with_params()

        with connection.cursor() as cursor:
            raw_sql = f"""
                INSERT INTO {search_model._meta.db_table} (field_id, row_id, value, updated_on)
                {sql}
                ON CONFLICT (field_id, row_id)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_on = EXCLUDED.updated_on;
            """  # nosec B608
            cursor.execute(raw_sql, params)

    @classmethod
    def _delete_pending_updates(cls, q: Q):
        """
        Deletes pending search value updates based on the provided Q object. This is a
        helper method to avoid code duplication in the process_search_data_updates
        method.
        """

        PendingSearchValueUpdate.objects.filter(q).order_by("id")._raw_delete(
            using=router.db_for_write(PendingSearchValueUpdate)
        )

    @classmethod
    def process_search_data_updates(cls, table: "Table"):
        """
        Process PendingSearchValueUpdate entries
        """

        def next_single_row_batch(count: int) -> QuerySet[PendingSearchValueUpdate]:
            return (
                PendingSearchValueUpdate.objects.filter(
                    table=table, row_id__isnull=False
                )
                .select_for_update(of=("self",), skip_locked=True)
                .order_by("field_id", "row_id")[:count]
            )

        @transaction.atomic
        def process_batch(num_updates=10):
            processed = 0

            # Handle full-field updates (row_id=None) before row-specific updates
            full_table_updates = PendingSearchValueUpdate.objects.filter(
                table=table, row_id=None
            ).select_for_update(of=("self",), skip_locked=True)[:num_updates]

            for update in full_table_updates:
                cls.update_search_data(table, field_ids=[update.field_id])
                cls._delete_pending_updates(Q(field_id=update.field_id))

                processed += 1
                if processed >= num_updates:
                    break

            # Now handle single-row updates, grouping them for efficiency
            while processed < num_updates:
                single_rows_updates = next_single_row_batch(2500)

                if not single_rows_updates:
                    break

                field_ids, row_ids = zip(
                    *[(u.field_id, u.row_id) for u in single_rows_updates]
                )

                cls.update_search_data(table, field_ids, row_ids)
                single_rows_updates.order_by("id")._raw_delete(
                    using=router.db_for_write(PendingSearchValueUpdate)
                )

                processed += 1

            return processed

        while True:
            count = 10
            processed = process_batch(count)
            if processed < count:
                break
