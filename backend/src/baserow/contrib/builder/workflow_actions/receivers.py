from django.db import transaction
from django.db.models.signals import pre_delete

from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    BuilderWorkflowServiceAction,
)
from baserow.core.services.deferred_deletion import (
    defer_service_deletion,
    is_service_deletion_deferred,
)
from baserow.core.services.models import Service


def before_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the action.
    """

    if not issubclass(instance.specific_class, BuilderWorkflowServiceAction):
        return

    if is_service_deletion_deferred():
        defer_service_deletion(instance.specific.service_id)
        return

    service_id = instance.specific.service_id

    def delete_service_after_commit():
        # The action is also deleted by cascade when its service is deleted, for
        # example by `DomainHandler.delete_published_builder`. The service is
        # already gone then, and this costs a single empty query.
        Service.objects_and_trash.filter(id=service_id).delete()

    transaction.on_commit(delete_service_after_commit)


def connect_to_builder_workflow_action_pre_delete_signal():
    pre_delete.connect(before_permanently_deleted, BuilderWorkflowAction)
