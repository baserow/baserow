from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from loguru import logger

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import drop_table
from baserow.contrib.database.search.tasks import schedule_table_search_data_update
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.tasks import (
    enqueue_task_on_commit_swallowing_any_exceptions,
)
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.models import Workspace
from baserow.core.signals import workspace_created
from baserow.core.trash.signals import permanently_deleted

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel, Table


@receiver(workspace_created)
def create_search_table_for_workspace(sender, workspace: "Workspace", **kwargs):
    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_search_table_for_workspace(workspace)


@receiver(permanently_deleted, sender="row")
def handle_permanently_deleted_row(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    from baserow.contrib.database.search.handler import SearchHandler

    table = TableHandler().get_table(parent_id)
    SearchHandler.cleanup_table_rows_vectors(table, [trash_item_id])


@receiver(permanently_deleted, sender="rows")
def handle_permanently_deleted_rows(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    from baserow.contrib.database.search.handler import SearchHandler

    table = TableHandler().get_table(parent_id)
    SearchHandler.cleanup_table_rows_vectors(table, trash_item.row_ids)


# @receiver(permanently_deleted, sender='table')
# def handle_permanently_deleted_table(sender, trash_item_id, trash_item, parent_id, *args, **kwargs):
#     from baserow.contrib.database.search.handler import SearchHandler
#     SearchHandler.cleanup_table_rows_vectors(trash_item)


@receiver(permanently_deleted, sender="workspace")
def handle_permanently_deleted_workspace(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    from baserow.contrib.database.search.handler import SearchHandler
    search_table = SearchHandler.remove_search_table_for_workspace(trash_item_id)


# @receiver([rows_updated, rows_deleted, rows_created])
# def migrate_table_search_on_modification(sender, user, table, **kwargs):
#     from baserow.contrib.database.search.handler import SearchHandler
#     workspace_id = table.database.workspace_id
#     logger.info(f'Starting table search migration for {table} after {sender}
#     from {user}')
#     SearchHandler._trigger_async_workspacesearchtable_task_if_needed(workspace_id)


#


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
    ensuring its corresponding table has a `tsvector` column ready for
    searching against.
    :param sender: Sender of the signal
    :param table: The Table which was accessed, directly or via a View.
    :param table_model: The GeneratedTableModel for this Table.
    :return: None
    """

    from baserow.contrib.database.search.handler import SearchHandler

    if not SearchHandler.full_text_enabled() or table.search_data_state in {
        SearchTableState.DONE,
        SearchTableState.INITED,
        SearchTableState.DISABLED,
    }:
        return

    logger.info(
        "Table {table_id} can populate search vectors.",
        table_id=table.id,
    )

    enqueue_task_on_commit_swallowing_any_exceptions(
        lambda: schedule_table_search_data_update.delay(
            table_id=table.id, update_tsvectors_for_changed_rows_only=False
        )
    )


@receiver(post_delete, sender=Field)
def clean_up_tsv_after_field_deleted(sender, instance, origin, **kwargs):
    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.after_field_perm_delete(instance)

#
# @receiver(post_delete, sender=Workspace)
# def clean_up_workspace_search(sender, instance, using, origin, **kwargs):
#     from baserow.contrib.database.search.handler import SearchHandler
#
#     SearchHandler.remove_search_table_for_workspace(instance.id)
