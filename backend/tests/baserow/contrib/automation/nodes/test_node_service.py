from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeNotMovable,
    AutomationNodeReferenceNodeInvalid,
)
from baserow.contrib.automation.nodes.models import LocalBaserowCreateRowActionNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.fixtures import Fixtures

SERVICE_PATH = "baserow.contrib.automation.nodes.service"


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_create_node(mocked_signal, data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    node_type = automation_node_type_registry.get("local_baserow_create_row")

    service = AutomationNodeService()
    node = service.create_node(
        user,
        node_type,
        workflow,
        reference_node_id=workflow.get_trigger().id,
        position="south",
        output="",
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_create_row": {},
            "local_baserow_rows_created": {"next": {"": ["local_baserow_create_row"]}},
        }
    )

    assert isinstance(node, LocalBaserowCreateRowActionNode)

    mocked_signal.send.assert_called_once_with(service, node=node, user=user)


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_create_node_as_child(mocked_signal, data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    node_type = automation_node_type_registry.get("local_baserow_create_row")

    service = AutomationNodeService()
    node = service.create_node(
        user,
        node_type,
        workflow,
        reference_node_id=iterator.id,
        position="child",
        output="",
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_create_row": {},
            "iterator": {"children": ["local_baserow_create_row"]},
            "local_baserow_rows_created": {"next": {"": ["iterator"]}},
        }
    )

    assert isinstance(node, LocalBaserowCreateRowActionNode)
    mocked_signal.send.assert_called_once_with(service, node=node, user=user)


@pytest.mark.django_db
def test_create_node_as_child_not_in_container(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    create_row = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow
    )

    node_type = automation_node_type_registry.get("local_baserow_create_row")

    service = AutomationNodeService()

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        service.create_node(
            user,
            node_type,
            workflow,
            reference_node_id=create_row.id,
            position="child",
            output="",
        )

    assert exc.value.args[0] == f"The reference node {create_row.id} can't have child"


