from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


@receiver(automation_workflow_updated)
def on_workflow_updated_test_run_dispatch_immediate_triggers(
    sender, workflow: AutomationWorkflow, **kwargs
):
    def run_workflow():
        if workflow.allow_test_run_until:
            trigger = workflow.get_trigger()
            # A subset of triggers support immediate test run dispatching, if this
            # `node_type` supports it, we'll immediately run the workflow with
            # the pre-defined data.
            if trigger.get_type().immediate_dispatch:
                AutomationWorkflowHandler().run_workflow(workflow, None)

    # We need to wait the commit otherwise the celery task workflow instance doesn't
    # have the allow_test_run_until property saved
    transaction.on_commit(run_workflow)


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
