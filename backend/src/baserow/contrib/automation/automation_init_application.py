from typing import TYPE_CHECKING

from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.automation.workflows.service import AutomationWorkflowService

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.contrib.automation.models import Automation, AutomationWorkflow


class AutomationApplicationTypeInitApplication:
    """
    Responsible for creating default content in a new automation application.
    """

    def __init__(self, user: "AbstractUser", application: "Automation"):
        self.user = user
        self.application = application

        with translation.override(user.profile.language):
            self.workflow_name = _("Workflow")

    def create_workflow(self, name: str) -> "AutomationWorkflow":
        return AutomationWorkflowService().create_workflow(
            self.user, self.application.id, name
        )
