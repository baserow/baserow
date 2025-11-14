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
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="Node before"
    )
    node_after = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
        previous_node=node_before,
        label="Node after",
    )
    node_type = automation_node_type_registry.get(LocalBaserowCreateRowNodeType.type)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Node before"]}},
            "Node before": {"next": {"": ["Node after"]}},
            "Node after": {},
        }
    )

    node = CreateAutomationNodeActionType.do(
        user,
        node_type,
        workflow,
        dict(reference_node_id=node_before.id, position="south", output=""),
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Node before"]}},
            "Node before": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {"next": {"": ["Node after"]}},
            "Node after": {},
        }
    )

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "Node after": {},
            "Node before": {"next": {"": ["Node after"]}},
            "local_baserow_rows_created": {"next": {"": ["Node before"]}},
        }
    )

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    # The node is restored
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Node before"]}},
            "Node before": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {"next": {"": ["Node after"]}},
            "Node after": {},
        }
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_replace_automation_action_node_type(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    node = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="To replace"
    )
    workflow.simulate_until_node_id = node.id
    workflow.save()

    data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="After"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "To replace": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["To replace"]}},
        }
    )

    replaced_node = ReplaceAutomationNodeActionType.do(
        user, node.id, LocalBaserowUpdateRowNodeType.type
    )

    workflow.refresh_from_db()
    assert workflow.simulate_until_node_id is None

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "local_baserow_rows_created": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {"next": {"": ["After"]}},
        }
    )

    # The original node is trashed, we have a new node of the new type.
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed
    assert isinstance(replaced_node, LocalBaserowUpdateRowNodeType.model_class)

    # Confirm that the `node` trash entry exists, and it is
    # `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        node.id,
    )
    assert original_trash_entry.managed

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "To replace": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["To replace"]}},
        }
    )

    # The original node is restored, the new node is trashed.
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed

    replaced_node.refresh_from_db(fields=["trashed"])
    assert replaced_node.trashed

    # Confirm that the `replaced_node` trash entry exists, and it
    # is `managed` to prevent users from restoring it manually.
    replaced_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        replaced_node.id,
    )
    assert replaced_trash_entry.managed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "local_baserow_rows_created": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {"next": {"": ["After"]}},
        }
    )
    # The original node is trashed again, the new node is restored.
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed

    replaced_node.refresh_from_db(fields=["trashed"])
    assert not replaced_node.trashed

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
    data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    workflow.simulate_until_node_id = original_trigger.id
    workflow.save()

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {},
        }
    )

    replaced_trigger = ReplaceAutomationNodeActionType.do(
        user, original_trigger.id, LocalBaserowRowsUpdatedNodeTriggerType.type
    )

    workflow.refresh_from_db()
    assert workflow.simulate_until_node_id is None

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_updated",
            "local_baserow_rows_updated": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {},
        }
    )

    # The original trigger is trashed, we have a new trigger of the new type.
    original_trigger.refresh_from_db(fields=["trashed"])

    assert original_trigger.trashed
    assert isinstance(
        replaced_trigger, LocalBaserowRowsUpdatedNodeTriggerType.model_class
    )

    # Confirm that the `original_trigger` trash entry exists, and
    # it is `managed` to prevent users from restoring it manually.
    original_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        original_trigger.id,
    )
    assert original_trash_entry.managed

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {},
        }
    )

    # The original trigger is restored, the new trigger is trashed.
    original_trigger.refresh_from_db(fields=["trashed"])
    assert not original_trigger.trashed

    replaced_trigger.refresh_from_db(fields=["trashed"])
    assert replaced_trigger.trashed

    # Confirm that the `replaced_trigger` trash entry exists, and
    # it is `managed` to prevent users from restoring it manually.
    replaced_trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        replaced_trigger.id,
    )
    assert replaced_trash_entry.managed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_updated",
            "local_baserow_rows_updated": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {},
        }
    )

    # The original trigger is trashed again, the new trigger is restored.
    original_trigger.refresh_from_db(fields=["trashed"])
    assert original_trigger.trashed

    replaced_trigger.refresh_from_db(fields=["trashed"])
    assert not replaced_trigger.trashed

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
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="Before"
    )
    node = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="To delete"
    )
    node_after = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="After"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "Before": {"next": {"": ["To delete"]}},
            "To delete": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    DeleteAutomationNodeActionType.do(user, node.id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "Before": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "Before": {"next": {"": ["To delete"]}},
            "To delete": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    # The original node is restored
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "After": {},
            "Before": {"next": {"": ["After"]}},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    # The node is trashed again
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_node_action_after_nothing(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    node_before = data_fixture.create_automation_node(
        workflow=workflow, type=LocalBaserowCreateRowNodeType.type, label="Before"
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
        previous_node=node_before,
        label="To delete",
    )
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "Before": {"next": {"": ["To delete"]}},
            "To delete": {},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    DeleteAutomationNodeActionType.do(user, node.id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "Before": {},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    # The node is trashed
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "Before": {"next": {"": ["To delete"]}},
            "To delete": {},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
    )

    # The original node is restored
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "Before": {},
            "local_baserow_rows_created": {"next": {"": ["Before"]}},
        }
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
        workflow=workflow, label="Source"
    )
    after_source_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="After"
    )
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Source"]}},
            "Source": {"next": {"": ["After"]}},
            "After": {},
        }
    )

    duplicated_node = DuplicateAutomationNodeActionType.do(user, source_node.id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Source"]}},
            "Source": {"next": {"": ["Source-"]}},
            "Source-": {"next": {"": ["After"]}},
            "After": {},
        }
    )

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    duplicated_node.refresh_from_db()
    assert duplicated_node.trashed

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Source"]}},
            "Source": {"next": {"": ["After"]}},
            "After": {},
        }
    )

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    duplicated_node.refresh_from_db()
    assert not duplicated_node.trashed

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["Source"]}},
            "Source": {"next": {"": ["Source-"]}},
            "Source-": {"next": {"": ["After"]}},
            "After": {},
        }
    )


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

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "router": {
                "next": {
                    "Default": ["fallback node"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )

    duplicated_node = DuplicateAutomationNodeActionType.do(user, source_node.id)
    duplicated_node.label = "Duplicated router"
    duplicated_node.save()

    assert duplicated_node.id != source_node.id

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["Duplicated router"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "Duplicated router": {"next": {"Default": ["fallback node"]}},
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "router": {
                "next": {
                    "Default": ["fallback node"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["Duplicated router"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "Duplicated router": {"next": {"Default": ["fallback node"]}},
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_node_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    first_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="first action"
    )
    second_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="second action"
    )
    node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="moved node"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "first action": {"next": {"": ["second action"]}},
            "second action": {"next": {"": ["moved node"]}},
            "moved node": {},
        }
    )

    moved_node = MoveAutomationNodeActionType.do(
        user, node.id, first_action.id, "south", ""
    )

    assert moved_node == node
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "first action": {"next": {"": ["moved node"]}},
            "moved node": {"next": {"": ["second action"]}},
            "second action": {},
        }
    )

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "first action": {"next": {"": ["second action"]}},
            "second action": {"next": {"": ["moved node"]}},
            "moved node": {},
        }
    )

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "first action": {"next": {"": ["moved node"]}},
            "moved node": {"next": {"": ["second action"]}},
            "second action": {},
        }
    )


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

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["fallback node"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "fallback node": {},
            "output edge 2": {},
            "output edge 1": {},
        }
    )

    moved_node = MoveAutomationNodeActionType.do(
        user, edge2_output.id, router.id, "south", str(edge1.uid)
    )

    # The node we're trying to move is `edge2_output`
    assert moved_node.id == edge2_output.id

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Do this": ["output edge 2"],
                    "Default": ["fallback node"],
                }
            },
            "output edge 2": {"next": {"": ["output edge 1"]}},
            "output edge 1": {},
            "fallback node": {},
        }
    )

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Default": ["fallback node"],
                    "Do that": ["output edge 2"],
                    "Do this": ["output edge 1"],
                }
            },
            "fallback node": {},
            "output edge 1": {},
            "output edge 2": {},
        }
    )

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Do this": ["output edge 2"],
                    "Default": ["fallback node"],
                }
            },
            "output edge 2": {"next": {"": ["output edge 1"]}},
            "output edge 1": {},
            "fallback node": {},
        }
    )
