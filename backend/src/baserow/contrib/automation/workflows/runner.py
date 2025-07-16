from typing import TYPE_CHECKING, Type

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

if TYPE_CHECKING:
    from baserow.contrib.automation.nodes.models import AutomationNode


class AutomationWorkflowRunner:
    """
    The AutomationWorkflowRunner is responsible for executing automation workflows.
    It handles the execution of the workflow and its associated actions.
    """

    def run(
        self,
        workflow: AutomationWorkflow,
        dispatch_context: AutomationDispatchContext,
    ):
        """
        Runs the automation workflow by iterating through its nodes and dispatching
        each node's action. It uses the provided dispatch context to manage the
        execution flow and data between nodes.

        :param workflow: The automation workflow to run.
        :param dispatch_context: The context in which the workflow is being dispatched,
            which contains the event payload and other relevant data.
        """

        def _dispatch_node(node: "AutomationNode"):
            node_type: Type[AutomationNodeActionNodeType] = node.get_type()
            try:
                dispatch_result = node_type.dispatch(node, dispatch_context)
                dispatch_context.after_dispatch(node, dispatch_result)
                next_nodes = node.get_next_nodes(dispatch_result.output_uid)
                for next_node in next_nodes:
                    _dispatch_node(next_node)
            except ServiceImproperlyConfiguredDispatchException as e:
                raise AutomationNodeMisconfiguredService(node.id) from e

        for node in workflow.get_trigger().get_next_nodes():
            _dispatch_node(node)
