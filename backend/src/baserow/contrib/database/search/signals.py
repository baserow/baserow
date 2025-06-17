from functools import partial

from django.db.models.signals import post_delete
from django.dispatch import receiver

from loguru import logger

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.tasks import migrate_search_data_table
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.tasks import (
    enqueue_task_on_commit_swallowing_any_exceptions,
)
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.models import Workspace
from baserow.core.signals import workspace_created
from baserow.core.trash.signals import permanently_deleted


@receiver(workspace_created)
def create_search_table_for_workspace(sender, workspace: "Workspace", **kwargs):
    """
    This handler creates for any new workspace two objects accompanying:
    * workspace-wide row for settings for all database applications
    * per-workspace search data table.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_search_table_for_workspace(workspace.id)


@receiver(permanently_deleted, sender="row")
def handle_permanently_deleted_row(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a row is removed physically, then search data should be cleaned from data
    for that row.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    try:
        # table may be already removed if this is called by parent's trash handler.
        table = TableHandler().get_table(parent_id)
    except TableDoesNotExist:
        return
    SearchHandler.cleanup_table_rows_vectors(table, [trash_item_id])


@receiver(permanently_deleted, sender="rows")
def handle_permanently_deleted_rows(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a set of row is removed physically, then search data should be cleaned from
    data for those rows.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    try:
        # table may be already removed if this is called by parent's trash handler.
        table = TableHandler().get_table(parent_id)
    except TableDoesNotExist:
        return
    SearchHandler.cleanup_table_rows_vectors(table, trash_item.row_ids)


@receiver(permanently_deleted, sender="workspace")
def handle_permanently_deleted_workspace(
    sender, trash_item_id, trash_item: "Workspace", parent_id, *args, **kwargs
):
    """
    Triggered when a workspace is being removed by the trash subsystem. This handler
    will remove search table for the workspace, if it was created.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.remove_search_table_for_workspace(trash_item_id)


@receiver(view_loaded)
def view_loaded_maybe_create_tsvector(
    sender,
    table: "Table",
    table_model: type["GeneratedTableModel"],
    **kwargs,
):
    """
    Triggered when a `View` has been "loaded" (dispatched a GET
    via the API) by an API consumer. This receiver ensures that we can
    trigger some maintenance tasks when this event occurs, such as
    ensuring the table is migrated to search data infrastructure.

    :param sender: Sender of the signal
    :param table: The Table which was accessed, directly or via a View.
    :param table_model: The GeneratedTableModel for this Table.
    :return: None
    """

    from baserow.contrib.database.search.handler import SearchHandler

    if not SearchHandler.full_text_enabled() or table.search_data_state in {
        SearchTableState.READY,
        SearchTableState.DISABLED,
    }:
        return

    logger.info(
        "Table {table_id} can populate search vectors.",
        table_id=table.id,
    )

    enqueue_task_on_commit_swallowing_any_exceptions(
        partial(migrate_search_data_table.delay, table_id=table.id)
    )


@receiver(post_delete, sender=Field)
def clean_up_tsv_after_field_deleted(sender, instance, origin, **kwargs):
    """
    Triggered when a field is permanently removed by Trash subsystem. If a table was
    migrated to search data table infrastructure (it should be at this point, but there
    is no guarantee that a removal happened before), this handler will remove all
    entries from a workspace-wide search data table that points to the removed field.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.after_field_perm_delete(instance)
