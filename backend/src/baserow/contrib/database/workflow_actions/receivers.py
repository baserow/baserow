from django.db import transaction
from django.db.models.signals import pre_delete

from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
)
from baserow.core.models import TrashEntry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


def before_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the action, and its trash entry. A deleted
    action cannot be restored, and a field changing away from a button deletes
    its trashed actions too, which would otherwise stay listed in the trash.
    """

    from baserow.contrib.database.workflow_actions.trash_types import (
        DatabaseWorkflowActionTrashableItemType,
    )

    if instance.trashed:
        TrashEntry.objects.filter(
            trash_item_type=DatabaseWorkflowActionTrashableItemType.type,
            trash_item_id=instance.id,
        ).delete()

    if isinstance(instance.specific, DatabaseWorkflowServiceAction):
        service = instance.specific.service

        def delete_service_after_commit():
            try:
                ServiceHandler().delete_service(service.get_type(), service)
            except Service.DoesNotExist:
                # Cascade deletion may already have removed it.
                pass

        transaction.on_commit(delete_service_after_commit)


def connect_to_database_workflow_action_pre_delete_signal():
    pre_delete.connect(before_permanently_deleted, DatabaseWorkflowAction)
