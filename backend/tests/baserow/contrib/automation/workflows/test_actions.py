from unittest.mock import MagicMock

import pytest

from baserow.contrib.automation.workflows.actions import (
    CreateAutomationWorkflowActionType,
    DeleteAutomationWorkflowActionType,
    DuplicateAutomationWorkflowActionType,
    OrderAutomationWorkflowActionType,
    UpdateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_do(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    assert automation.workflows.count() == 0

    workflow = CreateAutomationWorkflowActionType.do(
        user, automation.id, {"name": "test"}
    )
    assert automation.workflows.first() == workflow


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_undo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)

    # Create a workflow
    workflow = CreateAutomationWorkflowActionType.do(
        user, automation.id, {"name": "test"}
    )
    assert automation.workflows.count() == 1

    params = CreateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
    )

    # Now undo the creation
    CreateAutomationWorkflowActionType.undo(user, params, MagicMock())

    assert automation.workflows.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_redo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)

    # Create a workflow
    workflow = CreateAutomationWorkflowActionType.do(
        user, automation.id, {"name": "test"}
    )
    assert automation.workflows.count() == 1

    # Undo the creation, i.e. delete it
    params = CreateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
    )
    CreateAutomationWorkflowActionType.undo(user, params, MagicMock())
    assert automation.workflows.count() == 0

    # Now redo the deletion, i.e. the workflow should be restored
    CreateAutomationWorkflowActionType.redo(user, params, MagicMock())
    assert automation.workflows.count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_do(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    workflow = UpdateAutomationWorkflowActionType.do(
        user, workflow.id, {"name": "test1"}
    )

    workflow.refresh_from_db()
    assert workflow.name == "test1"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_undo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    workflow = UpdateAutomationWorkflowActionType.do(
        user, workflow.id, {"name": "test1"}
    )

    workflow.refresh_from_db()
    assert workflow.name == "test1"

    params = UpdateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        workflow_original_params={"name": "test1"},
        workflow_new_params={"name": "test2"},
    )
    UpdateAutomationWorkflowActionType.undo(user, params, MagicMock())

    workflow.refresh_from_db()
    assert workflow.name == "test1"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_redo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    workflow = UpdateAutomationWorkflowActionType.do(
        user, workflow.id, {"name": "test1"}
    )

    params = UpdateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        workflow_original_params={"name": "test1"},
        workflow_new_params={"name": "test2"},
    )
    UpdateAutomationWorkflowActionType.undo(user, params, MagicMock())

    workflow.refresh_from_db()
    assert workflow.name == "test1"

    UpdateAutomationWorkflowActionType.redo(user, params, MagicMock())

    # Ensure that the undone action is reversed
    workflow.refresh_from_db()
    assert workflow.name == "test2"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_do(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )
    assert automation.workflows.count() == 1

    workflow = DeleteAutomationWorkflowActionType.do(user, workflow.id)

    assert automation.workflows.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_undo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_name = "test"
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name=workflow_name
    )
    workflow_id = workflow.id

    assert automation.workflows.count() == 1
    workflow = DeleteAutomationWorkflowActionType.do(user, workflow_id)
    assert automation.workflows.count() == 0

    # Undo the deletion
    params = DeleteAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
    )
    workflow = DeleteAutomationWorkflowActionType.undo(user, params, MagicMock())

    # Ensure the workflow exists
    assert automation.workflows.count() == 1


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_redo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_name = "test"
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name=workflow_name
    )
    workflow_id = workflow.id

    workflow = DeleteAutomationWorkflowActionType.do(user, workflow_id)

    # Undo the deletion
    params = DeleteAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
    )
    DeleteAutomationWorkflowActionType.undo(user, params, MagicMock())

    # Ensure the workflow exists
    assert automation.workflows.count() == 1

    # Reverse the undo; the workflow should no longer exist
    DeleteAutomationWorkflowActionType.redo(user, params, MagicMock())
    assert automation.workflows.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_do(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(name="test", user=user)
    automation = workflow.automation

    assert automation.workflows.count() == 1

    duplicated_workflow = DuplicateAutomationWorkflowActionType.do(user, workflow)

    assert automation.workflows.count() == 2
    assert automation.workflows.first() == workflow
    assert automation.workflows.last() == duplicated_workflow


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_undo(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(name="test", user=user)
    automation = workflow.automation

    # Duplicate the workflow
    duplicated_workflow = DuplicateAutomationWorkflowActionType.do(user, workflow)
    assert automation.workflows.count() == 2

    params = DuplicateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=duplicated_workflow.id,
        workflow_name=duplicated_workflow.name,
        original_workflow_id=workflow.id,
        original_workflow_name=workflow.name,
    )

    # Now undo the duplication
    DuplicateAutomationWorkflowActionType.undo(user, params, MagicMock())

    assert automation.workflows.count() == 1
    assert automation.workflows.first() == workflow


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_redo(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(name="test", user=user)
    automation = workflow.automation

    # Duplicate the workflow
    duplicated_workflow = DuplicateAutomationWorkflowActionType.do(user, workflow)
    assert automation.workflows.count() == 2

    # Now undo the duplication
    params = DuplicateAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflow_id=duplicated_workflow.id,
        workflow_name=duplicated_workflow.name,
        original_workflow_id=workflow.id,
        original_workflow_name=workflow.name,
    )
    DuplicateAutomationWorkflowActionType.undo(user, params, MagicMock())
    assert automation.workflows.count() == 1

    # Now redo the last action, i.e. the duplicated workflow should be restored
    DuplicateAutomationWorkflowActionType.redo(user, params, MagicMock())
    assert automation.workflows.count() == 2
    assert automation.workflows.first() == workflow
    assert automation.workflows.last() == duplicated_workflow


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_order_do(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1"
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2"
    )

    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_1.id, workflow_2.id]

    # Reverse the order
    OrderAutomationWorkflowActionType.do(
        user, automation.id, [workflow_2.id, workflow_1.id]
    )
    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_2.id, workflow_1.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_order_undo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1"
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2"
    )

    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_1.id, workflow_2.id]

    # Reverse the order
    OrderAutomationWorkflowActionType.do(
        user, automation.id, [workflow_2.id, workflow_1.id]
    )

    # Now undo the ordering
    params = OrderAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflows_order=[workflow_2.id, workflow_1.id],
        original_workflows_order=[workflow_1.id, workflow_2.id],
    )
    OrderAutomationWorkflowActionType.undo(user, params, MagicMock())

    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_1.id, workflow_2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_order_redo(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow_1 = data_fixture.create_automation_workflow(
        automation=automation, name="test1"
    )
    workflow_2 = data_fixture.create_automation_workflow(
        automation=automation, name="test2"
    )

    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_1.id, workflow_2.id]

    # Reverse the order
    OrderAutomationWorkflowActionType.do(
        user, automation.id, [workflow_2.id, workflow_1.id]
    )

    # Now undo the ordering
    params = OrderAutomationWorkflowActionType.Params(
        automation_id=automation.id,
        automation_name=automation.name,
        workflows_order=[workflow_2.id, workflow_1.id],
        original_workflows_order=[workflow_1.id, workflow_2.id],
    )
    OrderAutomationWorkflowActionType.undo(user, params, MagicMock())

    # Finally reverse the undo; the state should be the initial reversal action
    OrderAutomationWorkflowActionType.redo(user, params, MagicMock())
    workflows_order = AutomationWorkflowHandler().get_workflows_order(automation)
    assert workflows_order == [workflow_2.id, workflow_1.id]
