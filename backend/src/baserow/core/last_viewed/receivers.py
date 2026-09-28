from django.dispatch import receiver

from baserow.core.registries import last_viewed_item_type_registry
from baserow.core.signals import workspace_user_deleted
from baserow.core.trash.signals import before_permanently_deleted

from .handler import LastViewedHandler


# `before_permanently_deleted` is used instead of `permanently_deleted` because the
# item still has its id and relations at that point. Which trash items take which
# rows with them is knowledge of the registered types, not of core.
@receiver(before_permanently_deleted)
def delete_last_viewed_of_permanently_deleted_item(sender, trash_item, **kwargs):
    for item_type in last_viewed_item_type_registry.get_all():
        item_ids = list(
            item_type.get_item_ids_of_permanently_deleted(sender, trash_item)
        )
        if item_ids:
            LastViewedHandler.delete_items(item_type.type, item_ids)


@receiver(workspace_user_deleted)
def delete_last_viewed_of_removed_workspace_user(sender, workspace_user, **kwargs):
    LastViewedHandler.delete_for_user_in_workspace(
        workspace_user.user_id, workspace_user.workspace_id
    )
