from typing import Type

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.exceptions import ServiceImproperlyConfigured


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
        for node in self.workflow_handler.get_action_nodes(workflow):
            node_type: Type[AutomationNodeActionNodeType] = node.get_type()
            try:
                dispatch_context = node_type.dispatch(node, dispatch_context)
            except ServiceImproperlyConfigured as e:
                raise AutomationNodeMisconfiguredService(node.id) from e