@pytest.mark.django_db
def test_create_node_reference_node_invalid(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    workflow_b = data_fixture.create_automation_workflow(user)
    node1_b = workflow_b.get_trigger()
    node2_b = data_fixture.create_automation_node(workflow=workflow_b)

    node_type = automation_node_type_registry.get("local_baserow_create_row")

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        AutomationNodeService().create_node(
            user,
            node_type,
            workflow=workflow,
            reference_node_id=node2_b.id,
            position="south",
            output="",
        )

    assert exc.value.args[0] == f"The reference node {node2_b.id} doesn't exist"


@pytest.mark.django_db
def test_create_node_permission_error(data_fixture: Fixtures):
    workflow = data_fixture.create_automation_workflow()
    node_type = automation_node_type_registry.get("local_baserow_create_row")
    another_user = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().create_node(another_user, node_type, workflow)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to workspace "
        f"{workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_node(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    node_instance = AutomationNodeService().get_node(user, node.id)

    assert node_instance.specific == node


@pytest.mark.django_db
def test_get_node_invalid_node_id(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().get_node(user, 100)

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_get_node_permission_error(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().get_node(another_user, node.id)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {node.workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_nodes(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(user=user, workflow=workflow)
    assert AutomationNodeService().get_nodes(user, workflow) == [trigger, node.specific]


@pytest.mark.django_db
def test_get_nodes_permission_error(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().get_nodes(another_user, workflow)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_node_updated")
@pytest.mark.django_db
def test_update_node(mocked_signal, data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    service = AutomationNodeService()
    updated_node = service.update_node(user, node.id, label="foo")

    node.refresh_from_db()
    assert node.label == "foo"

    mocked_signal.send.assert_called_once_with(
        service, user=user, node=updated_node.node
    )


@pytest.mark.django_db
def test_update_node_invalid_node_id(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().update_node(user, 100, label="foo")

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_update_node_permission_error(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().update_node(another_user, node.id, label="foo")

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {node.workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_node_deleted")
@pytest.mark.django_db
def test_delete_node(mocked_signal, data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    service = AutomationNodeService()
    service.delete_node(user, node.id)
    node.refresh_from_db()
    assert node.trashed

    mocked_signal.send.assert_called_once_with(
        service, workflow=node.workflow, node_id=node.id, user=user
    )

    trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        node.id,
    )
    assert not trash_entry.managed


@pytest.mark.django_db
def test_delete_node_invalid_node_id(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().delete_node(user, 100)

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_delete_node_permission_error(data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().delete_node(another_user, node.id)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {node.workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_duplicate_node(mocked_signal, data_fixture: Fixtures):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(workflow=workflow, label="test")

    service = AutomationNodeService()
    duplicated_node = service.duplicate_node(user, node.id)

    assert duplicated_node == workflow.automation_workflow_nodes.all()[2].specific

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["test"]}},
            "test": {"next": {"": ["test-"]}},
            "test-": {},
        }
    )

    assert duplicated_node.label == "test"

    mocked_signal.send.assert_called_once_with(service, node=duplicated_node, user=user)


@pytest.mark.django_db
def test_duplicate_node_permission_error(data_fixture: Fixtures):
    user = data_fixture.create_user()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().duplicate_node(another_user, node.id)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_replace_simple_node(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    original_node = data_fixture.create_automation_node(workflow=workflow)

    node_type = automation_node_type_registry.get("local_baserow_update_row")

    replace_result = AutomationNodeService().replace_node(
        user, original_node.id, node_type.type
    )

    original_node.refresh_from_db()
    assert original_node.trashed

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {},
        }
    )

    replace_result.node.id != original_node.id
    replace_result.original_node_type == original_node.get_type().type
    replace_result.original_node_id == original_node.id


@pytest.mark.django_db
def test_replace_node_in_first(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    first_node = data_fixture.create_automation_node(workflow=workflow)
    second_node = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(
        workflow=workflow,
    )

    node_type = automation_node_type_registry.get("local_baserow_update_row")

    service = AutomationNodeService()
    replace_result = service.replace_node(user, first_node.id, node_type.type)

    assert workflow.automation_workflow_nodes.count() == 4

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {"next": {"": ["local_baserow_create_row-"]}},
            "local_baserow_create_row-": {},
        }
    )


@pytest.mark.django_db
def test_replace_node_in_middle(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    first_node = data_fixture.create_automation_node(workflow=workflow, label="first")
    node_to_replace = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(workflow=workflow, label="last")

    node_type = automation_node_type_registry.get("local_baserow_update_row")

    replace_result = AutomationNodeService().replace_node(
        user, node_to_replace.id, node_type.type
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["first"]}},
            "first": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {"next": {"": ["last"]}},
            "last": {},
        }
    )

    assert workflow.automation_workflow_nodes.count() == 4


@pytest.mark.django_db
def test_replace_node_in_last(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    first_node = data_fixture.create_automation_node(workflow=workflow)
    second_node = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(workflow=workflow)

    node_type = automation_node_type_registry.get("local_baserow_update_row")

    replace_result = AutomationNodeService().replace_node(
        user, last_node.id, node_type.type
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["local_baserow_create_row"]}},
            "local_baserow_create_row": {"next": {"": ["local_baserow_create_row-"]}},
            "local_baserow_create_row-": {"next": {"": ["local_baserow_update_row"]}},
            "local_baserow_update_row": {},
        }
    )

    assert workflow.automation_workflow_nodes.count() == 4


@pytest.mark.django_db
def test_move_fixed_node_throws_exception(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    action1 = data_fixture.create_automation_node(workflow=workflow)

    with pytest.raises(AutomationNodeNotMovable) as exc:
        AutomationNodeService().move_node(user, trigger.id, action1.id, "south", "")

    assert exc.value.args[0] == "Trigger nodes cannot be moved."


@pytest.mark.django_db
def test_move_simple_node(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    # <-- to here
    action2 = data_fixture.create_automation_node(workflow=workflow, label="action2")
    action3 = data_fixture.create_automation_node(
        workflow=workflow, label="action3"
    )  # <- from here
    action4 = data_fixture.create_automation_node(workflow=workflow, label="action4")

    # move `action3` to be after `trigger`
    move_result = AutomationNodeService().move_node(
        user, action3.id, reference_node_id=action1.id, position="south", output=""
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "action1": {"next": {"": ["action3"]}},
            "action3": {"next": {"": ["action2"]}},
            "action2": {"next": {"": ["action4"]}},
            "action4": {},
            "local_baserow_rows_created": {"next": {"": ["action1"]}},
        }
    )

    # The node we're trying to move is `action3`
    assert move_result.node == action3
    assert move_result.previous_reference_node == action2
    assert move_result.previous_position == "south"
    assert move_result.previous_output == ""


@pytest.mark.django_db
def test_move_node_to_edge_above_existing_output(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    core_router_with_edges = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
        reference_node=workflow.get_trigger(),
    )
    router = core_router_with_edges.router
    edge1 = core_router_with_edges.edge1
    # <- to here
    edge1_output = core_router_with_edges.edge1_output
    edge2 = core_router_with_edges.edge2
    edge2_output = core_router_with_edges.edge2_output  # <- from here
    fallback_output_node = core_router_with_edges.fallback_output_node

    # move `edge2_output` to be *above* `edge1_output` inside `edge1`
    move_result = AutomationNodeService().move_node(
        user,
        edge2_output.id,
        reference_node_id=router.id,
        position="south",
        output=str(edge1.uid),
    )

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

    assert move_result.node == edge2_output
    assert move_result.previous_reference_node == router
    assert move_result.previous_position == "south"
    assert move_result.previous_output == str(edge2.uid)


@pytest.mark.django_db
def test_move_node_in_container(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow
    )  # <-inside here
    action2 = data_fixture.create_automation_node(workflow=workflow, label="action2")
    action3 = data_fixture.create_automation_node(
        workflow=workflow, label="action3"
    )  # <- from here
    action4 = data_fixture.create_automation_node(workflow=workflow, label="action4")

    # move `action3` to be the first child of iterator
    move_result = AutomationNodeService().move_node(
        user, action3.id, reference_node_id=iterator.id, position="child", output=""
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["action1"]}},
            "action1": {"next": {"": ["iterator"]}},
            "iterator": {"children": ["action3"], "next": {"": ["action2"]}},
            "action3": {},
            "action2": {"next": {"": ["action4"]}},
            "action4": {},
        }
    )

    # The node we're trying to move is `action3`
    assert move_result.node == action3
    assert move_result.previous_reference_node == action2
    assert move_result.previous_position == "south"
    assert move_result.previous_output == ""


@pytest.mark.django_db
def test_move_node_outside_of_container(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    action2 = data_fixture.create_automation_node(
        workflow=workflow, label="action2", reference_node=iterator, position="child"
    )  # <- from here
    action3 = data_fixture.create_automation_node(workflow=workflow, label="action3")
    # <- to here
    action4 = data_fixture.create_automation_node(workflow=workflow, label="action4")

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["action1"]}},
            "action1": {"next": {"": ["iterator"]}},
            "iterator": {"children": ["action2"], "next": {"": ["action3"]}},
            "action2": {},
            "action3": {"next": {"": ["action4"]}},
            "action4": {},
        }
    )

    # move `action3` to be the first child of iterator
    move_result = AutomationNodeService().move_node(
        user, action2.id, reference_node_id=action3.id, position="south", output=""
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["action1"]}},
            "action1": {"next": {"": ["iterator"]}},
            "iterator": {"next": {"": ["action3"]}},
            "action2": {"next": {"": ["action4"]}},
            "action3": {"next": {"": ["action2"]}},
            "action4": {},
        }
    )

    # The node we're trying to move is `action3`
    assert move_result.node == action2
    assert move_result.previous_reference_node == iterator
    assert move_result.previous_position == "child"
    assert move_result.previous_output == ""


