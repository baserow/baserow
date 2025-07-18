from django.db import transaction
from django.db.models.signals import pre_delete

from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    BuilderWorkflowServiceAction,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


def before_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the action.
    """

    if isinstance(instance.specific, BuilderWorkflowServiceAction):
        service = instance.specific.service

        def delete_service_after_commit():
            try:
                ServiceHandler().delete_service(service.get_type(), service)
            except Service.DoesNotExist:
                # Although cascade deletion should safely handle related models, it may
                # occasionally raise a DoesNotExist error.
                #
                # If the service does not exist, there is nothing to delete.
                pass

        transaction.on_commit(delete_service_after_commit)


def connect_to_builder_workflow_action_pre_delete_signal():
    pre_delete.connect(before_permanently_deleted, BuilderWorkflowAction)
