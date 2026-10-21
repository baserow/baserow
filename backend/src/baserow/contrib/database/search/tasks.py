from datetime import datetime, timedelta, timezone
from typing import List, Optional

from django.conf import settings
from django.db import InterfaceError, OperationalError
from django.db.models import Q

from celery_singleton import Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.table.exceptions import TableDoesNotExist

PERIODIC_CHECK_MINUTES = 15
PERIODIC_CHECK_TIME_LIMIT = 60 * PERIODIC_CHECK_MINUTES  # 15 minutes.


# Transient connection drops (e.g. managed-Postgres failover or pooler restart)
# can fail a brand-new connection during connect(); CONN_HEALTH_CHECKS can't catch
# those. Retry a few times since this task is idempotent.
@app.task(
    bind=True,
    queue="export",
    autoretry_for=(OperationalError, InterfaceError),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=max(1, settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT - 30),
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def schedule_update_search_data(
    self,
    table_id: int,
    field_ids: Optional[List[int]] = None,
    row_ids: Optional[List[int]] = None,
):
    """
    Schedules the `update_search_data` task for a table to initialize the search vectors
    or when changes occur. Field- or row-specific updates are queued first to avoid any
    lost updates. Then the singleton task is enqueued; if it’s already scheduled, a
    pending flag is set so new changes will be processed once the current run finishes.

    When ``field_ids`` is provided, pending work is queued for those fields. When
    ``row_ids`` is provided, pending work is limited to those rows. A bare table-level
    call should therefore expand to full-field updates before reaching this task, rather
    than passing ``field_ids=None`` and ``row_ids=None`` and expecting pending work to
    be created here.

    :param table_id: The ID of the table to update the search data for.
    :param field_ids: Optional list of field IDs to update. If provided, only these
        fields will be updated in the search data.
    :param row_ids: Optional list of row IDs to update. If provided, only these rows
        will be updated in the search data.
    """

    from baserow.contrib.database.search.registries import search_data_updater_registry
    from baserow.contrib.database.table.handler import TableHandler

    table = None
    types_to_schedule = []
    for search_data_updater_type in search_data_updater_registry.get_all():
        if not search_data_updater_type.should_queue():
            continue

        # If any specific update is requested, queue it so it can be processed later.
        new_pending_updates = False
        if field_ids or row_ids:
            if table is None:
                try:
                    table = TableHandler().get_table(table_id)
                except TableDoesNotExist:
                    logger.warning(f"Table with id {table_id} doesn't exist.")
                    return
            new_pending_updates = search_data_updater_type.queue(
                table, field_ids, row_ids
            )
            if not new_pending_updates:
                continue
        # Without changes, like from the periodic check, only the types with pending
        # updates are started.
        elif not search_data_updater_type.has_pending_updates(table_id):
            continue

        types_to_schedule.append((search_data_updater_type, new_pending_updates))

    # Scheduled after all changes are queued, so that a failing broker can't prevent
    # another type from queuing them. The periodic check starts the tasks that
    # couldn't be scheduled.
    for search_data_updater_type, new_pending_updates in types_to_schedule:
        try:
            search_data_updater_type.schedule(table_id, new_pending_updates)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Could not schedule the {} update of table {}.",
                search_data_updater_type.type,
                table_id,
            )


@app.task(queue="export")
def schedule_search_data_updater_task(search_data_updater_type: str, table_id: int):
    """
    Schedules the update task of one search data updater, without starting the update
    tasks of the other types.

    :param search_data_updater_type: The type of the search data updater.
    :param table_id: The table of which the pending updates are processed.
    """

    from baserow.contrib.database.search.registries import search_data_updater_registry

    search_data_updater_registry.get(search_data_updater_type).schedule(table_id)


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    raise_on_duplicate=True,
    lock_expiry=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    soft_time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
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
    """

    from baserow.contrib.database.search.registries import search_data_updater_registry
    from baserow.contrib.database.search.search_data_updater_types import (
        FullTextSearchDataUpdaterType,
    )

    search_data_updater_registry.get(FullTextSearchDataUpdaterType.type).update(
        table_id
    )


@app.task(
    queue="export",
    base=Singleton,
    raise_on_duplicate=False,
    soft_time_limit=PERIODIC_CHECK_TIME_LIMIT,
    time_limit=PERIODIC_CHECK_TIME_LIMIT,
    lock_expiry=PERIODIC_CHECK_TIME_LIMIT,
)
def periodic_check_pending_search_data():
    """
    Periodically checks for any pending search data updates and processes them.
    It deletes all the pending updates that are marked for deletion and tries to
    re-schedule the update task for any table that has pending updates. It may be that
    the original task stopped before completing, so this task ensures that any
    pending updates are eventually processed.
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.search.registries import search_data_updater_registry

    # Remove pending update entries for data that's already been deleted. Since
    # those records have been permanently deleted from the database, nothing
    # should try to update their search data, so this call won’t interfere with
    # any running tasks.
    for search_data_updater_type in search_data_updater_registry.get_all():
        search_data_updater_type.delete_data_marked_for_deletion()

    if SearchHandler.full_text_enabled():
        # Delete any stale pending update that is waiting for too long.
        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(
            hours=settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED
        )
        SearchHandler.delete_pending_updates(Q(updated_on__lt=cutoff_time))

    # Verify if there are any pending updates to process and try to re-schedule the
    # singleton table tasks in case the original one stopped before completing.
    table_ids_with_pending_updates = sorted(
        {
            table_id
            for search_data_updater_type in search_data_updater_registry.get_all()
            for table_id in search_data_updater_type.get_table_ids_with_pending_updates()
        }
    )
    for table_id in table_ids_with_pending_updates:
        # A transient DB error on one table shouldn't skip the remaining tables;
        # they'll be retried on the next periodic run anyway.
        try:
            schedule_update_search_data(table_id)
        except (OperationalError, InterfaceError) as exc:
            logger.warning(
                "Database error scheduling search update for table {}, will retry "
                "on the next periodic run: {}",
                table_id,
                exc,
            )


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=PERIODIC_CHECK_MINUTES),
        periodic_check_pending_search_data.s(),
    )
