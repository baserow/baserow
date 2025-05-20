import itertools
import traceback
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction

from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.search.types import SearchTableState


def get_lock_key_name(table_id):
    return f"search_data_table_lock_{table_id}"


def get_search_data_update_lock_key(table_id):
    return cache.get(get_lock_key_name(table_id))


def set_search_data_update_lock_key(table_id: int):
    return cache.set(
        key=get_lock_key_name(table_id),
        value=True,
        timeout=20,
    )


def clear_search_update_lock_key(table_id: int):
    return cache.delete(key=get_lock_key_name(table_id))


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def schedule_table_search_data_update(table_id: int, *args, **kwargs):
    # key exists, not scheduling anything
    if get_search_data_update_lock_key(table_id):
        logger.info(f"already scheduled: {table_id}")
        return
    set_search_data_update_lock_key(table_id)
    try:
        # run after a small delay.
        do_table_search_data_update.apply_async(
            countdown=3, kwargs={"table_id": table_id, **kwargs}, args=args
        )
    except DuplicateTaskError:
        pass


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    lock_expiry=settings.AUTO_INDEX_LOCK_EXPIRY,
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    raise_on_duplicate=True,
)
def do_table_search_data_update(
    table_id: int,
    update_tsvectors_for_changed_rows_only: bool = True,
    field_ids_to_restrict_update_to: list[int] | None = None,
):
    # allow scheduling next items
    clear_search_update_lock_key(table_id)

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.handler import TableHandler

    table = TableHandler().get_table(table_id)
    if not SearchHandler._should_migrate(table):
        logger.info(f"Table {table} disabled from migration")
        return
    try:
        with transaction.atomic():
            SearchHandler.create_search_table_for_workspace(table.database.workspace_id)
    except DatabaseError:
        logger.info("Workspace migrated to new search table")

    if not SearchHandler.migrate_table_tsvectors(table):
        # table was already migrated, just update from latest changes
        logger.info(
            f"Running regular update: {table} "
            f"for {field_ids_to_restrict_update_to or 'all' } fields"
        )
        with transaction.atomic():
            SearchHandler.update_search_data_for_table(
                table,
                field_ids_to_restrict_update_to=field_ids_to_restrict_update_to,
                changed_since=update_tsvectors_for_changed_rows_only,
            )
            SearchHandler.cleanup_old_vectors(table)

        logger.info("Scheduling update if needed")
        if get_search_data_update_lock_key(table_id):
            schedule_table_search_data_update.delay(table_id=table_id)


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def create_search_table_for_workspace(workspace_id: int):
    """
    Create a workspace settings table for database app.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_search_table_for_workspace(workspace=workspace_id)


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_tsvector_columns(
    table_id: int,
    update_tsvectors_for_changed_rows_only: bool,
    field_ids_to_restrict_update_to: Optional[List[int]] = None,
    create_missing_workspace_configuration: bool = False,
):
    """
    Responsible for asynchronously updating the `tsvector` columns on a table.

    :param table_id: The ID of the table we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update.
        If set to `False`, we will index all cells that match the other parameters.
    :param field_ids_to_restrict_update_to: If provided only the fields matching the
        provided ids will have their tsv columns updated.
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.models import Table

    try:
        table = Table.objects_and_trash.get(id=table_id)
    except Table.DoesNotExist:
        logger.warning(
            f"Could not find table with id {table_id} to update tsvector columns."
        )
        return
    if create_missing_workspace_configuration and table.search_data_state not in {
        SearchTableState.INITED,
        SearchTableState.DONE,
        SearchTableState.DISABLED,
    }:
        logger.info(
            f"Attempt to create workspace settings for {table.database.workspace_id}"
        )
        try:
            SearchHandler.create_search_table_for_workspace(table.database.workspace_id)
            SearchHandler.migrate_table_tsvectors(table)
        except Exception as err:
            logger.opt(exception=err).error(
                f"Cannot create workspace settings and migrate {table}: {err}"
            )

    else:
        logger.info(
            f"No migration needed, updating search data for "
            f"table {table}: {table.search_data_state}"
        )
        try:
            SearchHandler.update_search_data_for_table(
                table,
                changed_since=update_tsvectors_for_changed_rows_only,
                field_ids_to_restrict_update_to=field_ids_to_restrict_update_to,
            )
        except PostgresFullTextSearchDisabledException:
            logger.debug("Postgres full-text search is disabled.")


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_multiple_fields_tsvector_columns(
    field_ids: List[int],
    update_tsvectors_for_changed_rows_only: bool,
):
    """
    Responsible for asynchronously updating the `tsvector` columns for all the fields
    provided.

    :param field_ids: The fields we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update. If set to
        `False`, we will index all cells that match the other parameters.
    """

    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.search.handler import SearchHandler

    fields = (
        Field.objects_and_trash.filter(id__in=field_ids)
        .select_related("table")
        .order_by("table_id")
    )
    for _, field_group in itertools.groupby(fields, lambda f: f.table_id):
        table_fields = list(field_group)
        table = table_fields[0].table
        try:
            SearchHandler.update_search_data_for_table(
                table,
                changed_since=update_tsvectors_for_changed_rows_only,
                field_ids_to_restrict_update_to=[f.id for f in table_fields],
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

    :param table_id: The ID of the table we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update.
        If set to `False`, we will index all cells that match the other parameters.
    :param field_ids_to_restrict_update_to: If provided only the fields matching the
        provided ids will have their tsv columns updated.
    """

    from baserow.contrib.database.search.handler import SearchHandler
    from baserow.contrib.database.table.models import Table

    try:
        table = Table.objects_and_trash.get(id=table_id)
    except Table.DoesNotExist:
        logger.warning(
            f"Could not find table with id {table_id} for updating tsvector columns."
        )
        return
    try:
        SearchHandler.update_tsvector_columns_locked(
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

    :param field_ids: The fields we'd like to update the tsvectors for.
    :param update_tsvectors_for_changed_rows_only: By default we will only update rows
        on the table which have changed since the last search update. If set to
        `False`, we will index all cells that match the other parameters.
    """

    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.search.handler import SearchHandler

    fields = (
        Field.objects_and_trash.filter(id__in=field_ids)
        .select_related("table")
        .order_by("table_id")
    )
    for _, field_group in itertools.groupby(fields, lambda f: f.table_id):
        table_fields = list(field_group)
        table = table_fields[0].table
        try:
            SearchHandler.update_tsvector_columns_locked(
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
