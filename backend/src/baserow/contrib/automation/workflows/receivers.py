from django.dispatch import receiver

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.workflows.last_viewed_types import (
    AutomationWorkflowLastViewedItemType,
)
from baserow.contrib.automation.workflows.signals import automation_workflow_loaded
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.signals import workspace_deleted


@receiver(automation_workflow_loaded)
def automation_workflow_loaded_mark_last_viewed(sender, workflow, user, **kwargs):
    LastViewedHandler.schedule_mark_viewed(
        user, AutomationWorkflowLastViewedItemType.type, workflow.id
    )


@receiver(workspace_deleted)
def delete_published_automations_of_deleted_workspace(sender, workspace_id, **kwargs):
    # A published automation has no workspace of its own, so it isn't trashed with
    # the workspace it was published from. It's deleted instead, as it is when its
    # workflow or automation is deleted, so that it stops running.
    Automation.objects.filter(
        published_from__automation__workspace_id=workspace_id
    ).delete()
