from typing import TYPE_CHECKING

from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.integrations.actions import CreateIntegrationActionType
from baserow.core.integrations.service import IntegrationService

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.contrib.automation.models import Automation, AutomationWorkflow
    from baserow.core.integrations.models import Integration


class AutomationApplicationTypeInitApplication:
    """
    Responsible for creating default content in a new automation application.
    """

    def __init__(self, user: "AbstractUser", application: "Automation"):
        self.user = user
        self.application = application

        with translation.override(user.profile.language):
            self.workflow_name = _("Workflow")
            self.integration_name = _("Local Baserow")

    def create_workflow(self, name: str) -> "AutomationWorkflow":
        return AutomationWorkflowService().create_workflow(
            self.user, self.application.id, name
        )

    def create_local_baserow_integration(
        self, audit_logged: bool = False
    ) -> "Integration":
        """
        Creates the Local Baserow integration that row actions read and write
        tables through.

        :param audit_logged: Create it through its action, so the audit log shows
            it. It stays out of undo, so undo can't trash it under the nodes that
            use it.
        :return: The integration.
        """

        if audit_logged:
            with without_undo_redo_registration(self.user):
                return CreateIntegrationActionType.do(
                    self.user,
                    LocalBaserowIntegrationType(),
                    self.application,
                    name=self.integration_name,
                )

        return IntegrationService().create_integration(
            self.user,
            LocalBaserowIntegrationType(),
            self.application,
            name=self.integration_name,
        )
