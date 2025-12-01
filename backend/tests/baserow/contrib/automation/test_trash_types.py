import pytest

from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_trashing_automation_deletes_published_automations(data_fixture):
    """
    When an Automation application is trashed, ensure that all published
    automations are deleted.
    """

    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    original_workflow = data_fixture.create_automation_workflow(
        user, automation=automation
    )
    published_workflow = data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    TrashHandler.trash(user, automation.workspace, automation, automation)

    automation.refresh_from_db()

    assert automation.trashed is True
    assert (
        AutomationWorkflow.objects_and_trash.filter(id=original_workflow.id).exists()
        is True
    )
    assert (
        AutomationWorkflow.objects_and_trash.filter(id=published_workflow.id).exists()
        is False
    )
