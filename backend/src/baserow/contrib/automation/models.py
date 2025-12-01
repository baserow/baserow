from django.db import models

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.models import (
    AutomationWorkflow,
    DuplicateAutomationWorkflowJob,
)
from baserow.core.models import Application

__all__ = [
    "Automation",
    "AutomationWorkflow",
    "DuplicateAutomationWorkflowJob",
    "AutomationWorkflowHistory",
]


class Automation(Application):
    published_from = models.ForeignKey(
        AutomationWorkflow,
        on_delete=models.CASCADE,
        related_name="published_to",
        null=True,
        blank=True,
    )

    def get_parent(self):
        # If we had select related workspace we want to keep it
        self.application_ptr.workspace = self.workspace

        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr
