from django.dispatch import receiver

from baserow.core.trash.signals import permanently_deleted
from baserow_premium.row_comments.models import RowComment


@receiver(permanently_deleted, sender="row", dispatch_uid="row_comment_cleanup")
def permanently_deleted(sender, **kwargs):
    table_id = kwargs["parent_id"]
    trash_item_id = kwargs["trash_item_id"]
    RowComment.objects.filter(table_id=table_id, row_id=trash_item_id).delete()
