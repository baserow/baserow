from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.exceptions import (
    AutomationTriggerNodeDoesNotExist,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow


class AutomationWorkflowRunner:
    """
    The AutomationWorkflowRunner is responsible for executing automation workflows.
    It handles the execution of the workflow and its associated actions.
    """

    def run(
        self, workflow: AutomationWorkflow, dispatch_context: AutomationDispatchContext
    ):
        # Collect all specific action nodes for this workflow, ordered by `order`.
        nodes = AutomationNodeHandler().get_nodes(
            workflow,
            specific=True,
            base_queryset=AutomationNode.objects.order_by("order"),
        )

        # If we don't have any nodes, we can't run the workflow.
        if not nodes:
            raise AutomationTriggerNodeDoesNotExist(
                "This workflow contains no nodes, start by adding a trigger."
            )

        # If the first node is not a trigger, we can't run the workflow.
        if not nodes[0].get_type().is_workflow_trigger:
            raise AutomationTriggerNodeDoesNotExist(
                "This workflow does not have a trigger node, start by adding one."
            )

        action_nodes = [
            node for node in nodes if not node.get_type().is_workflow_trigger
        ]

        for node in action_nodes:
            node_type: Type[AutomationNodeActionNodeType] = node.get_type()  # type: ignore
            node_type.dispatch(node, dispatch_context)
