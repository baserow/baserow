from baserow.contrib.automation.workflows.models import AutomationWorkflow, DuplicateWorkflowAutomationJob
from baserow.core.models import Application

__all__ = [
    "Automation",
    "AutomationWorkflow",
    "DuplicateWorkflowAutomationJob",
]


class Automation(Application):
    def get_parent(self):
        # If we had select related workspace we want to keep it
        self.application_ptr.workspace = self.workspace

        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr
