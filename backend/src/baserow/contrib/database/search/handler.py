import math
import traceback
from enum import Enum
from typing import TYPE_CHECKING, List, NamedTuple, Optional, Type

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Expression, Func, Q, QuerySet, TextField, Value
from django.utils.encoding import force_str

from loguru import logger
from opentelemetry import trace
from redis.exceptions import LockNotOwnedError

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.search.expressions import LocalisedSearchVector
from baserow.contrib.database.search.regexes import (
    RE_ONE_OR_MORE_WHITESPACE,
    RE_REMOVE_ALL_PUNCTUATION_ALREADY_REMOVED_FROM_TSVS_FOR_QUERY,
    RE_REMOVE_NON_SEARCHABLE_PUNCTUATION_FROM_TSVECTOR_DATA,
)
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.table.constants import (
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
)
from baserow.core.psycopg import sql
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.utils import ChildProgressBuilder, exception_capturer

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.table.handler import TableForUpdate
    from baserow.contrib.database.table.models import GeneratedTableModel, Table

tracer = trace.get_tracer(__name__)


class SearchModes(str, Enum):
    # Use this mode to search rows using LIKE operators against each
    # `FieldType`, and return an accurate `count` in the response.
    # This method is slow after a few thousand rows and dozens of fields.
    MODE_COMPAT = "compat"

    # Use this mode to search rows using Postgres full-text search against
    # each `FieldType`, and provide a `count` in the response. This
    # method is much faster as tables grow in size.
    MODE_FT_WITH_COUNT = "full-text-with-count"


ALL_SEARCH_MODES = [getattr(mode, "value") for mode in SearchModes]


class FieldWithSearchVector(NamedTuple):
    field: "Field"
    search_vector: SearchVector

    @property
    def field_tsv_db_column(self):
        return self.field.tsv_db_column


class SearchHandler(
    metaclass=baserow_trace_methods(
        tracer, exclude=["full_text_enabled", "search_config"]
    )
):
    @classmethod
    def full_text_enabled(cls):
        return settings.USE_PG_FULLTEXT_SEARCH

    @classmethod
    def search_config(cls):
        return settings.PG_SEARCH_CONFIG

    @classmethod
    def get_default_search_mode_for_table(cls, table: "Table") -> str:
        # Template table indexes are not created to save space so we can only use compat
        # search here.
        if table.database.workspace.has_template():
            return SearchModes.MODE_COMPAT

        search_mode = settings.DEFAULT_SEARCH_MODE
        if table.tsvectors_are_supported:
            search_mode = SearchModes.MODE_FT_WITH_COUNT

        return search_mode

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
        :param skip_search_updates: Whether to update the fields after.
        :return: None
        """

        if field.tsvector_column_created:
            cls._create_tsv_column(field)
            if not skip_search_updates:
                cls.entire_field_values_changed_or_created(
                    field.table, updated_fields=[field]
                )

    @classmethod
    def _create_tsv_column(cls, field):
        with safe_django_schema_editor(atomic=False) as schema_editor:
            to_model = field.table.get_model(
                fields=[field], field_ids=[], add_dependencies=False
            )
            tsv_model_field = to_model._meta.get_field(field.tsv_db_column)
            schema_editor.add_field(to_model, tsv_model_field)
            schema_editor.add_index(
                to_model,
                GinIndex(
                    fields=[field.tsv_db_column],
                    name=field.tsv_index_name,
                ),
            )

    @classmethod
    def after_field_perm_delete(
        cls,
        field: "Field",
    ):
        """
        :param field: The current Baserow field which was deleted from this table.
        :return: None
        """

        if field.tsvector_column_created:
            # The table could have been perm deleted already so don't crash if we
            # fail to delete because the table is already gone as that also means
            # the tsv has been cleaned up already.
            cls._drop_column_if_table_exists(
                f"database_table_{field.table_id}", field.tsv_db_column
            )

    @staticmethod
    def _drop_column_if_table_exists(table_name: str, column_to_drop: str):
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "ALTER TABLE IF EXISTS {table_name} DROP COLUMN {column_to_drop}"
                ).format(
                    table_name=sql.Identifier(table_name),
                    column_to_drop=sql.Identifier(column_to_drop),
                )
            )

    @classmethod
    def _collect_search_vectors(
        cls,
        model: Type["GeneratedTableModel"],
        queryset: QuerySet,
        field_ids_to_restrict_update_to: Optional[List[int]] = None,
    ) -> List[FieldWithSearchVector]:
        """
        Responsible for finding all specific fields in a table, then per `FieldType`,
        calling `get_search_expression` to get its `SearchVector` object, if
        the field type is searchable.
        """

        vector_updates: List[FieldWithSearchVector] = []

        for field in model.get_fields_with_search_index():
            if (
                field_ids_to_restrict_update_to is None
                or field.id in field_ids_to_restrict_update_to
            ):
                vector_updates.append(
                    cls._get_field_with_vector_from_field(field, queryset)
                )  # noinspection PyTypeChecker
        return vector_updates

    @classmethod
    def _get_field_with_vector_from_field(cls, field, queryset):
        from baserow.contrib.database.fields.registries import field_type_registry

        field_type = field_type_registry.get_by_model(field)
        if field_type.is_searchable(field):
            search_vector = LocalisedSearchVector(
                field_type.get_search_expression(field, queryset)
            )
        else:
            search_vector = Value(None)
        return FieldWithSearchVector(field, search_vector)

    @classmethod
    def sync_tsvector_columns(cls, table: "TableForUpdate") -> "TableForUpdate":
        """
        Responsible for creating all the `tsvector` columns for each field in `table`.

        :param table: The Table we want to create a tsvector per field.
        :return: Table
        """

        from baserow.contrib.database.fields.models import Field

        if not cls.full_text_enabled():
            raise PostgresFullTextSearchDisabledException()

        # Prepare a fresh model we can use to create the column.
        model = table.get_model(force_add_tsvectors=True)

        # A list of fields which were given a tsvector field. Once
        # the schema changes have been applied, they'll be mass
        # updated with `tsvector_column_created=True`.
        fields_to_update: List[Field] = []

        fields_to_add = set()
        indices_to_add = set()

        for field in model.get_fields_missing_search_index():
            fields_to_add.add(field.tsv_db_column)
            indices_to_add.add((field.tsv_db_column, field.tsv_index_name))
            field.tsvector_column_created = True
            fields_to_update.append(field)

        with safe_django_schema_editor(atomic=False) as schema_editor:
            for field_name in fields_to_add:
                model_field = model._meta.get_field(field_name)
                logger.debug(f"Adding {field_name} to table {table.id}")
                schema_editor.add_field(model, model_field)
            for field_name, index_name in indices_to_add:
                schema_editor.add_index(
                    model,
                    GinIndex(fields=[field_name], name=index_name),
                )

        if fields_to_update:
            invalidate_table_in_model_cache(table.id)
            Field.objects.bulk_update(fields_to_update, ["tsvector_column_created"])

        return table

    @classmethod
    def get_update_changed_rows_only_lock_key(cls, table):
        return (
            f"_update_tsvector_columns_update_tsvectors_for_changed_rows_only"
            f"_{table.id}_lock"
        )

    @classmethod
    def update_tsvector_columns_locked(
        cls,
        table: "Table",
        update_tsvectors_for_changed_rows_only: bool,
        field_ids_to_restrict_update_to: Optional[List[int]] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Takes out a lock on the table what being updated if the
        `update_tsvectors_for_changed_rows_only` argument is `True`. If there is a
        lock, it won't do anything

        :param table: The table which we're going to update.
        :param update_tsvectors_for_changed_rows_only: If set to `True`, will only
            update the tsvector in rows which have changed since their last update.
            If set to `False`, will update all rows.
        :param field_ids_to_restrict_update_to: If provided only the fields matching the
            provided ids will have their tsv columns updated.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        """

        use_lock = hasattr(cache, "lock")
        used_lock = False
        if update_tsvectors_for_changed_rows_only and use_lock:
            # If the `update_tsvectors_for_changed_rows_only` is True, the update
            # statement will loop for as long as there are rows with
            # `needs_background_update` equals to `True`. This method can be called
            # while that process is running.
            cache_lock = cache.lock(
                cls.get_update_changed_rows_only_lock_key(table), timeout=60 * 60
            )

            # If the lock already exists, it means that another worker is already
            # updating the rows where `needs_background_update` equals `True`,
            # so we don't have to do anything.
            if cache_lock.locked():
                # This will make the progressbar skip this step.
                ChildProgressBuilder.build(progress_builder, child_total=1).increment()
                return

            cache_lock.acquire(blocking=True)
            used_lock = True

        try:
            cls.update_tsvector_columns(
                table,
                update_tsvectors_for_changed_rows_only,
                field_ids_to_restrict_update_to,
                progress_builder,
            )
        finally:
            # The lock must be released if anything goes wrong during the update or
            # when it's finished, otherwise it won't be possible to update the tsv
            # cells for another 60 minutes until the lock times out.
            if used_lock:
                try:
                    cache_lock.release()
                except LockNotOwnedError:
                    # If the lock release fails, it might be because of the timeout,
                    # and it's been stolen, so we don't really care.
                    pass

    @classmethod
    def update_tsvector_columns(
        cls,
        table: "Table",
        update_tsvectors_for_changed_rows_only: bool,
        field_ids_to_restrict_update_to: Optional[List[int]] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Responsible for updating a table's `tsvector` columns. If the caller is
        requesting that all changed rows are updated
        (`update_tsvectors_for_changed_rows_only=True`), then it's recommended to call
        `update_tsvector_columns_locked` instead, as it will prevent multiple
        concurrent tsvector UPDATE queries from being executed.

        :param table: The table which we're going to update.
        :param update_tsvectors_for_changed_rows_only: If set to `True`, will only
            update the tsvector in rows which have changed since their last update.
            If set to `False`, will update all rows.
        :param field_ids_to_restrict_update_to: If provided only the fields matching the
            provided ids will have their tsv columns updated.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :return: None
        """

        # If the installation is set up so that full-text search is not
        # used, and that compat mode is used, then raise an exception.
        if not SearchHandler.full_text_enabled():
            raise PostgresFullTextSearchDisabledException()

        if (
            update_tsvectors_for_changed_rows_only
            and field_ids_to_restrict_update_to is not None
        ):
            raise ValueError(
                "Must always update all fields when updating rows "
                "with needs_background_update=True."
            )

        model = table.get_model()
        qs = model.objects.all()

        # Narrow down our queryset based on the provided kwargs. If
        # `update_tsvectors_for_changed_rows_only` is `True` when they'll only update
        # rows where `last_updated__lte=now()
        if update_tsvectors_for_changed_rows_only:
            qs = qs.filter(Q(**{f"{ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME}": True}))

        collected_vectors = cls._collect_search_vectors(
            model, qs, field_ids_to_restrict_update_to
        )

        # If we've updated the entire `tsvector` column, issue a vacuum to clear dead
        # tuples immediately.
        was_full_column_update = not update_tsvectors_for_changed_rows_only
        must_vacuum = (
            was_full_column_update
            and collected_vectors
            and settings.AUTO_VACUUM_AFTER_SEARCH_UPDATE
            and not settings.TESTS
        )

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=1000 if must_vacuum else 800
        )

        rows_updated_count = cls.run_tsvector_update_statement(
            collected_vectors,
            qs,
            # If we are updating all field ids, then we can safely unset the needs
            # background update.
            set_background_updated_false=field_ids_to_restrict_update_to is None,
            update_tsvectors_for_changed_rows_only=update_tsvectors_for_changed_rows_only,
            progress_builder=progress.create_child_builder(represents_progress=800),
        )

        if must_vacuum:
            progress.increment(state="Vacuuming")
            cls.vacuum_table(table)
            progress.increment(200)
            logger.info(
                "Updated table {table_id}'s tsvs for all rows with optional field "
                "filter of {field_ids}.",
                table_id=table.id,
                field_ids=field_ids_to_restrict_update_to or "no fields",
            )
        else:
            logger.info(
                "Updated {rows_updated_count} rows in table {table_id}'s tsvs with "
                "optional field filter of {field_ids}.",
                rows_updated_count=rows_updated_count or "a unknown number of",
                field_ids=field_ids_to_restrict_update_to or "no fields",
                table_id=table.id,
            )

    @classmethod
    def vacuum_table(cls, table):
        with connection.cursor() as cursor:
            query = sql.SQL("VACUUM {table_name}").format(
                table_name=sql.Identifier(table.get_database_table_name())
            )
            cursor.execute(query)  # type: ignore

    @classmethod
    def split_update_into_chunks_by_ranges(
        cls,
        qs,
        update_query,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Optional[int]:
        """
        Split the queryset up into chunks based on the count, and update the tsv
        cells for the rows in the chunk. It will stop when max number of
        precalculated iterations is reached.
        """

        total_count = qs.count()

        # There can be an edge case where the row has already bee updated. To prevent
        # division by zero exceptions, we don't have to do anything here.
        if total_count == 0:
            return 0

        total_iterations = math.ceil(total_count / settings.TSV_UPDATE_CHUNK_SIZE)
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=total_iterations
        )
        total_updated = 0
        for i in range(0, total_count, settings.TSV_UPDATE_CHUNK_SIZE):
            with transaction.atomic():
                next_ids = qs.order_by("id").values_list("id", flat=True)[
                    i : i + settings.TSV_UPDATE_CHUNK_SIZE
                ]
                next_chunk = qs.filter(id__in=next_ids).select_for_update(of=("self",))
                total_updated += next_chunk.update(**update_query)
            progress.increment()
        return total_updated

    @classmethod
    def split_update_into_chunks_until_all_background_done(
        cls,
        qs,
        update_query,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Optional[int]:
        """
        This method keeps iterating over the provided row queryset, fetch the not
        updated rows in chunks, and update the tsv cells of those chunks. It will
        keep going until none are left.
        """

        estimated_count = qs.count()

        # There can be an edge case where the row has already been updated. To prevent
        # division by zero exceptions, we don't have to do anything here.
        if estimated_count == 0:
            return 0

        estimated_iterations = math.ceil(
            estimated_count / settings.TSV_UPDATE_CHUNK_SIZE
        )
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=estimated_iterations
        )
        total_updated = 0
        while True:
            with transaction.atomic():
                next_ids = qs.order_by("id").values_list("id", flat=True)[
                    0 : settings.TSV_UPDATE_CHUNK_SIZE
                ]
                next_ids = list(next_ids)
                next_chunk = qs.filter(id__in=next_ids)
                this_chunk_updated = next_chunk.update(**update_query)
                progress.increment()
                total_updated += 0
                if this_chunk_updated == 0:
                    return total_updated

    @classmethod
    def run_tsvector_update_statement(
        cls,
        collected_vectors: List,
        qs: QuerySet,
        set_background_updated_false: bool,
        update_tsvectors_for_changed_rows_only: bool,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Optional[int]:
        progress = ChildProgressBuilder.build(progress_builder, child_total=1000)

        try:
            update_query = {
                cv.field_tsv_db_column: cv.search_vector for cv in collected_vectors
            }
            if set_background_updated_false:
                update_query[ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME] = Value(False)
            if update_tsvectors_for_changed_rows_only:
                return cls.split_update_into_chunks_until_all_background_done(
                    qs,
                    update_query,
                    progress_builder=progress.create_child_builder(
                        represents_progress=1000
                    ),
                )
            else:
                return cls.split_update_into_chunks_by_ranges(
                    qs,
                    update_query,
                    progress_builder=progress.create_child_builder(
                        represents_progress=1000
                    ),
                )
        except Exception as e:
            progress.set_progress(0)

            logger.error(
                "Failed to do full update search vector because of {e}. "
                "Attempting to do per field updates one by one instead...",
                e=str(e),
            )
            exception_capturer(e)
            # Reset the original progress because we're going to start from scratch
            # again.
            progress.increment(-progress.progress)
            cls.try_slower_but_best_effort_tsv_update(
                collected_vectors,
                qs,
                set_background_updated_false,
                update_tsvectors_for_changed_rows_only,
                progress_builder=progress.create_child_builder(
                    represents_progress=1000
                ),
            )

    @classmethod
    def try_slower_but_best_effort_tsv_update(
        cls,
        collected_vectors: List[FieldWithSearchVector],
        qs: QuerySet,
        set_background_updated_false,
        update_tsvectors_for_changed_rows_only,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Given the complexity of all possible field configurations in Baserow there is
        a good chance some fields might fail to index. This method ensures that
        even if some columns fail to index in this exception situation, the rest of
        the normal columns will still be indexed and the user will be able to continue
        searching happily after.
        """

        from baserow.contrib.database.fields.handler import FieldHandler

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(collected_vectors) * 1000 + 1000
        )
        progress.increment(state="Slower update")

        num_worked = 0
        for cv in collected_vectors:
            try:
                # re-fetch the fields incase they changed since we got the model
                refetched_field = FieldHandler().get_field(cv.field.id).specific
                cv = cls._get_field_with_vector_from_field(refetched_field, qs)
                if update_tsvectors_for_changed_rows_only:
                    cls.split_update_into_chunks_until_all_background_done(
                        qs,
                        {cv.field_tsv_db_column: cv.search_vector},
                        progress_builder=progress.create_child_builder(
                            represents_progress=1000
                        ),
                    )
                else:
                    cls.split_update_into_chunks_by_ranges(
                        qs,
                        {cv.field_tsv_db_column: cv.search_vector},
                        progress_builder=progress.create_child_builder(
                            represents_progress=1000
                        ),
                    )
                num_worked += 1
            except Exception as another_e:
                field = cv.field
                logger.error(
                    "Failed to update search vector for field with id {field_id} / "
                    "type {field_type} because of {e}, field.__str__ is: "
                    + str(field)
                    + " and expression is "
                    + str(cv.search_vector),
                    field_id=field.id,
                    field_type=str(type(field)),
                    e=str(another_e),
                )
                cls._search_error_handler(another_e)
        if num_worked > len(collected_vectors) // 2 and set_background_updated_false:
            # If more than half managed to work then it's better to mark them as
            # having worked compared to the table filling up with more and more rows
            # that never get marked as having had a background update.
            cls.split_update_into_chunks_by_ranges(
                qs,
                {ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME: Value(False)},
                progress_builder=progress.create_child_builder(
                    represents_progress=1000
                ),
            )
        else:
            progress.increment(1000)

    @classmethod
    def field_value_updated_or_created(
        cls,
        table: "Table",
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

        cls._trigger_async_tsvector_task_if_needed(
            table,
            update_tsvs_for_changed_rows_only=True,
        )

    @classmethod
    def entire_field_values_changed_or_created(
        cls,
        table: "Table",
        updated_fields: Optional[List["Field"]] = None,
    ):
        """
        Called when field values for a table have been changed or created for an entire
        field column at once.

        :param table: The table a field value has been created or updated in.
        :param updated_fields: If only some fields have had values
            changed then the search vector update can be optimized by providing those
            here.
        """

        cls._trigger_async_tsvector_task_if_needed(
            table,
            update_tsvs_for_changed_rows_only=False,
            updated_fields=updated_fields,
        )

    @classmethod
    def _trigger_async_tsvector_task_if_needed(
        cls,
        table,
        update_tsvs_for_changed_rows_only,
        updated_fields: Optional[List["Field"]] = None,
    ):
        if table.tsvectors_are_supported:
            from baserow.contrib.database.search.tasks import (
                async_update_tsvector_columns,
            )
            from baserow.contrib.database.tasks import (
                enqueue_task_on_commit_swallowing_any_exceptions,
            )

            searchable_updated_fields_ids = (
                [field.id for field in updated_fields]
                if updated_fields is not None
                else None
            )

            enqueue_task_on_commit_swallowing_any_exceptions(
                lambda: async_update_tsvector_columns.delay(
                    table.id,
                    update_tsvs_for_changed_rows_only=update_tsvs_for_changed_rows_only,
                    field_ids_to_restrict_update_to=searchable_updated_fields_ids,
                )
            )

    @classmethod
    def _search_error_handler(cls, e):
        if settings.TESTS:
            # We want to see any issues immediately in debug mode.
            raise e
        traceback.print_exc()
        exception_capturer(e)

    @classmethod
    def after_field_moved_between_tables(
        cls, moved_field: "Field", original_table_id: int
    ):
        if moved_field.tsvector_column_created:
            cls._drop_column_if_table_exists(
                f"database_table_{original_table_id}", moved_field.tsv_db_column
            )
            cls._create_tsv_column(moved_field)
