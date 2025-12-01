import pytest

from baserow.contrib.automation.workflows.trash_types import (
    AutomationWorkflowTrashableItemType,
)
from baserow.core.models import TrashEntry


@pytest.mark.django_db
def test_workflow_trashable_get_parent(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowTrashableItemType().get_parent(workflow)

    assert result == workflow.automation


@pytest.mark.django_db
def test_workflow_trashable_get_name(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowTrashableItemType().get_name(workflow)

    assert result == workflow.name


def get_trash_entry(user, workflow):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=workflow.automation.workspace,
        application=workflow.automation,
        trash_item_type=AutomationWorkflowTrashableItemType,
        trash_item_id=workflow.id,
        name=AutomationWorkflowTrashableItemType().get_name(workflow),
        names=AutomationWorkflowTrashableItemType().get_names(workflow),
    )


@pytest.mark.django_db
def test_workflow_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        name="test", automation=automation
    )

    trash_entry = get_trash_entry(user, workflow)
    result = AutomationWorkflowTrashableItemType().trash(workflow, user, trash_entry)

    assert result is None
    assert automation.workflows.count() == 0


@pytest.mark.django_db
def test_workflow_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        name="test", automation=automation
    )

    trash_entry = get_trash_entry(user, workflow)
    result = AutomationWorkflowTrashableItemType().trash(workflow, user, trash_entry)
    assert automation.workflows.count() == 0

    result = AutomationWorkflowTrashableItemType().restore(workflow, trash_entry)

    assert result is None
    assert automation.workflows.count() == 1


@pytest.mark.django_db
def test_workflow_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        name="test", automation=automation
    )

    trash_entry = get_trash_entry(user, workflow)
    result = AutomationWorkflowTrashableItemType().trash(workflow, user, trash_entry)
    assert automation.workflows.count() == 0

    result = AutomationWorkflowTrashableItemType().permanently_delete_item(
        workflow, trash_entry
    )

    assert result is None
    assert automation.workflows.count() == 0


def test_workflow_trashable_get_restore_operation_type():
    result = AutomationWorkflowTrashableItemType().get_restore_operation_type()

    assert result == "automation.workflow.restore"
