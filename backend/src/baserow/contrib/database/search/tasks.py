from typing import List, Optional

from django.conf import settings
from django.core.cache import cache

from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.table.exceptions import TableDoesNotExist


class PendingSearchUpdateFlag:
    """
    Flag is used to indicate that a search data update task is pending for a
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
def schedule_update_search_data(
    table_id: int,
    field_ids: Optional[List[int]] = None,
    row_ids: Optional[List[int]] = None,
):
    """
    Schedules the `update_search_data` task for a table when changes occur. Field- or
    row-specific updates are queued first to avoid any lost updates. Then the singleton
    task is enqueued; if it’s already scheduled, a pending flag is set so new changes
    will be processed once the current run finishes.

    :param table_id: The ID of the table to update the search data for.
    :param field_ids: Optional list of field IDs to update. If provided, only these
        fields will be updated in the search data.
    :param row_ids: Optional list of row IDs to update. If provided, only these rows
        will be updated in the search data.
    :raises TableDoesNotExist: If the table with the given ID does not exist.
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    if not SearchHandler.full_text_enabled():
        return

    # If any specific update is requested, queue it so it can be processed later.
    if field_ids or row_ids:
        try:
            table = TableHandler().get_table(table_id)
        except TableDoesNotExist:
            logger.warning(f"Table with id {table_id} doesn't exist.")
            return

        SearchHandler.queue_pending_search_update(
            table=table, field_ids=field_ids, row_ids=row_ids
        )

    try:
        # debounce the task to avoid multiple calls in a short time
        update_search_data.s(table_id).apply_async(
            countdown=settings.PG_FULLTEXT_SEARCH_UPDATE_DATA_THROTTLE_SECONDS
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
    Updates the search data for a specific table. This task is scheduled to run
    every time there are changes in the table that require the search data to be
    updated. It runs as singleton for the given table to avoid concurrent updates
    that could lead to deadlocks. It's also usually debounced to avoid
    process multiple updates on the same rows/fields in a short time.

    :param table_id: The ID of the table to update the search data for.
    :raises TableDoesNotExist: If the table with the given ID does not exist.
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

    # Make sure the search table exists for the workspace first.
    workspace_id = table.database.workspace_id
    SearchHandler.create_workspace_search_table_if_not_exists(workspace_id)

    # Ensure every table field exists in the search table.
    # Used during migrations or when explicitly reinitializing search data.
    SearchHandler.initialize_missing_search_data(table)

    # Make sure newer updates will re-schedule this task at the end if needed.
    flag = PendingSearchUpdateFlag(table_id)
    flag.clear()

    SearchHandler.process_search_data_updates(table)

    # If new updates were queued during processing, schedule another update
    if flag.get():
        logger.debug(
            f"New updates detected, rescheduling the task for table {table_id}."
        )
        schedule_update_search_data.delay(table_id)


@app.task(queue="export")
def delete_search_data(
    table_id: int, field_ids: List[int] | None, row_ids: List[int] | None = None
):
    """
    Deletes search data for a specific table and optionally for specific rows.
    This task is used when rows are deleted or when the search data needs to be
    cleared for a table.

    :param table_id: The ID of the table to delete the search data for.
    :param field_ids: Optional list of field IDs to delete from the search data.
        If provided, only these fields will be deleted from the search data.
    :param row_ids: Optional list of row IDs to delete. If provided, only these
        rows will be deleted from the search data.
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    try:
        table = TableHandler().get_table(table_id)
    except TableDoesNotExist:
        logger.warning(f"Table with id {table_id} doesn't exist.")
        return

    SearchHandler.delete_search_data(table, field_ids=field_ids, row_ids=row_ids)