@pytest.mark.django_db
def test_move_container_after_itself(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    action2 = data_fixture.create_automation_node(workflow=workflow, label="action2")
    action3 = data_fixture.create_automation_node(workflow=workflow, label="action3")
    action4 = data_fixture.create_automation_node(workflow=workflow, label="action4")

    # move `action3` to be the first child of iterator
    move_result = AutomationNodeService().move_node(
        user, iterator.id, reference_node_id=action4.id, position="south", output=""
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["action1"]}},
            "action1": {"next": {"": ["action2"]}},
            "action2": {"next": {"": ["action3"]}},
            "action3": {"next": {"": ["action4"]}},
            "action4": {"next": {"": ["iterator"]}},
            "iterator": {},
        }
    )


@pytest.mark.django_db
def test_move_container_inside_itself_should_fail(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    iterator2 = data_fixture.create_core_iterator_action_node(
        workflow=workflow, reference_node=iterator, position="child"
    )
    action2 = data_fixture.create_automation_node(
        workflow=workflow, label="action2", reference_node=iterator2, position="child"
    )
    action3 = data_fixture.create_automation_node(
        workflow=workflow, label="action3", reference_node=action2, position="south"
    )
    action4 = data_fixture.create_automation_node(
        workflow=workflow, label="action4", reference_node=iterator2, position="south"
    )

    with pytest.raises(AutomationNodeNotMovable) as exc:
        AutomationNodeService().move_node(
            user, iterator.id, reference_node_id=action3.id, position="south", output=""
        )

    assert exc.value.args[0] == "A container node cannot be moved inside itself"

    with pytest.raises(AutomationNodeNotMovable) as exc:
        AutomationNodeService().move_node(
            user,
            iterator.id,
            reference_node_id=iterator2.id,
            position="south",
            output="",
        )

    assert exc.value.args[0] == "A container node cannot be moved inside itself"

    with pytest.raises(AutomationNodeNotMovable) as exc:
        AutomationNodeService().move_node(
            user,
            iterator.id,
            reference_node_id=iterator2.id,
            position="child",
            output="",
        )

    assert exc.value.args[0] == "A container node cannot be moved inside itself"


@pytest.mark.django_db
def test_move_node_invalid_reference_node(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow, label="action1")

    action2 = data_fixture.create_automation_node(workflow=workflow, label="action2")
    action3 = data_fixture.create_automation_node(workflow=workflow, label="action3")
    action4 = data_fixture.create_automation_node(workflow=workflow, label="action4")

    workflow_b = data_fixture.create_automation_workflow(user)
    node1_b = workflow_b.get_trigger()

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        AutomationNodeService().move_node(
            user, action3.id, reference_node_id=99999999, position="south", output=""
        )

    assert exc.value.args[0] == "The reference node 99999999 doesn't exist"

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        AutomationNodeService().move_node(
            user, action3.id, reference_node_id=action3.id, position="south", output=""
        )

    assert (
        exc.value.args[0] == "The reference node and the moved node must be different"
    )

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        AutomationNodeService().move_node(
            user, action3.id, reference_node_id=node1_b.id, position="south", output=""
        )

    assert exc.value.args[0] == f"The reference node {node1_b.id} doesn't exist"

    with pytest.raises(AutomationNodeReferenceNodeInvalid) as exc:
        AutomationNodeService().move_node(
            user, action3.id, reference_node_id=action2.id, position="child", output=""
        )

    assert exc.value.args[0] == f"The reference node {action2.id} can't have child"
