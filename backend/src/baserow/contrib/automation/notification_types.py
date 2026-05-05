from dataclasses import asdict, dataclass
from typing import List

from django.utils.translation import gettext as _

from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import NotificationType


@dataclass
class WorkflowDisabledNotificationData:
    workspace_id: int
    automation_id: int
    workflow_id: int
    workflow_name: str

    @classmethod
    def from_workflow(cls, workflow: AutomationWorkflow):
        original_workflow = workflow.get_original()
        return cls(
            workspace_id=original_workflow.automation.workspace_id,
            automation_id=original_workflow.automation_id,
            workflow_id=original_workflow.id,
            workflow_name=original_workflow.name,
        )


class WorkflowDisabledNotificationType(NotificationType):
    type = "automation_workflow_disabled"

    @classmethod
    def notify_recipients(
        cls, workflow: AutomationWorkflow
    ) -> List[NotificationRecipient]:
        original_workflow = workflow.get_original()
        recipients = list(
            original_workflow.notification_recipients.filter(
                profile__to_be_deleted=False,
                is_active=True,
            ).select_related("profile")
        )
        if not recipients:
            return []

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=recipients,
            data=asdict(WorkflowDisabledNotificationData.from_workflow(workflow)),
            sender=None,
            workspace=original_workflow.automation.workspace,
        )

    @classmethod
    def get_notification_title(cls, notification):
        return _("%(name)s workflow was disabled.") % {
            "name": notification.data["workflow_name"]
        }
