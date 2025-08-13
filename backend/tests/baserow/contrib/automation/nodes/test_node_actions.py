import uuid

import pytest

from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import (
    CreateAutomationNodeActionType,
    DeleteAutomationNodeActionType,
    ReplaceAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    LocalBaserowRowsUpdatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.action.handler import ActionHandler
from baserow.core.cache import local_cache


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    node_before = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    node_after = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
        previous_node=node_before,
    )
    node_type = automation_node_type_registry.get(LocalBaserowCreateRowNodeType.type)

    with local_cache.context():
        node = CreateAutomationNodeActionType.do(
            user,
            node_type,
            workflow,
            data={"before_id": node_after.id},
        )

    # The node is created
    node_after.refresh_from_db()
    assert node.previous_node_id == node_before.id
    assert node_after.previous_node_id == node.id

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert node.trashed
    assert node_after.previous_node_id == node_before.id

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The node is restored
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert not node.trashed
    assert node_after.previous_node_id == node.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_replace_automation_action_node_type(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    node_after = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type
    )

    with local_cache.context():
        replaced_node = ReplaceAutomationNodeActionType.do(
            user, node.id, LocalBaserowUpdateRowNodeType.type
        )

    # The original node is trashed, we have a new node of the new type.
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert node.trashed
    assert isinstance(replaced_node, LocalBaserowUpdateRowNodeType.model_class)
    assert node_after.previous_node_id == replaced_node.id

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original node is restored, the new node is trashed.
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert not node.trashed
    replaced_node.refresh_from_db(fields=["trashed"])
    assert replaced_node.trashed
    assert node_after.previous_node_id == node.id

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original node is trashed again, the new node is restored.
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert node.trashed
    replaced_node.refresh_from_db(fields=["trashed"])
    assert not replaced_node.trashed
    assert node_after.previous_node_id == replaced_node.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_replace_automation_trigger_node_type(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    original_trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow
    )
    action_node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )

    with local_cache.context():
        replaced_trigger = ReplaceAutomationNodeActionType.do(
            user, original_trigger.id, LocalBaserowRowsUpdatedNodeTriggerType.type
        )

    # The original trigger is trashed, we have a new trigger of the new type.
    original_trigger.refresh_from_db(fields=["trashed"])
    action_node.refresh_from_db()
    assert original_trigger.trashed
    assert isinstance(
        replaced_trigger, LocalBaserowRowsUpdatedNodeTriggerType.model_class
    )
    assert action_node.previous_node_id == replaced_trigger.id

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original trigger is restored, the new trigger is trashed.
    original_trigger.refresh_from_db(fields=["trashed"])
    action_node.refresh_from_db()
    assert not original_trigger.trashed
    replaced_trigger.refresh_from_db(fields=["trashed"])
    assert replaced_trigger.trashed
    assert action_node.previous_node_id == original_trigger.id

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original trigger is trashed again, the new trigger is restored.
    original_trigger.refresh_from_db(fields=["trashed"])
    action_node.refresh_from_db()
    assert original_trigger.trashed
    replaced_trigger.refresh_from_db(fields=["trashed"])
    assert not replaced_trigger.trashed
    assert action_node.previous_node_id == replaced_trigger.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    node_before = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
        previous_node=node_before,
    )
    node_after = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, previous_node=node
    )

    with local_cache.context():
        DeleteAutomationNodeActionType.do(user, node.id)

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert node.trashed
    assert node_after.previous_node_id == node_before.id

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original node is restored
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert not node.trashed
    assert node_after.previous_node_id == node.id

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The node is trashed again
    node.refresh_from_db(fields=["trashed"])
    node_after.refresh_from_db()
    assert node.trashed
    assert node_after.previous_node_id == node_before.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_node_action_after_nothing(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    node_before = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
        previous_node=node_before,
    )

    with local_cache.context():
        DeleteAutomationNodeActionType.do(user, node.id)

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The original node is restored
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The node is trashed again
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed
