from typing import List, Optional

from django.conf import settings
from django.core.cache import cache

from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.table.exceptions import TableDoesNotExist


class PendingSearchUpdateFlag:
    """
    This flag is used to indicate that a search data update task is pending for a
    specific table and it has not been possible to schedule it yet due to a concurrent
    task already running for the same table.

    When the task ends, if this flag is set, it will re-schedule itself to ensure that
    the search data is eventually updated.
    """

    def __init__(self, table_id: int):
        self.table_id = table_id

    @property
    def key(self):
        """
        Returns the cache key to use for the table lock.
        """

        return f"database_search_data_lock_{self.table_id}"

    def get(self):
        """
        Gets the lock for the search data update task.

        :return: True if the lock is set, False otherwise.
        """

        return cache.get(key=self.key)

    def set(self):
        """
        Sets the lock for the search data update task.
        """

        return cache.set(
            key=self.key,
            value=True,
            timeout=settings.AUTO_INDEX_LOCK_EXPIRY * 2,
        )

    def clear(self):
        """
        Clears the lock for the search data update task.
        """

        return cache.delete(key=self.key)


@app.task(queue="export")
def schedule_search_data_update(
    table_id: int,
    field_ids: Optional[List[int]] = None,
    row_ids: Optional[List[int]] = None,
):
    """
    TODO
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    if not SearchHandler.full_text_enabled():
        return

    try:
        table = TableHandler().get_table(table_id)
    except TableDoesNotExist:
        logger.warning(f"Table with id {table_id} doesn't exist.")
        return

    SearchHandler.add_pending_search_update(
        table=table, field_ids=field_ids, row_ids=row_ids
    )

    try:
        # debounce the task to avoid multiple calls in a short time
        update_search_data.s(table_id).apply_async(
            countdown=settings.SEARCH_DATA_UPDATE_GRACE_PERIOD
        )
    except DuplicateTaskError:
        PendingSearchUpdateFlag(table_id).set()


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    lock_expiry=settings.AUTO_INDEX_LOCK_EXPIRY,
    raise_on_duplicate=True,
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def update_search_data(table_id: int):
    """
    TODO
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    if not SearchHandler.full_text_enabled():
        logger.warning(
            "Task called, but full-text-search is disabled. This should not happen."
        )
        return

    try:
        table = TableHandler().get_table(table_id)
    except TableDoesNotExist:
        logger.warning(f"Table with id {table_id} doesn't exist.")
        return

    SearchHandler.initialize_search_data_for_fields(table)

    # Let's clear the flag now to make sure newer updates won't be lost while this
    # task is running.
    flag = PendingSearchUpdateFlag(table_id)
    flag.clear()

    SearchHandler.process_search_data_updates(table)

    if flag.get():
        logger.debug(
            "There are new pending changes to process. "
            f"Scheduling another update for {table_id}"
        )
        schedule_search_data_update.delay(table_id)


@app.task(queue="export")
def create_workspace_search_table(workspace_id: int):
    """
    Create a workspace search table if it does not exist yet.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table(workspace_id)
