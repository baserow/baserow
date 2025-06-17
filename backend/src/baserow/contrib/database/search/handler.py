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

import math
import traceback
from copy import copy
from datetime import datetime
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING, List, NamedTuple, Optional, Type

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction
from django.db.models import Expression, Func, Model, Q, QuerySet, TextField, Value
from django.utils.encoding import force_str

from loguru import logger
from opentelemetry import trace
from redis.exceptions import LockNotOwnedError

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.search.expressions import LocalisedSearchVector
from baserow.contrib.database.search.models import (
    SearchTableBase,
    SearchValueUpdate,
    get_search_indexes,
)
from baserow.contrib.database.search.regexes import (
    RE_ONE_OR_MORE_WHITESPACE,
    RE_REMOVE_ALL_PUNCTUATION_ALREADY_REMOVED_FROM_TSVS_FOR_QUERY,
    RE_REMOVE_NON_SEARCHABLE_PUNCTUATION_FROM_TSVECTOR_DATA,
)
from baserow.contrib.database.search.tasks import (
    create_search_table_for_workspace,
    migrate_search_data_table,
    schedule_table_search_data_update,
)
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.table.constants import (
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
)
from baserow.contrib.database.tasks import (
    enqueue_task_on_commit_swallowing_any_exceptions,
)
from baserow.core.psycopg import sql
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.utils import ChildProgressBuilder, exception_capturer

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
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

MAX_ROW_IDS_COUNT = 100


class FieldWithSearchVector(NamedTuple):
    field: "Field"
    search_vector: SearchVector

    @property
    def field_tsv_db_column(self):
        return self.field.tsv_db_column


