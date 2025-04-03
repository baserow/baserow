import itertools
import traceback
from typing import List, Optional

from django.conf import settings

from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.exceptions import (
    PostgresFullTextSearchDisabledException,
)
from baserow.contrib.database.table.models import Table


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_tsvector_columns(
    table_id: int,
    update_tsvs_for_changed_rows_only: bool,
    field_ids_to_restrict_update_to: Optional[List[int]] = None,
):
    """
    Responsible for asynchronously updating the `tsvector` columns on a table.

    :param table_id: The ID of the table we'd like to update the tsvectors for.
    :param update_tsvs_for_changed_rows_only: By default we will only update rows on
        the table which have changed since the last search update.
        If set to `False`, we will index all cells that match the other parameters.
    :param field_ids_to_restrict_update_to: If provided only the fields matching the
        provided ids will have their tsv columns updated.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    try:
        table = Table.objects_and_trash.get(id=table_id)
    except Table.DoesNotExist:
        logger.warning(
            f"Could not find table with id {table_id} for updating tsvector columns."
        )
        return
    try:
        SearchHandler.update_tsvector_columns_locked(
            table, update_tsvs_for_changed_rows_only, field_ids_to_restrict_update_to
        )
    except PostgresFullTextSearchDisabledException:
        logger.debug(f"Postgres full-text search is disabled.")


@app.task(
    queue="export",
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def async_update_multiple_fields_tsvector_columns(
    field_ids: List[int],
    update_tsvs_for_changed_rows_only: bool,
):
    """
    Responsible for asynchronously updating the `tsvector` columns for all the fields
    provided.

    :param field_ids: The fields we'd like to update the tsvectors for.
    :param update_tsvs_for_changed_rows_only: By default we will only update rows on the
        table which have changed since the last search update. If set to `False`, we
        will index all cells that match the other parameters.
    """

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
                table, update_tsvs_for_changed_rows_only, [f.id for f in table_fields]
            )
        except PostgresFullTextSearchDisabledException:
            logger.debug(f"Postgres full-text search is disabled.")
            break
        except Exception:
            tb = traceback.format_exc()
            field_ids = ", ".join(str(field.id) for field in field_group)
            logger.error(
                "Failed to update tsvector columns for fields {field_ids} in table {table_id} because of: \n{tb}.",
                field_ids=field_ids,
                table_id=table.id,
                tb=tb,
            )
