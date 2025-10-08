import uuid

import pytest

from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import (
    CreateAutomationNodeActionType,
    DeleteAutomationNodeActionType,
    DuplicateAutomationNodeActionType,
    MoveAutomationNodeActionType,
    ReplaceAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    LocalBaserowRowsUpdatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.core.action.handler import ActionHandler
from baserow.core.cache import local_cache
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
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
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
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

    # Confirm that the `node` trash entry exists, and it is
    # `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        node.id,
    )
    assert original_trash_entry.managed

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

    # Confirm that the `replaced_node` trash entry exists, and it
    # is `managed` to prevent users from restoring it manually.
    replaced_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        replaced_node.id,
    )
    assert replaced_trash_entry.managed

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

    # Confirm that the `node` trash entry still exists, and it
    # is `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        node.id,
    )
    assert original_trash_entry.managed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_replace_automation_trigger_node_type(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    original_trigger = workflow.get_trigger()
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

    # Confirm that the `original_trigger` trash entry exists, and
    # it is `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        original_trigger.id,
    )
    assert original_trash_entry.managed

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

    # Confirm that the `replaced_trigger` trash entry exists, and
    # it is `managed` to prevent users from restoring it manually.
    replaced_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        replaced_trigger.id,
    )
    assert replaced_trash_entry.managed

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

    # Confirm that the `original_trigger` trash entry still exists,
    # and it is `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        original_trigger.id,
    )
    assert original_trash_entry.managed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
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
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
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


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    source_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    after_source_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    with local_cache.context():
        duplicated_node = DuplicateAutomationNodeActionType.do(user, source_node.id)

    # The node is duplicated
    assert duplicated_node.previous_node_id == source_node.id
    after_source_node.refresh_from_db()
    assert after_source_node.previous_node_id == duplicated_node.id
    assert after_source_node.previous_node_output == ""

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The duplicated node is trashed
    duplicated_node.refresh_from_db(fields=["trashed"])
    assert duplicated_node.trashed
    after_source_node.refresh_from_db()
    assert after_source_node.previous_node_id == source_node.id
    assert after_source_node.previous_node_output == ""

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The duplicated node is restored
    duplicated_node.refresh_from_db(fields=["trashed"])
    assert not duplicated_node.trashed
    after_source_node.refresh_from_db()
    assert after_source_node.previous_node_id == duplicated_node.id
    assert after_source_node.previous_node_output == ""


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_node_action_with_multiple_outputs(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    core_router_with_edges = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    source_node = core_router_with_edges.router
    edge1 = core_router_with_edges.edge1
    edge1_output = core_router_with_edges.edge1_output
    edge2 = core_router_with_edges.edge2
    edge2_output = core_router_with_edges.edge2_output
    fallback_output_node = core_router_with_edges.fallback_output_node

    with local_cache.context():
        duplicated_node = DuplicateAutomationNodeActionType.do(user, source_node.id)

    # The node is duplicated
    assert duplicated_node.previous_node_id == source_node.id

    # The edge1/edge2 outputs are intact.
    edge1_output.refresh_from_db()
    assert edge1_output.previous_node_id == source_node.id
    assert edge1_output.previous_node_output == str(edge1.uid)
    edge2_output.refresh_from_db()
    assert edge2_output.previous_node_id == source_node.id
    assert edge2_output.previous_node_output == str(edge2.uid)

    # The original fallback output node is now after our duplicated router.
    fallback_output_node.refresh_from_db()
    assert fallback_output_node.previous_node_id == duplicated_node.id
    assert fallback_output_node.previous_node_output == ""

    with local_cache.context():
        ActionHandler.undo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The duplicated node is trashed
    duplicated_node.refresh_from_db(fields=["trashed"])
    assert duplicated_node.trashed
    fallback_output_node.refresh_from_db()
    # The original fallback output node is now after our source router, again.
    assert fallback_output_node.previous_node_id == source_node.id
    assert fallback_output_node.previous_node_output == ""

    with local_cache.context():
        ActionHandler.redo(
            user, [WorkflowActionScopeType.value(workflow.id)], session_id
        )

    # The duplicated node is restored
    duplicated_node.refresh_from_db(fields=["trashed"])
    assert not duplicated_node.trashed
    fallback_output_node.refresh_from_db()
    # The original fallback output node is now after our duplicated router, again.
    assert fallback_output_node.previous_node_id == duplicated_node.id
    assert fallback_output_node.previous_node_output == ""


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    after_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    previous_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    moved_node = MoveAutomationNodeActionType.do(user, node.id, after_node.id)

    assert moved_node.previous_node_id == after_node.id
    previous_node.refresh_from_db()
    assert previous_node.previous_node_id == moved_node.id

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    moved_node.refresh_from_db()
    assert moved_node.previous_node_id == previous_node.id
    previous_node.refresh_from_db()
    assert previous_node.previous_node_id == after_node.id

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    moved_node.refresh_from_db()
    assert moved_node.previous_node_id == after_node.id
    previous_node.refresh_from_db()
    assert previous_node.previous_node_id == moved_node.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_node_action_to_output(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    core_router_with_edges = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    router = core_router_with_edges.router
    edge1 = core_router_with_edges.edge1
    # <- to here
    edge1_output = core_router_with_edges.edge1_output
    edge2 = core_router_with_edges.edge2
    edge2_output = core_router_with_edges.edge2_output  # <- from here

    moved_node = MoveAutomationNodeActionType.do(
        user, edge2_output.id, router.id, edge1_output.previous_node_output
    )

    # The node we're trying to move is `edge2_output`
    assert moved_node == edge2_output
    assert moved_node.previous_node_id == router.id
    assert moved_node.previous_node_output == str(edge1.uid)

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    moved_node.refresh_from_db()
    assert moved_node.previous_node_id == router.id
    assert moved_node.previous_node_output == str(edge2.uid)

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    moved_node.refresh_from_db()
    assert moved_node.previous_node_id == router.id
    assert moved_node.previous_node_output == str(edge1.uid)
