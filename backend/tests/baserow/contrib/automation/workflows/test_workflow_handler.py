import pytest

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


@pytest.mark.django_db
def test_get_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    assert AutomationWorkflowHandler().get_workflow(workflow.id).id == workflow.id


@pytest.mark.django_db
def test_get_workflow_does_not_exist():
    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowHandler().get_workflow(123)


@pytest.mark.django_db
def test_get_workflow_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    # With selecting related
    base_queryset = AutomationWorkflow.objects.exclude(id=workflow.id)

    with pytest.raises(AutomationWorkflowDoesNotExist):
        AutomationWorkflowHandler().get_workflow(
            workflow.id, base_queryset=base_queryset
        )


@pytest.mark.django_db
def test_create_workflow(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    expected_order = AutomationWorkflow.get_last_order(automation)

    workflow = AutomationWorkflowHandler().create_workflow(automation, "test")

    assert workflow.order == expected_order
    assert workflow.name == "test"


@pytest.mark.django_db
def test_create_workflow_name_not_unique(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    with pytest.raises(AutomationWorkflowNameNotUnique):
        AutomationWorkflowHandler().create_workflow(workflow.automation, name="test")


@pytest.mark.django_db
def test_delete_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    previous_count = AutomationWorkflow.objects.count()

    AutomationWorkflowHandler().delete_workflow(workflow)

    assert AutomationWorkflow.objects.count() == previous_count - 1


@pytest.mark.django_db
def test_update_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    AutomationWorkflowHandler().update_workflow(workflow, name="new")

    workflow.refresh_from_db()

    assert workflow.name == "new"


@pytest.mark.django_db
def test_update_workflow_name_not_unique(data_fixture):
    workflow_1 = data_fixture.create_automation_workflow(name="test1")
    workflow_2 = data_fixture.create_automation_workflow(
        automation=workflow_1.automation, name="test2"
    )

    with pytest.raises(AutomationWorkflowNameNotUnique):
        AutomationWorkflowHandler().update_workflow(workflow_2, name=workflow_1.name)


@pytest.mark.django_db
def test_order_workflows(data_fixture):
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=10
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=20
    )

    assert AutomationWorkflowHandler().order_workflows(
        automation, [workflow_2.id, workflow_1.id]
    ) == [
        workflow_2.id,
        workflow_1.id,
    ]

    workflow_1.refresh_from_db()
    workflow_2.refresh_from_db()

    assert workflow_1.order > workflow_2.order


@pytest.mark.django_db
def test_order_workflows_not_in_automation(data_fixture):
    automation = data_fixture.create_automation_application()
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1", order=10
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2", order=20
    )

    base_qs = AutomationWorkflow.objects.filter(id=workflow_2.id)

    with pytest.raises(AutomationWorkflowNotInAutomation):
        AutomationWorkflowHandler().order_workflows(
            automation, [workflow_2.id, workflow_1.id], base_qs=base_qs
        )


@pytest.mark.django_db
def test_duplicate_workflow(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    previous_count = AutomationWorkflow.objects.count()

    workflow_clone = AutomationWorkflowHandler().duplicate_workflow(workflow)

    assert AutomationWorkflow.objects.count() == previous_count + 1
    assert workflow_clone.id != workflow.id
    assert workflow_clone.name != workflow.name
    assert workflow_clone.order != workflow.order
