from typing import Type

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)


class AutomationWorkflowRunner:
    """
    The AutomationWorkflowRunner is responsible for executing automation workflows.
    It handles the execution of the workflow and its associated actions.
    """

    def __init__(self):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )

        self.workflow_handler = AutomationWorkflowHandler()
        self.node_handler = AutomationNodeHandler()

    def run(
        self, workflow: AutomationWorkflow, dispatch_context: AutomationDispatchContext
    ):
        base_queryset = AutomationNode.objects.order_by("order")
        nodes = self.node_handler.get_nodes(workflow, base_queryset=base_queryset)
        action_nodes = [node for node in nodes if node.get_type().is_workflow_action]

        for node in action_nodes:
            node_type: Type[AutomationNodeActionNodeType] = node.get_type()
            try:
                dispatch_result = node_type.dispatch(node, dispatch_context)
                dispatch_context.register_node_result(node, dispatch_result.data)
            except ServiceImproperlyConfiguredDispatchException as e:
                raise AutomationNodeMisconfiguredService(node.id) from e
