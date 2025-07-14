from datetime import datetime

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow


class AutomationHistoryHandler:
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow_handler = AutomationWorkflowHandler()
    node_handler = AutomationNodeHandler()

    def create_workflow_history(
        self,
        workflow: AutomationWorkflow,
        completed_on: datetime,
        status: HistoryStatusChoices,
        message: str = "",
    ) -> AutomationWorkflowHistory:
        original_workflow = self.workflow_handler.get_original_workflow(workflow)
        return AutomationWorkflowHistory.objects.create(
            workflow=original_workflow,
            message=message,
            completed_on=completed_on,
            is_test_run=bool(workflow.allow_test_run_until),
            status=status,
        )

    def create_node_history(
        self,
        node: AutomationNode,
        completed_on: datetime,
        status: HistoryStatusChoices,
        message: str = "",
    ) -> AutomationWorkflowHistory:
        original_node = self.node_handler.get_original_node(node)
        return AutomationNodeHistory.objects.create(
            node=original_node,
            message=message,
            completed_on=completed_on,
            is_test_run=bool(node.workflow.allow_test_run_until),
            status=status,
        )
