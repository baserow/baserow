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

from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, List
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.search import SearchQuery
from django.db import IntegrityError, ProgrammingError, connection, router, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import (
    DateTimeField,
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
from django.db.models.sql.constants import LOUTER
from django.utils.encoding import force_str

from django_cte import With
from loguru import logger
from opentelemetry import trace

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.field_filters import FILTER_TYPE_OR, FilterBuilder
from baserow.contrib.database.fields.models import Field
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
from baserow.contrib.database.search.tasks import (
    delete_search_data,
    schedule_update_search_data,
)
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.core.psycopg import errors
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.utils import to_camel_case

if TYPE_CHECKING:
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


@lru_cache(maxsize=1024)
def _workspace_search_table_exists(workspace_id: int) -> bool:
    """
    Determines if the search table exists for the given workspace ID.
    This is a cached version of the _workspace_search_table_exists method to avoid
    repeated database queries for the same workspace.

    :param workspace_id: The ID of the workspace to check.
    :return: True if the search table exists, False otherwise.
    """

    search_table_name = SearchHandler.get_workspace_search_table_name(workspace_id)
    with connection.cursor() as cursor:
        raw_sql = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema()
                AND table_name = %s
            )
        """  # nosec B608
        cursor.execute(raw_sql, [search_table_name])
        return cursor.fetchone()[0]


@lru_cache(maxsize=1024)
def _generate_search_table_model(
    workspace_id: int, managed=False
) -> "AbstractSearchValue":
    """
    Generates the search table model for the given workspace ID. This model is used to
    store search values for each row in the workspace's tables.

    :param workspace_id: The ID of the workspace for which the search table model is
        being generated.
    :param managed: This flag should be set to True only when the database table needs
        to be created or dropped, False otherwise.
    :return: A dynamically generated model class that represents the search table for
        the specified workspace.
    :raises ValueError: If the workspace_id is not provided.
    """

    from baserow.contrib.database.table.models import GeneratedModelAppsProxy

    if not workspace_id:
        raise ValueError(
            "Workspace ID must be provided to generate a search table model."
        )

    app_label = "database_search"
    table_name = SearchHandler.get_workspace_search_table_name(workspace_id)
    model_name = to_camel_case(table_name)

    baserow_models = {}
    apps = GeneratedModelAppsProxy(baserow_models, app_label)
    meta = type(
        "Meta",
        (),
        {
            "apps": apps,
            "managed": managed,
            "db_table": table_name,
            "app_label": app_label,
            "indexes": get_search_indexes(workspace_id),
            "unique_together": [("field_id", "row_id")],
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


class SearchDatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    sql_delete_table = "DROP TABLE IF EXISTS %(table)s CASCADE"


class SearchHandler(
    metaclass=baserow_trace_methods(
        tracer, exclude=["full_text_enabled", "search_config"]
    )
):
    @classmethod
    def get_workspace_search_table_name(cls, workspace_id: int) -> str:
        """
        Returns the name of the search table for the given workspace ID.

        :param workspace_id: The ID of the workspace for which the search table name is
            being generated.
        :return: The name of the search table for the specified workspace.
        """

        return f"database_search_workspace_{workspace_id}_data"

    @classmethod
    def get_workspace_search_table_model(
        cls, workspace_id: int, managed: bool = False
    ) -> "AbstractSearchValue":
        """
        Generates the workspace search table model.

        :param workspace_id: The ID of the workspace for which the search table model is
            being generated.
        :param managed: This flag should be set to True only when the needs to be
            created for the first time, False otherwise.
        :return: A dynamically generated model class that represents the search table
            for the specified workspace.
        """

        return _generate_search_table_model(workspace_id, managed=managed)

    @classmethod
    def full_text_search_in_table(
        cls,
        queryset: QuerySet,
        input_search: str,
        fields: List["Field"],
    ) -> QuerySet:
        """
        Searches in the provided queryset looking for the provided sanitized search
        string in the provided fields:

        If the field search version is V1, it uses the existing tsvector columns to
        filter the queryset. If the field search version is V2, it uses a CTE to filter
        the queryset based on the search values in the search table.

        :param queryset: The queryset to search in.
        :param input_search: The search string to sanitize and look for in the fields.
        :param fields: The list of fields to search in. All the fields must be
            searchable and be in the same table as the queryset.
        :return: A filtered queryset containing the rows that match the search criteria.
        """

        sanitized_search = cls.escape_postgres_query(input_search)

        if len(sanitized_search) == 0:
            return queryset.filter(id__in=[])

        search_query = SearchQuery(
            sanitized_search,
            search_type="raw",
            config=SearchHandler.search_config(),
        )

        search_table = cls.get_workspace_search_table_model(
            fields[0].table.database.workspace_id
        )
        cte = With(
            search_table.objects.filter(
                field_id__in=[field.id for field in fields], value=search_query
            )
            .values("row_id")
            .distinct(),
            name=f"search_{uuid4().hex}",
        )
        search_queryset = (
            cte.join(queryset, id=cte.col.row_id, _join_type=LOUTER)
            .with_cte(cte)
            .annotate(match_search=cte.col.row_id)
        )

        filter_builder = FilterBuilder(filter_type=FILTER_TYPE_OR)
        filter_builder.filter(Q(match_search__isnull=False))
        cls.add_exact_id_search(filter_builder, input_search)

        return filter_builder.apply_to_queryset(search_queryset)

    @classmethod
    def add_exact_id_search(cls, filter_builder, input_search):
        try:
            # Search for the row ID if the `input_search` can be cast to an integer.
            stripped_input = input_search.strip()
            # int('0006') will produce 6 but we don't want 0006 to match row 6!
            if not stripped_input.startswith("0"):
                filter_builder.filter(Q(id=int(stripped_input)))
        except ValueError:
            pass

    @classmethod
    def can_use_full_text_search(cls, table: "Table") -> bool:
        """
        Determines if full-text search can be used for the given table, by checking
        if the search table exists for the workspace of the table and if full-text
        search is enabled in the settings.

        :param table: The table for which to check if full-text search can be used.
        """

        if not cls.full_text_enabled():
            return False

        workspace = table.database.workspace
        return cls.workspace_search_table_exists(workspace.id)

    @classmethod
    def workspace_search_table_exists(cls, workspace_id: int) -> bool:
        """
        Determines if the search table exists for the given workspace ID. This is a
        cached version of the _workspace_search_table_exists method to avoid repeated
        database queries for the same workspace.

        :param workspace_id: The ID of the workspace to check.
        :return: True if the search table exists, False otherwise. The result is cached
            to improve performance.
        """

        return _workspace_search_table_exists(workspace_id)

    @classmethod
    def create_workspace_search_table_if_not_exists(cls, workspace_id: int):
        """
        Creates the workspace search table if it does not already exist. Since multiple
        different tables in the same workspace can try to create the search table at the
        same time, ensure only one of them will actually create it with the other ones
        waiting for the lock to be released.

        :param workspace_id: The ID of the workspace for which the search table should
            be
        """

        if _workspace_search_table_exists(workspace_id):
            return

        # Django creates indexes only when the model is managed.
        search_table_model = cls.get_workspace_search_table_model(
            workspace_id, managed=True
        )

        try:
            with transaction.atomic():
                with connection.schema_editor() as se:
                    se.create_model(search_table_model)
        except ProgrammingError as exc:
            if isinstance(
                exc.__cause__, (errors.DuplicateTable, errors.DuplicateObject)
            ):
                # If the table already exists, we can safely ignore the error.
                logger.debug(
                    f"Search table for workspace {workspace_id} already exists."
                )
            else:
                raise exc
        except IntegrityError as exc:
            if isinstance(exc.__cause__, errors.UniqueViolation):
                logger.debug(
                    f"Race condition: sequence or object for workspace "
                    f"{workspace_id} already exists (UniqueViolation)."
                )
            else:
                raise
        _workspace_search_table_exists.cache_clear()

    @classmethod
    def delete_workspace_search_table_if_exists(cls, workspace_id: int):
        """
        Drops the workspace search table if it exists. This is useful for cleaning up
        the search table when a workspace is deleted or when the search feature is no
        longer needed.

        :param workspace_id: The ID of the workspace for which the search table should
        """

        search_table = cls.get_workspace_search_table_model(workspace_id, managed=True)
        with safe_django_schema_editor(classes=[SearchDatabaseSchemaEditor]) as se:
            se.delete_model(search_table)

        _workspace_search_table_exists.cache_clear()

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
        return settings.PG_FULLTEXT_SEARCH_ENABLED

    @classmethod
    def search_config(cls) -> str:
        return settings.PG_FULLTEXT_SEARCH_CONFIG

    @classmethod
    def get_default_search_mode_for_table(cls, table: "Table") -> str:
        return (
            SearchMode.FT_WITH_COUNT
            if cls.can_use_full_text_search(table)
            else SearchMode.COMPAT
        )

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

        cls.schedule_update_search_data(field.table, fields=[field])

    @classmethod
    def all_fields_values_changed_or_created(cls, fields: Iterable["Field"]):
        """
        Called when many fields values have been changed or created.
        Please note that fields might belong to different tables, so
        this method will schedule updates for each table separately.

        :param fields: The fields that have had their values changed or created.
        """

        if not fields:
            return

        fields_per_table = defaultdict(list)
        for field in fields:
            fields_per_table[field.table].append(field)

        for table, table_fields in fields_per_table.items():
            cls.schedule_update_search_data(table, fields=table_fields)

    @classmethod
    def after_field_moved_between_tables(
        cls, moved_field: "Field", original_table_id: int
    ):
        cls.schedule_update_search_data(moved_field.table, fields=[moved_field])

    @classmethod
    def schedule_update_search_data(
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
        :param fields: Optional list of fields that have been changed or created. If
            None, all fields in the table will be considered.
        :param row_ids: Optional list of row IDs that have been changed or created. If
            None, all rows in the table will be considered.
        """

        field_ids = None
        if fields:
            field_ids = [f.id for f in fields]

        transaction.on_commit(
            lambda: schedule_update_search_data.delay(table.id, field_ids, row_ids)
        )

    @classmethod
    def schedule_delete_search_data(
        cls,
        table: "Table",
        field_ids: List[int] | None = None,
        row_ids: List[int] | None = None,
    ):
        """
        Schedules the deletion of search data for the given table, fields and row ids.
        If field_ids is None, all fields will be deleted for the given rows or entire
        table. If row_ids is None, all rows will be deleted for the given fields or
        entire table.

        :param table: The table for which the search data should be deleted.
        :param field_ids: Optional list of field IDs to delete search data for. If None,
            all fields will be considered.
        :param row_ids: Optional list of row IDs to delete search data for. If None,
            all rows will be considered.
        """

        # extract the field IDs before the commit to ensure we have the correct IDs
        table_field_ids = [
            f.id for f in table.get_model().get_fields(include_trash=True)
        ]
        if field_ids is None:
            field_ids = table_field_ids
        else:
            field_ids = [fid for fid in set(field_ids) if fid in table_field_ids]

        workspace_id = table.database.workspace_id
        transaction.on_commit(
            lambda: delete_search_data.delay(workspace_id, field_ids, row_ids)
        )

    @classmethod
    def delete_search_data(
        cls,
        workspace_id: int,
        field_ids: List[int],
        row_ids: List[int] | None = None,
    ):
        """
        Deletes search data for the specified fields in a workspace and, optionally, for
        specific rows. This method is used when rows, fields or tables are permanently
        deleted or when search data needs to be cleared. At this point, all the original
        resources might have been permanently deleted from the database, so this method
        cannot verify if the IDs are valid or not, but it will took them for granted and
        delete the search data for them.

        :param workspace_id: The ID of the workspace for which to delete search data.
        :param field_ids: List of field IDs to delete search data for.
        :param row_ids: Optional list of row IDs to delete search data for. If None, all
            rows will be considered for deletion.
        """

        if not cls.workspace_search_table_exists(workspace_id):
            return

        search_model = cls.get_workspace_search_table_model(workspace_id)

        # Delete any potential remaining pending update
        q = Q(field_id__in=field_ids)
        if row_ids is not None:
            q &= Q(row_id__in=row_ids)
        cls._delete_pending_updates(q)

        # And now delete the actual search data
        qs = search_model.objects.filter(field_id__in=field_ids)
        if row_ids is not None:
            qs = qs.filter(row_id__in=row_ids)
        qs._raw_delete(using=router.db_for_write(search_model))

    @classmethod
    def queue_pending_search_update(
        cls,
        table: "Table",
        field_ids: List[int] | None = None,
        row_ids: List[int] | None = None,
    ):
        """
        Queues a pending search value update for the given table, fields and row ids.
        If field_ids is None, all searchable fields will be considered.
        If row_ids is None, all rows will be considered.
        Because PendingSearchValueUpdate has a unique constraint on (field_id, row_id),
        this method will only create new entries for combinations that do not already
        exist in the PendingSearchValueUpdate table.

        :param table: The table for which the search value update should be queued.
        :param field_ids: Optional list of field IDs to queue search value updates for.
            If None, all searchable fields will be considered.
        :param row_ids: Optional list of row IDs to queue search value updates for.
            If None, all rows will be considered.
        """

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
    def initialize_missing_search_data(cls, table: "Table"):
        """
        Queues a pending update for all fields in the given table that have not yet
        had their search data initialized.

        :param table: The table for which the search data should be initialized.
        :raises TableDoesNotExist: If the table does not exist.
        """

        fields_to_initialize = Field.objects.filter(
            table=table,
            search_data_initialized_at__isnull=True,
        ).order_by("id")

        if not fields_to_initialize:
            return  # all fields already initializedl

        field_ids = []
        now = datetime.now(tz=timezone.utc)
        for field in fields_to_initialize:
            field_ids.append(field.id)
            field.search_data_initialized_at = now

        with transaction.atomic():
            Field.objects.bulk_update(
                fields_to_initialize, ["search_data_initialized_at"]
            )
            cls.queue_pending_search_update(table, field_ids=field_ids)
        # Ensure table models can see the updated field attributes to avoid
        # rescheduling tasks for the same fields.
        invalidate_table_in_model_cache(table.id)

    @classmethod
    def update_search_data(
        cls,
        table: "Table",
        field_ids: Iterable[int] | None = None,
        row_ids: Iterable[int] | None = None,
    ):
        """
        Updates the search data for the given table, fields and row ids.
        If field_ids is None, all searchable fields will be updated.
        If row_ids is None, all rows will be updated.

        :param table: The table for which the search data should be updated.
        :param field_ids: Optional list of field IDs to update search data for. If None,
            all searchable fields will be considered.
        :param row_ids: Optional list of row IDs to update search data for. If None,
            all rows will be considered.
        """

        model = table.get_model()
        qs: QuerySet = model.objects_and_trash.all()
        if row_ids is not None:
            qs = qs.filter(id__in=list(row_ids))

        searchable_fields = {
            f.id: f for f in model.get_searchable_fields(include_trash=True)
        }
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
        search_model = cls.get_workspace_search_table_model(workspace_id)
        field_querysets = []

        now = datetime.now(tz=timezone.utc)
        for field_id in field_ids:
            field = searchable_fields[field_id]
            field_qs = qs.all()

            search_expr: Expression = field.get_type().get_search_expression(
                field, field_qs
            )
            field_qs = field_qs.annotate(
                row_id=F("id"),
                field_id=Value(field_id, output_field=IntegerField()),
                value=LocalisedSearchVector(search_expr),
                timestamp=Value(now, output_field=DateTimeField()),
            )
            field_querysets.append(
                field_qs.values("field_id", "row_id", "value", "timestamp")
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

        with transaction.atomic():
            # Even if slower, enforce order and lock rows to prevent potential deadlocks
            # If updates are already locked, they will be removed by the other process
            PendingSearchValueUpdate.objects.filter(q).select_for_update(
                of=("self",), skip_locked=True
            ).order_by("field_id", "row_id")._raw_delete(
                using=router.db_for_write(PendingSearchValueUpdate)
            )

    @classmethod
    def process_search_data_updates(cls, table: "Table"):
        """
        Process pending search updates for a given table in two phases:

        1. Full‐field updates (row_id=None): rebuilds the search index for an entire
           field.
        2. Row‐specific updates: groups updates for remaining fields into batches and
           refreshes only affected cells.

        :param table: The Table whose pending search updates will be handled.
        """

        full_field_updates = (
            PendingSearchValueUpdate.objects.filter(table=table, row_id=None)
            .select_for_update(of=("self",), skip_locked=True)
            .order_by("field_id")
            .values_list("field_id", flat=True)
        )

        # First process full-field updates (row_id=None), removing any remaining
        # row-specific updates on the same field.
        last = False
        while not last:
            with transaction.atomic():
                batch_size = 5
                field_ids = list(full_field_updates[:batch_size])
                if not field_ids:
                    break
                elif len(field_ids) < batch_size:
                    last = True

                cls._delete_pending_updates(Q(field_id__in=field_ids))
                cls.update_search_data(table, field_ids=field_ids)

        def _fetch_next_batch() -> QuerySet[PendingSearchValueUpdate]:
            return (
                PendingSearchValueUpdate.objects.filter(
                    table=table, row_id__isnull=False
                )
                .select_for_update(of=("self",), skip_locked=True)
                .order_by("field_id", "row_id")
            )

        # Now handle single-cells updates, grouping them for efficiency
        last = False
        while not last:
            with transaction.atomic():
                batch_size = 1000
                pending_cells_updates = _fetch_next_batch()[:batch_size]
                if len(pending_cells_updates) < batch_size:
                    last = True

                field_ids, row_ids, update_ids = set(), set(), []
                for cell_update in pending_cells_updates:
                    field_ids.add(cell_update.field_id)
                    row_ids.add(cell_update.row_id)
                    update_ids.append(cell_update.id)

                if update_ids:
                    cls.update_search_data(
                        table, field_ids=list(field_ids), row_ids=list(row_ids)
                    )
                    cls._delete_pending_updates(Q(id__in=update_ids))
