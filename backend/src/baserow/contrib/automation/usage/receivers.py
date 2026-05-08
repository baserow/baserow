from datetime import date

from django.db.models import F
from django.dispatch import receiver

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.signals import automation_node_dispatch_completed
from baserow.contrib.automation.usage.models import WorkspaceAutomationUsage


@receiver(automation_node_dispatch_completed)
def update_automation_usage(sender, node: AutomationNode, **kwargs) -> None:
    """
    Updates the automation usage for the node's workspace.
    """

    cost = node.get_type().get_dispatch_cost()
    if cost == 0:
        return

    workspace = node.workflow.automation.workspace

    usage, _ = WorkspaceAutomationUsage.objects.get_or_create(
        workspace=workspace,
        period=date.today(),
    )
    WorkspaceAutomationUsage.objects.filter(pk=usage.pk).update(
        dispatch_count=F("dispatch_count") + cost
    )