# Note: this is separated from SearchHandler to not to pollute SearchHandler's
# interface with methods that are using old logic.
class SearchHandlerCompat(
    metaclass=baserow_trace_methods(
        tracer, exclude=["full_text_enabled", "search_config"]
    )
):
    """
    Old version of SearchHandler, which works with in-table tsv columns.

    Some calls in the SearchHandler may be performed on tables that are not (yet)
    migrated to new search data table. Such calls should be delegated to
    SearchHandlerCompat.
    """

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
    def sync_tsvector_columns(cls, table: "Table") -> "Table":
        """
        Responsible for creating all the `tsvector` columns for each field in `table`.

        :param table: The Table we want to create a tsvector per field.
        :return: Table
        """

        logger.error(f"Called sync_tsvecotr_columns on {table}.")
        from baserow.contrib.database.fields.models import Field

        if not SearchHandler.full_text_enabled():
            raise PostgresFullTextSearchDisabledException()

        if table.search_data_state == SearchTableState.READY:
            logger.info(f"Table {table} is migrated.")
            return table

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

        if SearchHandler.table_is_active(table):
            logger.error(f"Called update_tsvector_columns_locked on {table}")
            return

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

        if SearchHandler.table_is_active(table):
            logger.error(f"Called update_tsvector_columns on {table}")
            return

        # If the installation is set up so that full-text search is not
        # used, and that compat mode is used, then raise an exception.
        if not SearchHandler.full_text_enabled():
            raise PostgresFullTextSearchDisabledException()

        if update_tsvectors_for_changed_rows_only and field_ids_to_restrict_update_to:
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
        logger.error(f"Called vacuum table on {table}")
        return

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
    def _field_value_updated_or_created(
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
            update_tsvectors_for_changed_rows_only=True,
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
            update_tsvectors_for_changed_rows_only=False,
            updated_fields=updated_fields,
        )

    @classmethod
    def all_fields_values_changed_or_created(cls, updated_fields: List["Field"]):
        """
        Called when field values for a table have been changed or created for an entire
        field column at once. This is more efficient than calling
        `entire_field_values_changed_or_created` for each table individually when
        multiple tables have had field values changed. Please, make sure to
        select_related the table for the "updated_fields" to avoid N+1 queries.

        :param updated_fields: If only some fields have had values changed then the
            search vector update can be optimized by providing those here.
        """

        from baserow.contrib.database.search.tasks import (
            async_update_multiple_fields_tsvector_columns_v1,
        )
        from baserow.contrib.database.tasks import (
            enqueue_task_on_commit_swallowing_any_exceptions,
        )

        searchable_updated_fields_ids = [
            field.id for field in updated_fields if field.table.tsvectors_are_supported
        ]

        if searchable_updated_fields_ids:
            enqueue_task_on_commit_swallowing_any_exceptions(
                lambda: async_update_multiple_fields_tsvector_columns_v1.delay(
                    field_ids=searchable_updated_fields_ids,
                    update_tsvectors_for_changed_rows_only=False,
                )
            )

    @classmethod
    def _trigger_async_tsvector_task_if_needed(
        cls,
        table,
        update_tsvectors_for_changed_rows_only,
        updated_fields: Optional[List["Field"]] = None,
    ):
        if table.tsvectors_are_supported:
            from baserow.contrib.database.search.tasks import (
                async_update_tsvector_columns_v1,
            )
            from baserow.contrib.database.tasks import (
                enqueue_task_on_commit_swallowing_any_exceptions,
            )

            searchable_updated_fields_ids = (
                [
                    field if isinstance(field, int) else field.id
                    for field in updated_fields
                ]
                if updated_fields is not None
                else None
            )

            enqueue_task_on_commit_swallowing_any_exceptions(
                lambda: async_update_tsvector_columns_v1.delay(
                    table.id,
                    update_tsvectors_for_changed_rows_only=update_tsvectors_for_changed_rows_only,
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


class SearchHandler(
    metaclass=baserow_trace_methods(
        tracer, exclude=["full_text_enabled", "search_config"]
    )
):
    """
    Manages various search-related operations:
    * Prepare required infrastrucutre:
      * Create per-workspace search data table.
      * Create per-workspace settings record that keeps information on search data
        schema version.
    * Manage and check search data state on per-table basis (if a table uses search data
      table, or if it should be migrated to use it).
    * Extracts search data (tsvector values calculated based on a field type) from user
      data tables.
    * Update search data when originating user data change.
    * Prepare search-related values.

    For constructing search queries, see `.search_builder.SearchBuilder` class.
    """

    @classmethod
    def _get_search_table_table_name(cls, workspace_id) -> str:
        return f"database_workspace_search_{workspace_id}"

    @classmethod
    def _get_search_table_model_name(cls, workspace_id) -> str:
        return f"SearchTable{workspace_id}"

    @classmethod
    def get_search_table_model(cls, workspace_id: int) -> "SearchTableBase":
        """
        Generates SearchTable model
        :param table:
        :return:
        """

        from baserow.contrib.database.table.models import GeneratedModelAppsProxy

        app_label = f"database_workspace_search_{workspace_id}"
        table_name = cls._get_search_table_table_name(workspace_id)
        model_name = cls._get_search_table_model_name(workspace_id)

        indexes = get_search_indexes(workspace_id)
        baserow_models = {}
        apps = GeneratedModelAppsProxy(baserow_models, app_label)
        meta = type(
            "Meta",
            (),
            {
                "apps": apps,
                # we want to create this model
                "managed": True,
                "db_table": table_name,
                "app_label": app_label,
                "ordering": ["row_id", "field_id", "-updated_on"],
                "indexes": indexes,
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
                SearchTableBase,
                Model,
            ),
            attrs,
        )
        return model

    @classmethod
    def create_search_table_for_workspace(cls, workspace_id: int):
        from baserow.contrib.database.models import WorkspaceDatabaseSettings
        from baserow.contrib.database.search.models import SearchTableBase

        workspace_settings, _created = WorkspaceDatabaseSettings.objects.get_or_create(
            workspace_id=workspace_id
        )
        search_table = cls.get_search_table_model(workspace_id)

        # TODO: handle search table schema changes with .search_table_version value
        if workspace_settings.search_table_version is None:
            create_table(search_table)
            workspace_settings.search_table_version = SearchTableBase.version
            workspace_settings.save(update_fields=["search_table_version"])

        return search_table

    @classmethod
    def remove_search_table_for_workspace(cls, workspace_id: int):
        search_table = cls.get_search_table_model(workspace_id)
        drop_table(search_table)

    @classmethod
    def _migrate_table_tsvectors(cls, table):
        """
        Migrates old tsv columns to a workspace-wide search table.

        This method uses a quick migration strategy by copying existing tsv values
        for fields. Note, that tsv values may be inacurate: not up-to-date (due to
        update failures) or empty (due to missing background updates).

        :param table:
        :return:
        """

        workspace_id = table.database.workspace_id

        logger.info(f"Start migrating {table}.")
        search_table_name = cls._get_search_table_table_name(workspace_id)
        model = table.get_model()
        table_name = model._meta.db_table
        fields = model.get_field_objects()
        searchable_fields = [
            f["field"] for f in fields if f["field"].tsvector_column_created
        ]
        with connection.cursor() as cursor:
            for field in searchable_fields:
                q = f"""INSERT INTO {search_table_name} (row_id, field_id, updated_on, value)
                 select id, {field.id}, updated_on, {field.tsv_db_column}
                   FROM {table_name}
                   WHERE
                    NOT trashed
                    AND {field.tsv_db_column} IS DISTINCT FROM NULL
                    """  # nosec B608
                cursor.execute(q)
        logger.info(f"Search data migration done for {table}.")

    @classmethod
    def _get_queryset_for_rows_with_emtpy_tsv_columns(
        cls,
        table: "Table",
        query: QuerySet | None = None,
        fields: list["Field"] | None = None,
        since: datetime | None = None,
    ) -> QuerySet:
        """
        Generates a query that returns rows with tsv columns that are empty.

        :param table: table definition
        :param query: optional base queryset
        :param fields: optional list of fields to query for tsv vectors
        :param since: optional min created/updated on timestamp
        :return: Queryset with rows that have empty values in tsv columns
        """

        model = table.get_model()
        if not fields:
            fields = [
                f["field"]
                for f in model.get_field_objects()
                if (not f["type"].read_only)
                and (
                    getattr(f["field"], "tsv_column", None)
                    and f["field"].tsvector_column_created
                )
            ]
        if not query:
            query = model.objects.all()
        if since:
            query.filter(Q(updated_on__gt=since))
        qfilters = Q()
        for field in fields:
            qfilters = qfilters | Q(**{f"{field.tsv_column}__isnull": True})

        return query.filter(qfilters)

    @classmethod
    def get_rows_with_empty_tsv_columns(
        cls,
        table: "Table",
        query: QuerySet | None = None,
        fields: list["Field"] | None = None,
        since: datetime | None = None,
    ) -> list[int]:
        """
        Returns a list of rows for a table, that have empty tsv vectors for selected
        fields.
        """

        q = cls._get_queryset_for_rows_with_emtpy_tsv_columns(
            table, query, fields, since
        )
        return list(q.values_list("id", flat=True))

    @classmethod
    def migrate_table_tsvectors(cls, table: "Table"):
        """
        Migrates a table to search table infrastructure.
        :param table:
        :return:
        """

        if not cls.full_text_enabled():
            return
        if cls.table_is_migrated(table):
            logger.debug(f"Table already migrated {table}")
            return
        if not cls.table_is_active(table):
            logger.debug(f"Table migration blocked for {table}")
            return

        try:
            logger.debug(f"Migrating from tsv to search data in {table}")

            with transaction.atomic():
                empty_vector_row_ids = cls.get_rows_with_empty_tsv_columns(table)

                # migrate rows that have tsvector columns filled
                cls._migrate_table_tsvectors(table)

                if empty_vector_row_ids:
                    # migrate rows that we know have empty tsv columns.
                    cls.update_search_data_for_table(
                        table, row_ids=empty_vector_row_ids, skip_table_checks=True
                    )
                table.search_data_state = SearchTableState.READY
                table.save(update_fields=["search_data_state"])

            logger.debug(f"Done migrating from tsv to search data in {table}")
        except Exception as err:
            logger.opt(exception=err).error(
                f"Error when migrating search data for {table}: {err}"
            )
            return

    @classmethod
    def update_search_data_for_table(
        cls,
        table: "Table",
        row_ids: list[int],
        skip_table_checks: bool = False,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        full or partial update may be performed.

        :param table: table definition
        :param field_ids_to_restrict_update_to: Optional list of field ids to restrict
            the source of data for the update. If not provided, all searchable fields
            will be used.
        :param progress_builder:
        :param update_tsvectors_for_rows_changed_since: Optional datetime to restrict
            update to rows newer than the provided value.
        :param update_tsvectors_for_changed_rows_only: Optional flag to restrict
            update to rows that changed since the last update. The last update timestamp
            is calculated as a max updated_on value for any field for a table.
        :param row_ids: Optional list of row ids to use for the update.
        :param skip_table_checks: Optional flag to skip a check if table has been
            migrated.
        :return:
        """

        # If the installation is set up so that full-text search is not
        # used, and that compat mode is used, then raise an exception.
        # Also, the table should be migrated already.
        if not SearchHandler.full_text_enabled():
            raise PostgresFullTextSearchDisabledException()
        if not (cls.table_is_migrated(table) or skip_table_checks):
            logger.warning(
                f"Called SearchHandler.update_search_data_for_table "
                f"on not migrated table {table}"
            )
            return

        if not row_ids:
            return
        workspace_id = table.database.workspace_id
        search_model = cls.get_search_table_model(workspace_id)

        model = table.get_model()
        fields = model.get_field_objects(include_trash=True)
        # progress = ChildProgressBuilder.build(
        #     progress_builder, child_total=1000 if must_vacuum else 800
        # )
        if not fields:
            return

        query: QuerySet = model.objects.filter(id__in=row_ids)

        qannotate = {}
        for f in fields:
            try:
                expr: Expression = f["type"].get_search_expression(f["field"], query)

            # This can happen if there's no suitable primary field,
            # i.e. a table with linkrow field only
            except StopIteration:
                expr = None
            if expr is None:
                continue

            qannotate[f"search_{f['name']}"] = LocalisedSearchVector(expr)

        inserts = []
        for row in query.annotate(**qannotate).select_related():
            for field in fields:
                svect = search_model(
                    row_id=row.id,
                    field_id=field["field"].id,
                    updated_on=row.updated_on,
                    value=getattr(row, f"search_{field['name']}"),
                )
                if svect.value:
                    inserts.append(svect)
        logger.debug(f"Adding {len(inserts)} entries to {search_model} for {table}.")

        search_model.objects.bulk_create(inserts)

    @classmethod
    def _trigger_async_workspacesearchtable_task_if_needed(cls, workspace_id: int):
        create_search_table_for_workspace.delay(workspace_id=workspace_id)

    @classmethod
    def _trigger_async_tsvector_task_if_needed(
        cls,
        table,
        update_tsvectors_for_changed_rows_only: bool = True,
        updated_fields: Optional[List["Field"]] = None,
        updated_row_ids: list[int] | None = None,
    ):
        """

        :param table:
        :param update_tsvectors_for_changed_rows_only: (v1 compatibility flag)
        :param updated_fields: list of field ids that were updated
        :param updated_row_ids: list of rows that were updated
        :return:
        """

        # disabled, or a snapshot
        if not cls.table_is_active(table):
            if update_tsvectors_for_changed_rows_only and updated_fields:
                update_tsvectors_for_changed_rows_only = False
            return SearchHandlerCompat()._trigger_async_tsvector_task_if_needed(
                table, update_tsvectors_for_changed_rows_only, updated_fields
            )
        # not migrated yet
        if cls.table_can_migrate(table):
            enqueue_task_on_commit_swallowing_any_exceptions(
                partial(migrate_search_data_table.delay, table_id=table.id)
            )
        else:
            searchable_updated_fields_ids = (
                [
                    field if isinstance(field, int) else field.id
                    for field in updated_fields
                ]
                if updated_fields is not None
                else None
            )
            enqueue_task_on_commit_swallowing_any_exceptions(
                partial(
                    cls.mark_table_data_change,
                    table_id=table.id,
                    row_ids=updated_row_ids,
                    field_ids=searchable_updated_fields_ids,
                )
            )

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
            return SearchModes.MODE_COMPAT

        search_mode = settings.DEFAULT_SEARCH_MODE
        if table.tsvectors_are_supported:
            search_mode = SearchModes.MODE_FT_WITH_COUNT

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

        table = field.table
        # use old search handler for not migrated tables
        # if not cls.table_is_active(table):
        #     return SearchHandlerCompat().after_field_created(
        #         field, skip_search_updates=skip_search_updates
        #     )

        SearchHandlerCompat().after_field_created(
            field, skip_search_updates=skip_search_updates
        )
        if not cls.table_is_active(table):
            return
        if not skip_search_updates:
            cls.mark_table_data_change(table_id=table.id, field_ids=[field.id])

    @classmethod
    def table_is_active(cls, table: "Table") -> bool:
        """
        Tells if a table can be used, or migrated to search data table migration.
        A table can be marked as `disabled`, which means it should not be migrated
        to search data table infrastructure.
        """

        return table.search_data_state != SearchTableState.DISABLED

    @classmethod
    def table_is_migrated(cls, table: "Table") -> bool:
        """
        Returns `True` if a table can be used with search data table for the
        workspace related.
        """

        return (
            table.search_data_state == SearchTableState.READY
            # exclude snapshots
            and table.database.workspace_id
        )

    @classmethod
    def table_can_migrate(cls, table: "Table", check_table_state: bool = True) -> bool:
        """
        Returns `True` if a table wasn't migrated to search data table infrastructure
        yet, and can be migrated.

        :param table:
        :param check_table_state: If not set, check only if the workspace is migrated.
        :return:
        """

        if not (cls.table_is_active(table) and cls.full_text_enabled()):
            return False
        try:
            workspace_settings = table.database.workspace.workspacedatabasesettings
        # AttributeError means the table can be part of a snapshot, so it won't be
        # connected to a workspace.
        except (ObjectDoesNotExist, AttributeError):
            return False
        if check_table_state:
            return (
                workspace_settings.search_table_version == SearchTableBase.version
                and not cls.table_is_migrated(table)
            )
        else:
            return workspace_settings.search_table_version == SearchTableBase.version

    @classmethod
    def after_field_moved_between_tables(
        cls, moved_field: "Field", original_table_id: int
    ):
        from baserow.contrib.database.table.handler import TableHandler

        previous_table = TableHandler().get_table(original_table_id)
        #
        # if not (
        #     cls.table_is_active(previous_table)
        #     and cls.table_is_active(moved_field.table)
        # ):
        #     return SearchHandlerCompat().after_field_moved_between_tables(
        #         moved_field, original_table_id=original_table_id
        #     )
        SearchHandlerCompat().after_field_moved_between_tables(
            moved_field, original_table_id=original_table_id
        )

        if not (
            cls.table_is_active(previous_table)
            and cls.table_is_active(moved_field.table)
        ):
            return

        cls._trigger_async_tsvector_task_if_needed(
            moved_field.table,
            update_tsvectors_for_changed_rows_only=False,
            updated_fields=[moved_field],
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

        table = field.table

        SearchHandlerCompat().after_field_perm_delete(field)
        if not cls.table_is_active(table):
            return

        cls.cleanup_table_rows_vectors(table, field_ids=[field.id])

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

        if not cls.table_is_active(table):
            return SearchHandlerCompat().entire_field_values_changed_or_created(
                table, updated_fields=updated_fields
            )

        cls._trigger_async_tsvector_task_if_needed(
            table,
            update_tsvectors_for_changed_rows_only=False,
            updated_fields=updated_fields,
        )

    @classmethod
    def all_fields_values_changed_or_created(cls, updated_fields: List["Field"]):
        """
        Called when field values for a table have been changed or created for an entire
        field column at once. This is more efficient than calling
        `entire_field_values_changed_or_created` for each table individually when
        multiple tables have had field values changed. Please, make sure to
        select_related the table for the "updated_fields" to avoid N+1 queries.

        :param updated_fields: If only some fields have had values changed then the
            search vector update can be optimized by providing those here.
        """

        if not updated_fields:
            return
        table = updated_fields[0].table

        SearchHandlerCompat().all_fields_values_changed_or_created(
            updated_fields=updated_fields
        )

        if not cls.table_is_active(table):
            return

        searchable_updated_fields_ids = [field.id for field in updated_fields]

        if searchable_updated_fields_ids:
            cls._trigger_async_tsvector_task_if_needed(
                table,
                update_tsvectors_for_changed_rows_only=False,
                updated_fields=searchable_updated_fields_ids,
            )

    @classmethod
    def cleanup_table_rows_vectors(
        cls,
        table: "Table",
        row_ids: list[int] | None = None,
        field_ids: list[int] | None = None,
    ):
        """
        Removes rows for specific fields.

        If no field_ids is provided, all fields from table will be used.
        If no row_ids is provided, all rows for all fields from a table will be removed.

        """

        if not cls.full_text_enabled():
            return
        if not cls.table_is_migrated(table):
            logger.warning(
                f"Called SearchHandler.cleanup_table_rows_vectors "
                f"on not migrated table {table}"
            )
            return
        all_field_ids = [
            f["field"].id
            for f in table.get_model().get_field_objects(include_trash=True)
        ]

        if field_ids is None:
            field_ids = all_field_ids

        search_table = cls.get_search_table_model(table.database.workspace_id)
        filters = {"field_id__in": field_ids}
        if row_ids:
            filters["row_id__in"] = row_ids
        logger.debug(
            f"{search_table}: removing {len(row_ids) if row_ids else 'all'} rows for "
            f"{table} for fields {field_ids}"
        )
        search_table.objects.filter(**filters).delete()

    @classmethod
    def cleanup_old_vectors(cls, table: "Table"):
        """
        Removes stale search vector rows (older than latest) from search table.
        """

        if not cls.full_text_enabled():
            return
        if not cls.table_is_migrated(table):
            logger.warning(
                f"Called SearchHandler.cleanup_old_vectors "
                f"on not migrated table {table}: {table.search_data_state}"
            )
            return
        workspace_id = table.database.workspace_id
        search_table = cls.get_search_table_model(workspace_id)

        field_ids = [f["field"].id for f in table.get_model().get_field_objects()]

        where = sql.SQL(" WHERE field_id =any(%s) ")

        query = sql.SQL(
            """ WITH src_q as (SELECT row_id, field_id, max(updated_on) as max_updated_on
                from {} {} group by row_id, field_id)
                DELETE FROM {} as t
                    USING src_q where
                            (src_q.row_id = t.row_id
                            AND src_q.field_id = t.field_id
                            AND t.updated_on < src_q.max_updated_on)
                RETURNING t.id, t.row_id, t.field_id, t.updated_on
        """
        ).format(
            sql.Identifier(search_table._meta.db_table),
            where,
            sql.Identifier(search_table._meta.db_table),
        )  # nosec B608
        params = [field_ids]

        with connection.cursor() as c:
            c.execute(query, params)
            out = c.fetchall()
            return out

    @classmethod
    def field_value_updated_or_created(
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

        cls._trigger_async_tsvector_task_if_needed(
            table,
            update_tsvectors_for_changed_rows_only=True,
            updated_row_ids=row_ids,
            updated_fields=fields,
        )

    @classmethod
    def mark_table_data_change(
        cls,
        table_id: int,
        row_ids: list[int] = None,
        field_ids: list[int] | None = None,
        skip_schedule: bool = False,
    ):
        """
        Add a search table update change entry. Change entry keeps information on
        which table, which rows and/or which fields changed. Based on that, search
        data table is updated with .handle_table_data_change().
        """

        if not (row_ids and field_ids):
            logger.debug(f"Scheduling full table update for {table_id}")
        else:
            logger.debug(
                f"Scheduling update for {table_id}: rows: {row_ids}, fields: {field_ids}"
            )

        # TODO: in some cases the row_ids count may be significant (10k+ rows), which
        #  may affect the performance.
        ret = SearchValueUpdate.objects.create(
            table_id=table_id, row_ids=row_ids, field_ids=field_ids
        )
        if not skip_schedule:
            schedule_table_search_data_update(table_id=table_id)
        return ret

    @classmethod
    def process_table_data_changes(cls, table: "Table"):
        """
        Process SearchValueUpdate entries
        """

        model = table.get_model()
        fields = {f["field"].id: f for f in model.get_field_objects(include_trash=True)}

        workspace_id = table.database.workspace_id
        search_model = cls.get_search_table_model(workspace_id)

        update_params_query = SearchValueUpdate.objects.filter(
            table=table
        ).select_for_update(of=("self",), skip_locked=True)

        source_query: QuerySet = model.objects_and_trash.all()
        inserts = []
        just_field_ids = set([])
        for item in update_params_query:
            field_ids = item.field_ids or fields.keys()
            row_ids = item.row_ids
            logger.debug(
                f"table data change: {table}, rows: {row_ids}, fields: {field_ids}"
            )
            if row_ids:
                query = source_query.filter(id__in=row_ids)
            else:
                query = copy(source_query)

            qannotate = {}
            used_fields = []
            for field_id in field_ids:
                f = fields.get(field_id)
                if not f:
                    logger.info(f"Field {field_id} not found in {table}")
                    continue
                try:
                    expr: Expression = f["type"].get_search_expression(
                        f["field"], query
                    )

                # This can happen if there's no suitable primary field,
                # i.e. a table with linkrow field only
                except StopIteration:
                    logger.info(
                        f"Field {field_id} in {table} " f"ommitted: No primary field "
                    )
                    continue
                if expr is None:
                    logger.info(f"Field {field_id} in {table} ommitted: No expression ")
                    continue

                qannotate[f"search_{f['name']}"] = LocalisedSearchVector(expr)
                used_fields.append(f)

            # Need to remove existing values for updates that affect whole fields,
            # because field type change will not cause updated_on timestamp update,
            # so search data cleanup will not remove stalled entries.
            # Here we just collect used field ids.
            if not row_ids:
                just_field_ids = just_field_ids.union(
                    set([f["field"].id for f in used_fields])
                )
            for row in query.annotate(**qannotate):
                for field in used_fields:
                    svect = search_model(
                        row_id=row.id,
                        field_id=field["field"].id,
                        updated_on=row.updated_on,
                        value=getattr(row, f"search_{field['name']}"),
                    )
                    # if svect.value:
                    inserts.append(svect)

        update_params_query.delete()
        logger.debug(f"Adding {len(inserts)} entries " f"to {search_model} for {table}")

        if just_field_ids:
            search_model.objects.filter(field_id__in=list(just_field_ids)).delete()

        search_model.objects.bulk_create(list(inserts))


def drop_table(tmodel):
    # regular schema editor doesn't support IF EXISTS, and there may be a case when
    # a workspace doesn't have the table.
    query = sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
        sql.Identifier(tmodel._meta.db_table)
    )
    with connection.cursor() as c:
        c.execute(query)


def create_table(tmodel):
    drop_table(tmodel)
    with safe_django_schema_editor() as se:
        se.create_model(tmodel)


def truncate_table(tmodel):
    with connection.cursor() as c:
        c.execute(f"TRUNCATE TABLE {tmodel._meta.db_table}")
