from collections import defaultdict

from django.dispatch import receiver

from baserow.contrib.database.fields.formula_visitors import (
    TABLE_FIELD_IDS_CACHE_KEY,
)
from baserow.contrib.database.fields.periodic_field_update_handler import (
    PeriodicFieldUpdateHandler,
)
from baserow.contrib.database.fields.signals import field_updated
from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.table.signals import table_schema_changed
from baserow.contrib.database.views import signals as view_signals
from baserow.core.cache import local_cache

from .models import LinkRowField


@receiver([view_signals.view_loaded, row_signals.rows_loaded])
def mark_workspace_used_on_rows_loaded(sender, table, **kwargs):
    PeriodicFieldUpdateHandler.mark_workspace_as_recently_used(
        table.database.workspace_id
    )


@receiver(view_signals.view_deleted)
def clear_link_row_limit_selection_view_when_view_is_deleted(
    sender, view_id, view, user, **kwargs
):
    """
    A view can have dependencies in the form of the `link_row_limit_selection_view`
    foreign key. When the view is trashed, the foreignkey keeps existing,
    but the functionality doesn't work anymore because the view is trashed. This
    function listens the view delete signal, checks if there are dependencies,
    and if so, it will clear them. Doing it manually is much more performant than
    calling the `update_field` method.
    """

    link_rows = LinkRowField.objects_and_trash.filter(
        link_row_limit_selection_view=view,
    ).select_for_update()

    if len(link_rows) == 0:
        return

    for link_row in link_rows:
        link_row.link_row_limit_selection_view = None

    LinkRowField.objects_and_trash.bulk_update(
        link_rows, ["link_row_limit_selection_view"]
    )

    # Group by table so that one we can send one `field_update` signal for each
    # table. If there are multiple link row fields, we combine them in one request by
    # adding them into the `related_fields` parameter. This ensures that one
    # real-time event is sent per table if needed.
    grouped_by_table = defaultdict(list)
    for link_row in link_rows:
        if not link_row.trashed:
            grouped_by_table[link_row.table_id].append(link_row)
    for table_id, link_rows in grouped_by_table.items():
        field_updated.send(
            sender,
            field=link_rows[0],
            related_fields=link_rows[1:],
            user=None,
        )


@receiver(table_schema_changed)
def invalidate_formula_field_table_field_ids_cache(sender, table_id, **kwargs):
    # Invalidate the cached field ids used to validate formula field references
    # (see formula_visitors.get_table_field_ids) when a field is added, updated,
    # trashed or restored.
    local_cache.delete(f"{TABLE_FIELD_IDS_CACHE_KEY}_{table_id}")
