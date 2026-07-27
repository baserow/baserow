from django.db import transaction
from django.db.models.signals import pre_delete

from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


def before_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the action.
    """

    if isinstance(instance.specific, DatabaseWorkflowServiceAction):
        service = instance.specific.service

        def delete_service_after_commit():
            try:
                ServiceHandler().delete_service(service.get_type(), service)
            except Service.DoesNotExist:
                # Cascade deletion usually handles this, but it can occasionally
                # raise DoesNotExist. Nothing to delete in that case.
                pass

        transaction.on_commit(delete_service_after_commit)


def connect_to_database_workflow_action_pre_delete_signal():
    pre_delete.connect(before_permanently_deleted, DatabaseWorkflowAction)
