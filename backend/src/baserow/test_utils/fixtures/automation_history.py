from django.utils import timezone

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.workflows.constants import WorkflowState


class AutomationHistoryFixtures:
    def create_workflow_history(self, user=None, **kwargs):
        if user is None:
            user = self.create_user()

        published_workflow = kwargs.pop("published_workflow", None)
        if published_workflow is None:
            published_workflow = self.create_automation_workflow(
                user=user, state=WorkflowState.LIVE
            )

        original_workflow = kwargs.pop("original_workflow", None)
        if original_workflow is None:
            original_workflow = self.create_automation_workflow(user=user)

        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

        started_on = kwargs.pop("started_on", None)
        if started_on is None:
            started_on = timezone.now()

        completed_on = kwargs.pop("completed_on", None)
        if completed_on is None:
            completed_on = timezone.now()

        status = kwargs.pop("status", None)
        if status is None:
            status = HistoryStatusChoices.SUCCESS

        is_test_run = kwargs.pop("status", False)

        self.create_local_baserow_create_row_action_node(
            user=user, workflow=original_workflow
        )

        history = AutomationHistoryHandler().create_workflow_history(
            workflow=original_workflow,
            started_on=started_on,
            is_test_run=is_test_run,
        )

        history.completed_on = completed_on
        history.status = status
        history.save()

        return history
