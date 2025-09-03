from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import CorePeriodicTriggerNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.utils import get_periodic_trigger_payload
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


@receiver(automation_workflow_updated)
def on_workflow_updated_test_run_execute_periodic_workflows(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    if workflow.allow_test_run_until:
        trigger = workflow.get_trigger(specific=False)
        node_type = automation_node_type_registry.get_by_model(trigger.specific_class)
        if node_type.type == CorePeriodicTriggerNodeType.type:
            # If the `allow_test_run_until` is enabled on the workflow, then a test
            # run must immediately take place for the periodic trigger node. This is
            # because the interval could be set to take place in a week from now. To
            # test it properly, it must be triggered immediately.
            node_type.on_event(
                CorePeriodicService.objects.filter(id=trigger.service_id),
                get_periodic_trigger_payload(timezone.now()),
            )


def after_permanently_deleted(sender, instance, **kwargs):
    """
    Delete the service related to the node.
    """

    try:
        if instance.service_id:
            service = instance.service
            ServiceHandler().delete_service(service.get_type(), service)
    except Service.DoesNotExist:
        # Although cascade deletion should safely handle related models, it may
        # occasionally raise a DoesNotExist error.
        #
        # If the service does not exist, there is nothing to delete.
        pass


def connect_to_node_pre_delete_signal():
    post_delete.connect(after_permanently_deleted, AutomationNode)
