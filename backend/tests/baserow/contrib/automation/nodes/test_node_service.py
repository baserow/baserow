from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeBeforeInvalid,
    AutomationNodeDoesNotExist,
    AutomationNodeNotMovable,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowCreateRowActionNode
from baserow.contrib.automation.nodes.registries import (
    ReplaceAutomationNodeTrashOperationType,
    automation_node_type_registry,
)
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.contrib.automation.nodes.types import NextAutomationNodeValues
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.trash.handler import TrashHandler

SERVICE_PATH = "baserow.contrib.automation.nodes.service"


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_create_node(mocked_signal, data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    node_type = automation_node_type_registry.get("create_row")

    service = AutomationNodeService()
    node = service.create_node(user, node_type, workflow)

    assert isinstance(node, LocalBaserowCreateRowActionNode)
    mocked_signal.send.assert_called_once_with(service, node=node, user=user)


@pytest.mark.django_db
def test_create_node_before_invalid(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    workflow_b = data_fixture.create_automation_workflow(user)
    node1_b = workflow_b.get_trigger(specific=False)
    node2_b = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow_b
    )

    node_type = automation_node_type_registry.get("create_row")

    with pytest.raises(AutomationNodeBeforeInvalid) as exc:
        AutomationNodeService().create_node(
            user, node_type, workflow=workflow, before=node2_b
        )
    assert (
        exc.value.args[0]
        == "The `before` node must belong to the same workflow as the one supplied."
    )

    with pytest.raises(AutomationNodeBeforeInvalid) as exc:
        AutomationNodeService().create_node(
            user, node_type, workflow=workflow_b, before=node1_b
        )
    assert exc.value.args[0] == "You cannot create an automation node before a trigger."


@pytest.mark.django_db
def test_create_node_permission_error(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node_type = automation_node_type_registry.get("create_row")
    another_user = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().create_node(another_user, node_type, workflow)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to workspace "
        f"{workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    node_instance = AutomationNodeService().get_node(user, node.id)

    assert node_instance.specific == node


@pytest.mark.django_db
def test_get_node_invalid_node_id(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().get_node(user, 100)

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_get_node_permission_error(data_fixture):
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
def test_get_nodes(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(user=user, workflow=workflow)
    assert AutomationNodeService().get_nodes(user, workflow) == [trigger, node.specific]


@pytest.mark.django_db
def test_get_nodes_permission_error(data_fixture):
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
def test_update_node(mocked_signal, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)
    assert node.previous_node_output == ""

    service = AutomationNodeService()
    updated_node = service.update_node(user, node.id, previous_node_output="foo")

    node.refresh_from_db()
    assert node.previous_node_output == "foo"

    mocked_signal.send.assert_called_once_with(
        service, user=user, node=updated_node.node
    )


@pytest.mark.django_db
def test_update_node_invalid_node_id(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().update_node(user, 100, previous_node_output="foo")

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_update_node_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().update_node(
            another_user, node.id, previous_node_output="foo"
        )

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {node.workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_node_deleted")
@pytest.mark.django_db
def test_delete_node(mocked_signal, data_fixture):
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
def test_delete_node_with_managed_trash_entry(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    AutomationNodeService().delete_node(
        user, node.id, trash_operation_type=ReplaceAutomationNodeTrashOperationType.type
    )
    node.refresh_from_db()
    assert node.trashed

    trash_entry = TrashHandler.get_trash_entry(
        AutomationNodeTrashableItemType.type,
        node.id,
    )
    assert trash_entry.managed


@pytest.mark.django_db
def test_delete_node_invalid_node_id(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeService().delete_node(user, 100)

    assert str(e.value) == "The node 100 does not exist."


@pytest.mark.django_db
def test_delete_node_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().delete_node(another_user, node.id)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {node.workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_nodes_reordered")
@pytest.mark.django_db
def test_order_nodes(mocked_signal, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    node_order = AutomationNodeHandler().get_nodes_order(workflow)
    assert node_order == [trigger.id, node_1.id, node_2.id]

    service = AutomationNodeService()
    new_order = service.order_nodes(user, workflow, [trigger.id, node_2.id, node_1.id])
    assert new_order == [trigger.id, node_2.id, node_1.id]

    node_order = AutomationNodeHandler().get_nodes_order(workflow)
    assert node_order == [trigger.id, node_2.id, node_1.id]
    mocked_signal.send.assert_called_once_with(
        service, workflow=workflow, order=node_order, user=user
    )


@pytest.mark.django_db
def test_order_nodes_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().order_nodes(
            another_user, workflow, [node_2.id, node_1.id]
        )

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_duplicate_node(mocked_signal, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(workflow=workflow)

    service = AutomationNodeService()
    duplication = service.duplicate_node(user, node)

    assert (
        duplication.duplicated_node
        == workflow.automation_workflow_nodes.all()[2].specific
    )

    mocked_signal.send.assert_called_once_with(
        service, node=duplication.duplicated_node, user=user
    )


@pytest.mark.django_db
def test_duplicate_node_permission_error(data_fixture):
    user = data_fixture.create_user()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().duplicate_node(another_user, node)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_replace_simple_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    original_node = data_fixture.create_automation_node(workflow=workflow)

    node_type = automation_node_type_registry.get("update_row")

    replace_result = AutomationNodeService().replace_node(
        user, original_node.id, node_type.type
    )
    original_node.refresh_from_db()
    assert original_node.trashed

    assert replace_result.node.get_type() == node_type
    assert replace_result.node.previous_node_id == trigger.id
    assert replace_result.original_node_id == original_node.id
    assert replace_result.original_node_type == "create_row"


@pytest.mark.django_db
def test_replace_node_in_first(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    first_node = data_fixture.create_automation_node(workflow=workflow)
    second_node = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(
        workflow=workflow,
    )

    node_type = automation_node_type_registry.get("update_row")

    service = AutomationNodeService()
    replace_result = service.replace_node(user, first_node.id, node_type.type)

    assert workflow.automation_workflow_nodes.count() == 4

    second_node.refresh_from_db()
    last_node.refresh_from_db()

    assert replace_result.node.id == second_node.previous_node.id
    assert replace_result.node.previous_node_id == trigger.id
    assert last_node.previous_node.id == second_node.id

    assert second_node.previous_node.get_type().type == "update_row"


@pytest.mark.django_db
def test_replace_node_in_middle(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    first_node = data_fixture.create_automation_node(workflow=workflow)
    node_to_replace = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(workflow=workflow)

    node_type = automation_node_type_registry.get("update_row")

    replace_result = AutomationNodeService().replace_node(
        user, node_to_replace.id, node_type.type
    )

    assert workflow.automation_workflow_nodes.count() == 4

    last_node.refresh_from_db()
    first_node.refresh_from_db()

    assert replace_result.node.id == last_node.previous_node.id
    assert replace_result.node.previous_node.id == first_node.id
    assert first_node.previous_node_id == trigger.id

    assert last_node.previous_node.get_type().type == "update_row"


@pytest.mark.django_db
def test_replace_node_in_last(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    first_node = data_fixture.create_automation_node(workflow=workflow)
    second_node = data_fixture.create_automation_node(workflow=workflow)
    last_node = data_fixture.create_automation_node(workflow=workflow)

    node_type = automation_node_type_registry.get("update_row")

    service = AutomationNodeService()
    replace_result = service.replace_node(user, last_node.id, node_type.type)

    first_node.refresh_from_db()
    second_node.refresh_from_db()

    assert replace_result.node.previous_node.id == second_node.id
    assert second_node.previous_node.id == first_node.id
    assert first_node.previous_node_id == trigger.id

    assert (
        workflow.automation_workflow_nodes.get(previous_node=second_node)
        .get_type()
        .type
        == "update_row"
    )


@pytest.mark.django_db
def test_simulate_dispatch_node_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().simulate_dispatch_node(another_user, node.id)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_simulate_dispatch_node_trigger(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    trigger_node = data_fixture.create_local_baserow_rows_created_trigger_node(
        user=user
    )

    assert trigger_node.service.sample_data is None
    assert trigger_node.workflow.simulate_until_node is None

    AutomationNodeService().simulate_dispatch_node(user, trigger_node.id)

    trigger_node.refresh_from_db()

    assert trigger_node.service.sample_data is None
    assert trigger_node.workflow.simulate_until_node.id == trigger_node.id


@pytest.mark.django_db
def test_simulate_dispatch_node_action(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )
    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=data_fixture.create_local_baserow_integration(user=user),
    )
    action_service.field_mappings.create(
        field=fields[0],
        value="'A new row'",
    )
    action_node = data_fixture.create_automation_node(
        user=user,
        workflow=workflow,
        type="create_row",
        service=action_service,
    )

    assert action_node.service.sample_data is None

    AutomationNodeService().simulate_dispatch_node(user, action_node.id)

    action_node.refresh_from_db()
    row = table.get_model().objects.first()

    assert action_node.service.sample_data == {
        "data": {
            f"field_{fields[0].id}": "A new row",
            "id": row.id,
            "order": str(row.order),
        },
        "output_uid": "",
        "status": 200,
    }


@pytest.mark.django_db
def test_move_fixed_node_throws_exception(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger(specific=False)
    action1 = data_fixture.create_automation_node(workflow=workflow)
    with pytest.raises(AutomationNodeNotMovable) as exc:
        AutomationNodeService().move_node(user, trigger.id, action1.id)
    assert exc.value.args[0] == "This automation node cannot be moved."


@pytest.mark.django_db
def test_move_simple_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    action1 = data_fixture.create_automation_node(workflow=workflow)
    # <-- to here
    action2 = data_fixture.create_automation_node(workflow=workflow)
    action3 = data_fixture.create_automation_node(workflow=workflow)  # <- from here
    action4 = data_fixture.create_automation_node(workflow=workflow)

    # move `action3` to be after `trigger`
    move_result = AutomationNodeService().move_node(user, action3.id, action1.id)

    # The node we're trying to move is `action3`
    assert move_result.node == action3
    assert move_result.node.previous_node_id == action1.id
    assert move_result.node.previous_node_output == ""

    # The node's origin previous node was `action2`
    assert move_result.origin_previous_node_id == action2.id
    assert move_result.origin_previous_node_output == ""

    # Before the move, at the origin, `action4` was after `action3`
    assert move_result.origin_old_next_nodes_values == [
        NextAutomationNodeValues(
            id=action4.id, previous_node_id=action3.id, previous_node_output=""
        )
    ]

    # After the move, at the origin, `action4` is now after `action2`
    assert move_result.origin_new_next_nodes_values == [
        NextAutomationNodeValues(
            id=action4.id, previous_node_id=action2.id, previous_node_output=""
        )
    ]

    # Before the move, at the destination, `action2` was after `action1`.
    assert move_result.destination_old_next_nodes_values == [
        NextAutomationNodeValues(
            id=action2.id, previous_node_id=action1.id, previous_node_output=""
        )
    ]

    # After the move, at the destination, `action2` is now after `action3`.
    assert move_result.destination_new_next_nodes_values == [
        NextAutomationNodeValues(
            id=action2.id, previous_node_id=action3.id, previous_node_output=""
        )
    ]

    # The node's destination previous node is now `action1`.
    assert move_result.destination_previous_node_id == action1.id
    assert move_result.destination_previous_node_output == ""


@pytest.mark.django_db
def test_move_node_to_edge_above_existing_output(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    core_router_with_edges = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    router = core_router_with_edges.router
    edge1 = core_router_with_edges.edge1
    # <- to here
    edge1_output = core_router_with_edges.edge1_output
    edge2 = core_router_with_edges.edge2
    edge2_output = core_router_with_edges.edge2_output  # <- from here

    # move `edge2_output` to be *above* `edge1_output` inside `edge1`
    move_result = AutomationNodeService().move_node(
        user, edge2_output.id, router.id, edge1_output.previous_node_output
    )

    # The node we're trying to move is `edge2_output`
    assert move_result.node == edge2_output
    assert move_result.node.previous_node_id == router.id
    assert move_result.node.previous_node_output == str(edge1.uid)

    # The node's origin previous node was `action2`
    assert move_result.origin_previous_node_id == router.id
    assert move_result.origin_previous_node_output == str(edge2.uid)

    # Before the move, at the origin, there are no next nodes after `edge2_output`.
    assert move_result.origin_old_next_nodes_values == []

    # After the move, at the origin, there are still no next nodes.
    assert move_result.origin_new_next_nodes_values == []

    # Before the move, at the destination, `edge1_output` was after `router`.
    assert move_result.destination_old_next_nodes_values == [
        NextAutomationNodeValues(
            id=edge1_output.id,
            previous_node_id=router.id,
            previous_node_output=str(edge1.uid),
        )
    ]

    # After the move, at the destination, `edge1_output` is now after `edge2_output`.
    assert move_result.destination_new_next_nodes_values == [
        NextAutomationNodeValues(
            id=edge1_output.id,
            previous_node_id=edge2_output.id,
            previous_node_output="",
        )
    ]
