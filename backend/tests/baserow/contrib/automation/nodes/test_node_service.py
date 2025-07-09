from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeBeforeInvalid,
    AutomationNodeDoesNotExist,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import (
    AutomationNode,
    LocalBaserowCreateRowActionNode,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.core.exceptions import UserNotInWorkspace

SERVICE_PATH = "baserow.contrib.automation.nodes.service"


@patch(f"{SERVICE_PATH}.automation_node_created")
@pytest.mark.django_db
def test_create_node(mocked_signal, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_type = automation_node_type_registry.get("create_row")

    service = AutomationNodeService()
    node = service.create_node(user, node_type, workflow)

    assert isinstance(node, LocalBaserowCreateRowActionNode)
    mocked_signal.send.assert_called_once_with(service, node=node, user=user)


@pytest.mark.django_db
def test_create_node_before(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    node1 = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, order="1.0000"
    )
    node3 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, order="2.0000"
    )

    node_type = automation_node_type_registry.get("create_row")
    node2 = AutomationNodeService().create_node(
        user,
        node_type,
        workflow=workflow,
        before=node3,
    )

    nodes = AutomationNode.objects.all()
    assert nodes[0].id == node1.id
    assert nodes[1].id == node2.id
    assert nodes[2].id == node3.id


@pytest.mark.django_db
def test_create_node_before_invalid(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_b = data_fixture.create_automation_workflow(user=user)
    node1_b = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow_b, order="1.0000"
    )
    node2_b = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow_b, order="2.0000"
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
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_type = automation_node_type_registry.get("create_row")

    another_user, _ = data_fixture.create_user_and_token()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().create_node(another_user, node_type, workflow)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to workspace "
        f"{workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
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
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    nodes = AutomationNodeService().get_nodes(user, workflow)

    assert nodes[0].specific == node


@pytest.mark.django_db
def test_get_nodes_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

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
    workflow = data_fixture.create_automation_workflow(user=user)
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
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert workflow.automation_workflow_nodes.count() == 1

    service = AutomationNodeService()
    service.delete_node(user, node.id)

    assert workflow.automation_workflow_nodes.count() == 0
    mocked_signal.send.assert_called_once_with(
        service, workflow=node.workflow, node_id=node.id, user=user
    )


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
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    node_order = AutomationNodeHandler().get_nodes_order(workflow)
    assert node_order == [node_1.id, node_2.id]

    service = AutomationNodeService()
    new_order = service.order_nodes(user, workflow, [node_2.id, node_1.id])
    assert new_order == [node_2.id, node_1.id]

    node_order = AutomationNodeHandler().get_nodes_order(workflow)
    assert node_order == [node_2.id, node_1.id]
    mocked_signal.send.assert_called_once_with(
        service, workflow=workflow, order=node_order, user=user
    )


@pytest.mark.django_db
def test_order_nodes_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
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
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert workflow.automation_workflow_nodes.count() == 1

    service = AutomationNodeService()
    duplicated_node = service.duplicate_node(user, node)

    assert workflow.automation_workflow_nodes.count() == 2
    assert duplicated_node == workflow.automation_workflow_nodes.all()[1].specific

    mocked_signal.send.assert_called_once_with(service, node=duplicated_node, user=user)


@pytest.mark.django_db
def test_duplicate_node_permission_error(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    another_user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationNodeService().duplicate_node(another_user, node)

    assert str(e.value) == (
        f"User {another_user.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )
