import itertools
import traceback
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.exceptions import TableDoesNotExist


def get_lock_key_name(table_id: int) -> str:
    return f"search_data_table_lock_{table_id}"


def get_search_data_update_lock_key(table_id: int) -> bool | None:
    return cache.get(get_lock_key_name(table_id))


def set_search_data_update_lock_key(table_id: int):
    """
    Marks that search data for table with `table_id` is going to be updated. This tells
    that there's no need to schedule another
    `schedule_table_search_data_update`/`do_table_search_data_update` task for some
    time, as one is already waiting.
    """

    return cache.set(
        key=get_lock_key_name(table_id),
        value=True,
        timeout=settings.SEARCH_DATA_UPDATE_GRACE_PERIOD * 2,
    )


def clear_search_update_lock_key(table_id: int):
    return cache.delete(key=get_lock_key_name(table_id))


def schedule_table_search_data_update(table_id: int):
    # key exists, not scheduling anything
    if get_search_data_update_lock_key(table_id):
        logger.warning(f"Search daa already scheduled for table {table_id}")
        return
    set_search_data_update_lock_key(table_id)
    try:
        # run after a small delay.
        do_table_search_data_update.s(table_id=table_id).apply_async(
            countdown=settings.SEARCH_DATA_UPDATE_GRACE_PERIOD
        )
    except DuplicateTaskError:
        pass


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    lock_expiry=settings.AUTO_INDEX_LOCK_EXPIRY,
    raise_on_duplicate=True,
)
def do_table_search_data_update(table_id: int):
    """
    Updates search data for a table identified by `table_id` id.
    """

    # Allow scheduling next items
    clear_search_update_lock_key(table_id)

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    if not SearchHandler.full_text_enabled():
        logger.info("FTS disabled. Exiting.")
        return
    try:
        table = TableHandler().get_table(table_id)
    except TableDoesNotExist:
        logger.warning(f"Table with id {table_id} doesn't exist.")
        return
    if not SearchHandler.table_is_active(table):
        logger.info(f"Table {table} disabled from migration")
        return

    if not SearchHandler.table_is_migrated(table):
        logger.warning(f"table {table} not migrated")
        return

    def process():
        SearchHandler.process_table_data_changes(table)
        SearchHandler.cleanup_old_vectors(table)

    with transaction.atomic():
        process()

    if get_search_data_update_lock_key(table_id):
        logger.info(f"Scheduling another update for {table_id}")
        schedule_table_search_data_update(table_id=table_id)


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def create_search_table_for_workspace(workspace_id: int):
    """
    Create a workspace settings table for database app.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_search_table_for_workspace(workspace_id)


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    lock_expiry=settings.AUTO_INDEX_LOCK_EXPIRY,
    raise_on_duplicate=True,
)
def migrate_search_data_table(table_id: int):
    """
    Migrate table tsv fields to search data table.
    """

    if get_search_data_update_lock_key(table_id):
        logger.debug(f"search data lock present for {table_id}")
        return
    set_search_data_update_lock_key(table_id)

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import Table, TableHandler

    try:
        table = TableHandler().get_table(table_id)
    except Table.DoesNotExist:
        logger.warning(
            f"Could not find table with id {table_id} to update tsvector columns."
        )
        return
    # ensure we have workspace-wide settings and table

    SearchHandler.create_search_table_for_workspace(table.database.workspace_id)
    if table.search_data_state in {SearchTableState.READY, SearchTableState.DISABLED}:
        return
    logger.info(f"Attempt to migrate {table}")
    try:
        SearchHandler.migrate_table_tsvectors(table)
    except Exception as err:
        logger.opt(exception=err).error(
            f"Cannot create workspace settings and migrate {table}: {err}"
        )


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_tsvector_columns_v1(
    table_id: int,
    update_tsvectors_for_changed_rows_only: bool,
    field_ids_to_restrict_update_to: Optional[List[int]] = None,
):
    """
    Responsible for asynchronously updating the `tsvector` columns on a table.

    NOTE: This task is kept for backward compatibility.

    :param table_id: The ID of the table we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update.
        If set to `False`, we will index all cells that match the other parameters.
    :param field_ids_to_restrict_update_to: If provided only the fields matching the
        provided ids will have their tsv columns updated.
    """

    from baserow.contrib.database.search.handler import SearchHandlerCompat
    from baserow.contrib.database.table.models import Table

    try:
        table = Table.objects_and_trash.get(id=table_id)
    except Table.DoesNotExist:
        logger.warning(
            f"Could not find table with id {table_id} for updating tsvector columns."
        )
        return
    try:
        SearchHandlerCompat.update_tsvector_columns_locked(
            table,
            update_tsvectors_for_changed_rows_only,
            field_ids_to_restrict_update_to,
        )
    except PostgresFullTextSearchDisabledException:
        logger.debug("Postgres full-text search is disabled.")


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_multiple_fields_tsvector_columns_v1(
    field_ids: List[int],
    update_tsvectors_for_changed_rows_only: bool,
):
    """
    Responsible for asynchronously updating the `tsvector` columns for all the fields
    provided.

    NOTE: This task is kept for backward compatibility.

    :param field_ids: The fields we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update. If set to
        `False`, we will index all cells that match the other parameters.
    """

    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.search.handler import SearchHandlerCompat

    fields = (
        Field.objects_and_trash.filter(id__in=field_ids)
        .select_related("table")
        .order_by("table_id")
    )
    for _, field_group in itertools.groupby(fields, lambda f: f.table_id):
        table_fields = list(field_group)
        table = table_fields[0].table
        try:
            SearchHandlerCompat.update_tsvector_columns_locked(
                table,
                update_tsvectors_for_changed_rows_only,
                [f.id for f in table_fields],
            )
        except PostgresFullTextSearchDisabledException:
            logger.debug("Postgres full-text search is disabled.")
            break
        except Exception:
            tb = traceback.format_exc()
            field_ids = ", ".join(str(field.id) for field in field_group)
            logger.error(
                "Failed to update tsvector columns for fields {field_ids} "
                "in table {table_id} because of: \n{tb}.",
                field_ids=field_ids,
                table_id=table.id,
                tb=tb,
            )
