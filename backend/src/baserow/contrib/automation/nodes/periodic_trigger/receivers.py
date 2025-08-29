from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from django.utils import timezone

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import PeriodicTriggerNodeType
from baserow.contrib.automation.nodes.periodic_trigger.models import (
    PeriodicTriggerService,
)
from baserow.contrib.automation.nodes.periodic_trigger.utils import (
    get_periodic_trigger_payload,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated


@receiver(automation_workflow_updated)
def workflow_updated(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    if workflow.allow_test_run_until:
        trigger = workflow.get_trigger(specific=False)
        node_type = automation_node_type_registry.get_by_model(trigger.specific_class)
        if node_type.type == PeriodicTriggerNodeType.type:
            # If the `allow_test_run_until` is enabled on the workflow, then a test
            # run must immediately take place for the periodic trigger node. This is
            # because the interval could be set to take place in a week from now. To
            # test it properly, it must be triggered immediately.
            node_type.on_event(
                PeriodicTriggerService.objects.filter(id=trigger.service_id),
                get_periodic_trigger_payload(timezone.now()),
            )
