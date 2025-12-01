from unittest.mock import patch

import pytest

from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.models import Job
from baserow.core.utils import Progress

SERVICES_PATH = "baserow.contrib.automation.workflows.service"


@pytest.mark.django_db
def test_get_workflow_returns_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    returned_workflow = AutomationWorkflowService().get_workflow(user, workflow.id)

    assert returned_workflow == workflow


@pytest.mark.django_db
def test_get_workflow_raises_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowService().get_workflow(user, 999)


@pytest.mark.django_db
def test_get_workflow_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application()
    workflow = data_fixture.create_automation_workflow(automation=automation)

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().get_workflow(user, workflow.id)


@patch(f"{SERVICES_PATH}.automation_workflow_created")
@pytest.mark.django_db
def test_workflow_created_signal_sent(workflow_created_mock, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    service = AutomationWorkflowService()

    workflow = service.create_workflow(user, automation.id, "test")

    workflow_created_mock.send.assert_called_once_with(
        service, workflow=workflow, user=user
    )


@pytest.mark.django_db
def test_create_workflow_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application()

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().create_workflow(user, automation.id, "test")


@pytest.mark.django_db
def test_create_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)

    workflow = AutomationWorkflowService().create_workflow(user, automation.id, "foo")

    assert workflow.automation_workflow_nodes.count() == 0


@patch(f"{SERVICES_PATH}.automation_workflow_deleted")
@pytest.mark.django_db
def test_workflow_deleted_signal_sent(workflow_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    service = AutomationWorkflowService()
    service.delete_workflow(user, workflow.id)

    workflow_deleted_mock.send.assert_called_once_with(
        service,
        automation=automation,
        workflow_id=workflow.id,
        user=user,
    )


@pytest.mark.django_db(transaction=True)
def test_delete_workflow_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    another_user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)

    workflow = AutomationWorkflowService().create_workflow(user, automation.id, "test")

    previous_count = AutomationWorkflow.objects.count()

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().delete_workflow(another_user, workflow.id)

    assert AutomationWorkflow.objects.count() == previous_count


@patch(f"{SERVICES_PATH}.automation_workflow_updated")
@pytest.mark.django_db
def test_workflow_updated_signal_sent(workflow_updated_mock, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    service = AutomationWorkflowService()
    service.update_workflow(user, workflow.id, name="new")

    workflow_updated_mock.send.assert_called_once_with(
        service, workflow=workflow, user=user
    )


@pytest.mark.django_db
def test_update_workflow_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application()
    workflow = data_fixture.create_automation_workflow(automation=automation)

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().update_workflow(user, workflow.id, name="test")


@pytest.mark.django_db
def test_update_workflow_ignores_invalid_values(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    updated_workflow = AutomationWorkflowService().update_workflow(
        user, workflow.id, foo="bar"
    )

    assert hasattr(updated_workflow, "foo") is False


@patch(f"{SERVICES_PATH}.automation_workflows_reordered")
@pytest.mark.django_db
def test_workflows_reordered_signal_sent(workflows_reordered_mock, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(automation=automation, order=1)
    workflow_2 = data_fixture.create_automation_workflow(automation=automation, order=2)

    service = AutomationWorkflowService()
    workflow_orders = service.order_workflows(
        user, automation, [workflow_2.id, workflow_1.id]
    )

    workflows_reordered_mock.send.assert_called_once_with(
        service, automation=automation, order=workflow_orders, user=user
    )


@pytest.mark.django_db
def test_order_workflows_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(automation=automation, order=1)
    workflow_2 = data_fixture.create_automation_workflow(automation=automation, order=2)

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().order_workflows(
            user, automation, [workflow_2.id, workflow_1.id]
        )


@pytest.mark.django_db
def test_order_workflows_not_in_automation(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(automation=automation, order=1)
    workflow_2 = data_fixture.create_automation_workflow(order=2)

    with pytest.raises(AutomationWorkflowNotInAutomation):
        AutomationWorkflowService().order_workflows(
            user, automation, [workflow_2.id, workflow_1.id]
        )


@pytest.mark.django_db
def test_duplicate_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    workflow_clone = AutomationWorkflowService().duplicate_workflow(user, workflow)

    assert workflow_clone.order != workflow.order
    assert workflow_clone.id != workflow.id
    assert workflow_clone.name != workflow.name


@pytest.mark.django_db
def test_duplicate_workflow_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().duplicate_workflow(user, workflow)


@pytest.mark.django_db
def test_async_publish_raises_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().async_publish(user, workflow.id)


@pytest.mark.django_db
def test_async_publish_starts_job(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    assert Job.objects.count() == 0

    job = AutomationWorkflowService().async_publish(user, workflow.id)

    assert Job.objects.count() == 1
    assert job == Job.objects.first().specific


@pytest.mark.django_db
def test_publish_raises_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()

    with pytest.raises(UserNotInWorkspace):
        AutomationWorkflowService().publish(user, workflow, Progress(0))


@pytest.mark.django_db
@patch(f"{SERVICES_PATH}.automation_workflow_published")
def test_publish_workflow(mock_signal, data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=automation)

    service = AutomationWorkflowService()
    service.publish(user, workflow, Progress(0))

    workflow.refresh_from_db()
    assert workflow.state == WorkflowState.DRAFT

    published_automation = Automation.objects.get(published_from=workflow)
    assert published_automation.automation.workspace is None
    assert published_automation.workflows.count() == 1

    published_workflow = published_automation.workflows.first()
    assert published_workflow.state == WorkflowState.LIVE

    mock_signal.send.assert_called_once_with(
        service, user=user, workflow=published_workflow
    )
