from django.utils import timezone

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler


class AutomationHistoryFixtures:
    def create_workflow_history(self, user=None, **kwargs):
        published_workflow = kwargs.pop("published_workflow", None)
        if published_workflow is None:
            if user is None:
                user = self.create_user()
            published_workflow = self.create_automation_workflow(
                user=user, published=True
            )

        original_workflow = kwargs.pop("original_workflow", None)
        if original_workflow is None:
            original_workflow = self.create_automation_workflow(user=user)

        published_workflow.automation.published_from = original_workflow
        published_workflow.automation.save()

        completed_on = kwargs.pop("completed_on", None)
        if completed_on is None:
            completed_on = timezone.now()

        status = kwargs.pop("status", None)
        if status is None:
            status = HistoryStatusChoices.SUCCESS

        self.create_local_baserow_rows_created_trigger_node(
            user=user, workflow=original_workflow
        )
        self.create_local_baserow_create_row_action_node(
            user=user, workflow=original_workflow
        )

        return AutomationHistoryHandler().create_workflow_history(
            workflow=published_workflow,
            completed_on=completed_on,
            status=status,
        )
