from datetime import datetime
from typing import Optional

from django.db.models import QuerySet

from baserow.contrib.automation.history.constants import HistoryStatusChoices
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

        return (
            base_queryset.filter(workflow=workflow)
            .prefetch_related("workflow__automation__workspace")
            .order_by("-created_on")
        )

    def create_workflow_history(
        self,
        workflow: AutomationWorkflow,
        created_on: datetime,
        completed_on: datetime,
        status: HistoryStatusChoices,
        is_test_run: bool,
        message: str = "",
    ) -> AutomationWorkflowHistory:
        history = AutomationWorkflowHistory.objects.create(
            workflow=workflow,
            message=message,
            completed_on=completed_on,
            is_test_run=is_test_run,
            status=status,
        )

        # The created_on field must be manually saved to ensure the workflow's
        # start time is accurately recorded.
        #
        # When the task is executed very quickly, Django's auto_now_add/auto_now
        # behaviour can save the created_on field to be slightly after the
        # completed_on field.
        history.created_on = created_on
        history.save()

        return history
