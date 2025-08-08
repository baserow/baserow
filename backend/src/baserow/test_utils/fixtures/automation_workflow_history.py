from django.utils import timezone

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import AutomationWorkflowHistory


class AutomationWorkflowHistoryFixtures:
    def create_automation_workflow_history(self, user=None, **kwargs):
        if "workflow" not in kwargs:
            user = user or self.create_user()
            kwargs["workflow"] = self.create_automation_workflow(user=user)

        if "started_on" not in kwargs:
            kwargs["started_on"] = timezone.now()

        if "status" not in kwargs:
            kwargs["status"] = HistoryStatusChoices.STARTED

        if "is_test_run" not in kwargs:
            kwargs["is_test_run"] = False

        return AutomationWorkflowHistory.objects.create(**kwargs)
