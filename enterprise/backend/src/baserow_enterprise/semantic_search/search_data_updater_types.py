from datetime import datetime
from itertools import groupby
from typing import Any, Optional

from django.conf import settings
from django.db import router, transaction
from django.db.models import QuerySet
from django.utils import timezone

from loguru import logger

from baserow.contrib.database.search.registries import SearchDataUpdaterType
from baserow.contrib.database.table.models import Table
from baserow.core.embeddings import EmbeddingsServiceError, vector_search_available

from .handler import INDEX_BATCH_ROWS, SemanticSearchHandler, _FieldIndexer
from .models import SemanticSearchField, SemanticSearchPendingUpdate
from .vector_table import SemanticSearchVectorTable

UPDATE_THROTTLE_SECONDS = 5


class SemanticSearchDataUpdaterType(SearchDataUpdaterType):
    type = "semantic_search"
    queue_model = SemanticSearchPendingUpdate
    reschedule_flag_key_prefix = "semantic_search_data_lock"
    row_batch_size = INDEX_BATCH_ROWS
    full_field_updates_cover_row_updates = False

    def get_update_task(self):
        from .tasks import update_semantic_search_data

        return update_semantic_search_data

    def get_throttle_seconds(self) -> int:
        return UPDATE_THROTTLE_SECONDS

    def get_time_budget_seconds(self) -> int:
        return settings.BASEROW_SEMANTIC_SEARCH_TASK_TIME_BUDGET_SECONDS

    def should_queue(self) -> bool:
        # Like full-text search, instances without vector search skip it entirely.
        # Fields enabled through an import already have an update of all rows
        # queued, which reads the values that changed in the meantime.
        return vector_search_available()

    def _get_semantic_search_fields(
        self, table: Table, field_ids: list[int] | None
    ) -> QuerySet:
        semantic_search_fields = SemanticSearchField.objects.filter(
            field__table=table, field__trashed=False
        )
        if field_ids is not None:
            semantic_search_fields = semantic_search_fields.filter(
                field_id__in=field_ids
            )
        return semantic_search_fields

    def queue_pending_updates(
        self, field_ids: list[int], row_ids: list[int] | None = None, **values: Any
    ):
        if row_ids is not None:
            super().queue_pending_updates(field_ids, row_ids, **values)
            return

        # The unique constraint doesn't prevent duplicate updates of all rows,
        # because PostgreSQL 14 considers their null row ids different. Every
        # duplicate would be a separate pass over all rows.
        full_updates = self.queue_model.objects_and_trash.filter(
            field_id__in=field_ids, row_id=None
        )
        queued_field_ids = set(full_updates.values_list("field_id", flat=True))
        # Re-enabling semantic search before the vectors are deleted keeps them. The
        # update of all rows reuses the ones of unchanged values, and deletes the
        # ones of rows that no longer exist.
        full_updates.update(
            updated_on=timezone.now(), deletion_workspace_id=None, **values
        )
        super().queue_pending_updates(
            [field_id for field_id in field_ids if field_id not in queued_field_ids],
            **values,
        )

    def mark_for_deletion(
        self,
        workspace_id: int,
        field_ids: list[int],
        row_ids: list[int] | None = None,
    ):
        """
        Marks the vectors for deletion, like the full-text search data, so that they
        are deleted by the periodic check. Pending updates of whole fields are no
        longer processed, and a marked row is always a permanently deleted row.

        :param workspace_id: The workspace of the vectors.
        :param field_ids: The fields of which the vectors are deleted.
        :param row_ids: Only the vectors of these rows are deleted, if set.
        """

        marked = {
            "deletion_workspace_id": workspace_id,
            "updated_on": timezone.now(),
        }
        if row_ids is not None:
            # Ordered to avoid deadlocks when updating the same cells.
            self.queue_model.objects_and_trash.bulk_create(
                [
                    self.queue_model(field_id=field_id, row_id=row_id, **marked)
                    for field_id in sorted(set(field_ids))
                    for row_id in sorted(set(row_ids))
                ],
                update_conflicts=True,
                unique_fields=["field_id", "row_id"],
                update_fields=list(marked),
                batch_size=1000,
            )
            return

        # The rows are covered by the deletion of the whole field.
        self.queue_model.objects_and_trash.filter(
            field_id__in=field_ids, row_id__isnull=False
        )._raw_delete(using=router.db_for_write(self.queue_model))
        full_updates = self.queue_model.objects_and_trash.filter(
            field_id__in=field_ids, row_id=None
        )
        marked_field_ids = set(full_updates.values_list("field_id", flat=True))
        full_updates.update(**marked)
        self.queue_model.objects_and_trash.bulk_create(
            [
                self.queue_model(field_id=field_id, row_id=None, **marked)
                for field_id in sorted(set(field_ids) - marked_field_ids)
            ]
        )

    def delete_data_marked_for_deletion(self):
        workspace_ids = (
            self.queue_model.objects_and_trash.filter(
                deletion_workspace_id__isnull=False
            )
            .order_by("deletion_workspace_id")
            .values_list("deletion_workspace_id", flat=True)
            .distinct()
        )
        for workspace_id in workspace_ids:
            # Per workspace, so that a failing one doesn't prevent the others.
            try:
                with transaction.atomic():
                    self._delete_workspace_data_marked_for_deletion(workspace_id)
            except Exception as exc:
                logger.error(
                    "Failed to delete semantic search data for workspace {}: {}",
                    workspace_id,
                    exc,
                )

    def _delete_workspace_data_marked_for_deletion(self, workspace_id: int):
        # Marked later, so not yet seen by the deletion of the vectors.
        check_timestamp = timezone.now()
        marked_updates = self.queue_model.objects_and_trash.filter(
            deletion_workspace_id=workspace_id, updated_on__lte=check_timestamp
        )
        SemanticSearchVectorTable(workspace_id).delete_marked(marked_updates)
        marked_updates._raw_delete(using=router.db_for_write(self.queue_model))

    def queue(
        self,
        table: Table,
        field_ids: list[int] | None = None,
        row_ids: list[int] | None = None,
    ) -> bool:
        # Checked before the license, because most tables don't have semantic
        # search fields and this runs for every change.
        semantic_search_fields = list(
            self._get_semantic_search_fields(table, field_ids)
        )
        if not semantic_search_fields:
            return False

        handler = SemanticSearchHandler()
        if row_ids is not None and handler.can_index(table.database.workspace):
            # A few changed rows don't make the field show that it's being indexed.
            self.queue_pending_updates(
                [
                    semantic_search_field.field_id
                    for semantic_search_field in semantic_search_fields
                ],
                row_ids,
            )
            return True

        # While indexing is paused, one update of all rows replaces any number of
        # changed rows, and it's cheap because unchanged values are skipped.
        handler.queue_full_updates(table, semantic_search_fields, start_indexing=False)
        return True

    def prepare(self, table: Table) -> bool:
        handler = SemanticSearchHandler()
        workspace = table.database.workspace
        if (
            workspace is None
            or not handler.can_index(workspace)
            or handler.is_retry_postponed(table)
        ):
            return False
        SemanticSearchVectorTable(workspace.id).create_if_not_exists()
        return True

    def _get_indexer(
        self, table: Table, field_id: int, deadline: Optional[float]
    ) -> Optional[_FieldIndexer]:
        """
        :param table: The table of the field.
        :param field_id: The field that's indexed.
        :param deadline: The `time.monotonic()` after which no new batch is started.
        :return: None if the field can't be indexed anymore, for example because
            semantic search was disabled or the field was trashed. It's indexed
            again when it's restored.
        """

        handler = SemanticSearchHandler()
        semantic_search_field = (
            self._get_semantic_search_fields(table, [field_id])
            .select_related("field")
            .first()
        )
        if semantic_search_field is None:
            return None
        field = semantic_search_field.field.specific
        semantic_search_field_type = handler.get_semantic_search_field_type(field)
        if semantic_search_field_type is None:
            return None
        return _FieldIndexer(
            field,
            semantic_search_field_type,
            table.get_model(),
            SemanticSearchVectorTable(table.database.workspace_id),
            deadline,
        )

    def process_full_field_updates(
        self,
        table: Table,
        updates: list[SemanticSearchPendingUpdate],
        check_timestamp: datetime,
        deadline: Optional[float],
    ) -> bool:
        for update in updates:
            indexer = self._get_indexer(table, update.field_id, deadline)
            if indexer is not None and not indexer.index_all_rows(
                update, check_timestamp
            ):
                return False
        return True

    def process_row_updates(
        self,
        table: Table,
        updates: list[SemanticSearchPendingUpdate],
        deadline: Optional[float],
    ) -> int:
        processed = 0
        for field_id, field_updates in groupby(updates, lambda update: update.field_id):
            row_ids = [update.row_id for update in field_updates]
            indexer = self._get_indexer(table, field_id, deadline)
            indexed = len(row_ids) if indexer is None else indexer.index_rows(row_ids)
            processed += indexed
            if indexed < len(row_ids):
                break
        return processed

    def process_pending_updates(
        self, table: Table, deadline: Optional[float] = None
    ) -> bool:
        handler = SemanticSearchHandler()
        try:
            completed = super().process_pending_updates(table, deadline)
        finally:
            handler.mark_indexed(table)
        handler.clear_indexing_failures(table)
        return completed

    def get_retry_countdown(self, table: Table, exception: Exception) -> int | None:
        if not isinstance(exception, EmbeddingsServiceError):
            return None
        countdown = SemanticSearchHandler().mark_indexing_failed(table)
        logger.warning(
            "Semantic search indexing of table {} failed, retrying in {}s.",
            table.id,
            countdown,
        )
        return countdown
