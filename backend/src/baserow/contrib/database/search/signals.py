from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.search.tasks import schedule_search_data_update
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
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

    SearchHandler.create_workspace_search_table(workspace.id)


@receiver(permanently_deleted, sender="row")
def handle_permanently_deleted_row(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a row is permanently deleted, then related search data should be cleaned
    from search data table.
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

    SearchHandler.delete_workspace_search_table(trash_item_id)


@receiver(view_loaded)
def view_loaded_schedule_search_data_update(
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

    if not SearchHandler.full_text_enabled():
        return

    tsvector_fields_to_initialize = any(
        f
        for f in table_model.get_searchable_fields()
        if f.search_data_initialized_at is None
    )
    if tsvector_fields_to_initialize:
        transaction.on_commit(lambda: schedule_search_data_update.delay(table.id))


@receiver(permanently_deleted, sender="field")
def delete_search_data_for_field(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a field is permanently deleted, then related search data should be cleaned
    from search data table.
    """

    from baserow.contrib.database.search.handler import SearchHandler

    try:
        table = TableHandler().get_table(parent_id)
    except TableDoesNotExist:
        return

    SearchHandler.delete_search_data(table, field_ids=[trash_item_id])
