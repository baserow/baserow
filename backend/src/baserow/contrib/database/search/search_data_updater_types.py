from datetime import datetime
from typing import Optional

from django.conf import settings

from loguru import logger

from baserow.contrib.database.table.models import Table

from .handler import SearchHandler
from .models import PendingSearchValueUpdate
from .registries import SearchDataUpdaterType


class FullTextSearchDataUpdaterType(SearchDataUpdaterType):
    type = "full_text"
    queue_model = PendingSearchValueUpdate
    reschedule_flag_key_prefix = "database_search_data_lock"
    # Balance between query efficiency and cpu-usage for complex search expressions.
    full_field_batch_size = 3
    atomic_batches = True

    @property
    def row_batch_size(self) -> int:
        return settings.SEARCH_UPDATE_BATCH_SIZE

    def get_update_task(self):
        from .tasks import update_search_data

        return update_search_data

    def get_throttle_seconds(self) -> int:
        return settings.PG_FULLTEXT_SEARCH_UPDATE_DATA_THROTTLE_SECONDS

    def get_time_budget_seconds(self) -> int:
        # Leave a safety margin so the task can finish cleanly before the hard limit.
        hard_limit = settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT
        if hard_limit <= 30:
            logger.warning(
                "CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT={}s is at or below the 30s "
                "safety margin; the task may be killed before it can finish.",
                hard_limit,
            )
        return max(1, hard_limit - 30)

    def has_pending_updates(self, table_id: int) -> bool:
        # The update task also initializes the search data of new fields.
        return True

    def should_queue(self) -> bool:
        return SearchHandler.full_text_enabled()

    def get_queued_field_ids(
        self, table: Table, field_ids: list[int] | None
    ) -> list[int]:
        searchable_field_ids = {
            field.id
            for field in table.get_model().get_searchable_fields(include_trash=True)
        }
        if field_ids is None:
            return list(searchable_field_ids)
        return [
            field_id for field_id in set(field_ids) if field_id in searchable_field_ids
        ]

    def prepare(self, table: Table) -> bool:
        if not SearchHandler.full_text_enabled():
            logger.warning(
                "Task called, but full-text-search is disabled. This should not happen."
            )
            return False

        # Make sure the search table exists for the workspace first.
        SearchHandler.create_workspace_search_table_if_not_exists(
            table.database.workspace_id
        )
        # Ensure every table field exists in the search table.
        # Used during migrations or when explicitly reinitializing search data.
        SearchHandler.initialize_missing_search_data(table)
        return True

    def process_full_field_updates(
        self,
        table: Table,
        updates: list[PendingSearchValueUpdate],
        check_timestamp: datetime,
        deadline: Optional[float],
    ) -> bool:
        SearchHandler.update_search_data(
            table, field_ids=[update.field_id for update in updates]
        )
        return True

    def process_row_updates(
        self,
        table: Table,
        updates: list[PendingSearchValueUpdate],
        deadline: Optional[float],
    ) -> int:
        SearchHandler.update_search_data(
            table,
            field_ids=list({update.field_id for update in updates}),
            row_ids=list({update.row_id for update in updates}),
        )
        return len(updates)
