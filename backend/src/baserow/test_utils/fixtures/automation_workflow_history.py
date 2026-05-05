from django.utils import timezone

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)


class AutomationWorkflowHistoryFixtures:
    def create_automation_workflow_history(self, user=None, **kwargs):
        if "original_workflow" not in kwargs:
            kwargs["original_workflow"] = kwargs["workflow"]

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

    def create_automation_node_history(self, user=None, **kwargs):
        user = user or self.create_user()

        if "workflow_history" not in kwargs:
            kwargs["workflow_history"] = self.create_automation_workflow_history(
                user=user, **kwargs
            )

        if "node" not in kwargs:
            kwargs["node"] = self.create_automation_node(
                user=user,
                workflow=kwargs["workflow_history"].workflow,
                **kwargs,
            )

        if "started_on" not in kwargs:
            kwargs["started_on"] = timezone.now()

        if "status" not in kwargs:
            kwargs["status"] = HistoryStatusChoices.STARTED

        return AutomationNodeHistory.objects.create(**kwargs)

    def create_automation_node_result(self, user=None, **kwargs):
        user = user or self.create_user()

        if "node_history" not in kwargs:
            kwargs["node_history"] = self.create_automation_node_history(
                user=user, **kwargs
            )

        return AutomationNodeResult.objects.create(**kwargs)
