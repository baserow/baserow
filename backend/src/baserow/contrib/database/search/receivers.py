from django.dispatch import receiver

from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.models import Workspace
from baserow.core.trash.signals import before_permanently_deleted, permanently_deleted


@receiver(permanently_deleted, sender="workspace")
def handle_permanently_deleted_workspace(
    sender, trash_item_id, trash_item: "Workspace", parent_id, *args, **kwargs
):
    """
    Triggered when a workspace is permanently deleted. This handler
    will remove search table for the workspace, if exists.
    """

    SearchHandler.delete_workspace_search_table_if_exists(trash_item_id)


@receiver(before_permanently_deleted, sender="table")
def handle_permanently_deleted_table(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a table is permanently deleted, then related search data should be cleaned from
    search data table. This is also called by `DatabaseApplicationType.pre_delete` for
    every table before a database is permanently deleted, so it will clean up all tables
    in the database.
    """

    table = trash_item
    if SearchHandler.full_text_enabled():
        SearchHandler.mark_search_data_for_deletion(table)
    else:  # we can drop the entire search table if exists
        workspace_id = table.database.workspace_id
        SearchHandler.delete_workspace_search_table_if_exists(workspace_id)


@receiver(before_permanently_deleted, sender="field")
def handle_permanently_deleted_field(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a field is permanently deleted, then related search data should be cleaned
    from search data table.
    """

    field = trash_item
    table = field.table
    if SearchHandler.full_text_enabled():
        SearchHandler.mark_search_data_for_deletion(table, field_ids=[trash_item_id])
    else:  # we can drop the entire search table if exists
        workspace_id = table.database.workspace_id
        SearchHandler.delete_workspace_search_table_if_exists(workspace_id)


@receiver(before_permanently_deleted, sender="row")
def handle_permanently_deleted_row(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a row is permanently deleted, then related search data should be cleaned
    from search data table.
    """

    row = trash_item
    if SearchHandler.full_text_enabled():
        SearchHandler.mark_search_data_for_deletion(row.baserow_table, row_ids=[row.id])
    else:  # we can drop the entire search table if exists
        workspace_id = row.baserow_table.database.workspace_id
        SearchHandler.delete_workspace_search_table_if_exists(workspace_id)


@receiver(before_permanently_deleted, sender="rows")
def handle_permanently_deleted_rows(
    sender, trash_item_id, trash_item, parent_id, *args, **kwargs
):
    """
    When a set of rows is permanently deleted, then search data should be cleaned from
    data for those rows.
    """

    row_ids = trash_item.row_ids
    if not row_ids:
        return

    table = trash_item.table
    if SearchHandler.full_text_enabled():
        SearchHandler.mark_search_data_for_deletion(table, row_ids=row_ids)
    else:  # we can drop the entire search table if exists
        workspace_id = table.database.workspace_id
        SearchHandler.delete_workspace_search_table_if_exists(workspace_id)


@receiver(view_loaded)
def view_loaded_schedule_update_search_data(
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

    if not SearchHandler.full_text_enabled():
        return

    tsvector_fields_to_initialize = any(
        f
        for f in table_model.get_searchable_fields(include_trash=True)
        if f.search_data_initialized_at is None
    )
    if tsvector_fields_to_initialize:
        SearchHandler.schedule_update_search_data(table)
