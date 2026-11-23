from django.dispatch import receiver

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.constants import WORKFLOW_DIRTY_CACHE_KEY
from baserow.contrib.automation.workflows.last_viewed_types import (
    AutomationWorkflowLastViewedItemType,
)
from baserow.contrib.automation.workflows.signals import automation_workflow_loaded
from baserow.core.cache import global_cache
from baserow.core.integrations.signals import (
    integration_created,
    integration_deleted,
    integration_updated,
)
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


def _mark_workflows_using_integration_changed(integration_id: int):
    """
    Marks every workflow with a node that uses the integration as changed, so that
    its next test run makes a new copy instead of reusing one that still has the
    integration as it was. The copies aren't marked: their nodes use the copies of
    the integrations made with them, and keep them, as a published workflow does.

    :param integration_id: The integration that was changed, deleted or restored.
    """

    workflow_ids = (
        AutomationNode.objects.filter(service__integration_id=integration_id)
        .values_list("workflow_id", flat=True)
        .distinct()
    )
    for workflow_id in workflow_ids:
        global_cache.update(
            WORKFLOW_DIRTY_CACHE_KEY.format(workflow_id), lambda _: True
        )


@receiver(integration_updated)
def integration_updated_mark_workflows_changed(sender, integration, **kwargs):
    _mark_workflows_using_integration_changed(integration.id)


@receiver(integration_deleted)
def integration_deleted_mark_workflows_changed(sender, integration_id, **kwargs):
    _mark_workflows_using_integration_changed(integration_id)


# Also sent when an integration is restored from the trash.
@receiver(integration_created)
def integration_created_mark_workflows_changed(sender, integration, **kwargs):
    _mark_workflows_using_integration_changed(integration.id)
