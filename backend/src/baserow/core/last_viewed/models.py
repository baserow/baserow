from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserLastViewedItem(models.Model):
    """
    Records when a user last opened a leaf item (a view, builder page, dashboard or
    automation workflow). Only leaves are stored; the application and workspace
    values are derived with a MAX over these rows, so a deleted leaf automatically
    falls back to the next most recently viewed one.
    """

    # Every upsert consumes a sequence value, also when it changes nothing, so a
    # 32-bit id would run out on a busy instance.
    id = models.BigAutoField(primary_key=True)
    # The unique constraint below already leads with `user`, so a separate index
    # would only add write cost.
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="last_viewed_items", db_index=False
    )
    # Polymorphic reference resolved through `last_viewed_item_type_registry`, so
    # there is deliberately no foreign key to the leaf.
    item_type = models.CharField(max_length=64)
    item_id = models.PositiveIntegerField()
    # Denormalized so the per-application and per-workspace values can be computed
    # without joining every leaf table.
    application = models.ForeignKey(
        "core.Application", on_delete=models.CASCADE, related_name="+"
    )
    workspace = models.ForeignKey(
        "core.Workspace", on_delete=models.CASCADE, related_name="+"
    )
    last_viewed = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item_type", "item_id"],
                name="unique_user_last_viewed_item",
            ),
        ]
        indexes = [
            # Serves the per application MAX for the requesting user.
            models.Index(
                fields=["user", "application"], name="lastviewed_user_app_idx"
            ),
            # Serves the trash receivers and the stale row sweep, which look items
            # up by their polymorphic reference across all users.
            models.Index(fields=["item_type", "item_id"], name="lastviewed_item_idx"),
        ]
