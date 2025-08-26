from datetime import datetime
from typing import Optional

from django.db.models import QuerySet

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.models import AutomationWorkflow


class AutomationHistoryHandler:
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow_handler = AutomationWorkflowHandler()
    node_handler = AutomationNodeHandler()

    def get_workflow_history(
        self, workflow: AutomationWorkflow, base_queryset: Optional[QuerySet] = None
    ) -> QuerySet[AutomationWorkflowHistory]:
        """
        Returns all the AutomationWorkflowHistory related to the provided workflow.
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflowHistory.objects.all()

        return base_queryset.filter(workflow=workflow).prefetch_related(
            "workflow__automation__workspace"
        )

    def create_workflow_history(
        self,
        workflow: AutomationWorkflow,
        started_on: datetime,
        is_test_run: bool,
    ) -> AutomationWorkflowHistory:
        return AutomationWorkflowHistory.objects.create(
            workflow=workflow,
            started_on=started_on,
            is_test_run=is_test_run,
        )
