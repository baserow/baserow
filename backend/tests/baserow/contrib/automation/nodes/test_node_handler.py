import pytest

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeNotInWorkflow,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowCreateRowActionNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.local_baserow.models import LocalBaserowRowsCreated
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyDict


@pytest.mark.django_db
def test_create_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    node_type = automation_node_type_registry.get("create_row")
    prepared_values = node_type.prepare_values({}, user)

    node = AutomationNodeHandler().create_node(
        node_type, workflow=workflow, **prepared_values
    )

    assert isinstance(node, LocalBaserowCreateRowActionNode)


@pytest.mark.django_db
def test_get_nodes(data_fixture, django_assert_num_queries):
    node = data_fixture.create_local_baserow_rows_created_trigger_node()
    workflow = node.workflow

    with django_assert_num_queries(1):
        nodes_qs = AutomationNodeHandler().get_nodes(workflow, specific=False)
        assert [n.id for n in nodes_qs.all()] == [node.id]

    with django_assert_num_queries(6):
        nodes = AutomationNodeHandler().get_nodes(workflow, specific=True)
        assert [n.id for n in nodes] == [node.id]
        assert isinstance(nodes[0].service, LocalBaserowRowsCreated)


@pytest.mark.django_db
def test_get_nodes_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_local_baserow_rows_created_trigger_node()
    workflow = node.workflow
    automation = workflow.automation

    # Trash the automation application
    TrashHandler.trash(user, automation.workspace, automation, automation)

    nodes_qs = AutomationNodeHandler().get_nodes(workflow, specific=False)
    assert nodes_qs.count() == 0


@pytest.mark.django_db
def test_get_node(data_fixture):
    node = data_fixture.create_automation_node()

    node_instance = AutomationNodeHandler().get_node(node.id)

    assert node_instance.specific == node


@pytest.mark.django_db
def test_get_node_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node()
    workflow = node.workflow
    automation = workflow.automation

    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeHandler().get_node(node.id)

    assert str(e.value) == f"The node {node.id} does not exist."


@pytest.mark.django_db
def test_update_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    assert node.previous_node_output == ""

    updated_node = AutomationNodeHandler().update_node(
        node, previous_node_output="foo result"
    )

    assert updated_node.node.previous_node_output == "foo result"


@pytest.mark.django_db
def test_export_prepared_values(data_fixture):
    node = data_fixture.create_automation_node()

    values = node.get_type().export_prepared_values(node)

    assert values == {
        "service": AnyDict(),
        "workflow": node.workflow_id,
        "previous_node_output": "",
    }


@pytest.mark.django_db
def test_delete_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(user=user, workflow=workflow)

    assert workflow.automation_workflow_nodes.count() == 1

    AutomationNodeHandler().delete_node(user, node)

    assert workflow.automation_workflow_nodes.count() == 0


@pytest.mark.django_db
def test_get_nodes_order(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    order = AutomationNodeHandler().get_nodes_order(workflow)

    assert order == [node_1.id, node_2.id]


@pytest.mark.django_db
def test_order_nodes(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)

    order = AutomationNodeHandler().get_nodes_order(workflow)
    assert order == [node_1.id, node_2.id]

    new_order = AutomationNodeHandler().order_nodes(workflow, [node_2.id, node_1.id])
    assert new_order == [node_2.id, node_1.id]

    order = AutomationNodeHandler().get_nodes_order(workflow)
    assert order == [node_2.id, node_1.id]


@pytest.mark.django_db
def test_order_nodes_excludes_trashed_application(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow)
    automation = workflow.automation

    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationNodeNotInWorkflow) as e:
        AutomationNodeHandler().order_nodes(workflow, [node_2.id, node_1.id])

    assert str(e.value) == f"The node {node_2.id} does not belong to the workflow."


@pytest.mark.django_db
def test_order_nodes_invalid_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow_1 = data_fixture.create_automation_workflow(user=user)
    node_1 = data_fixture.create_automation_node(user=user, workflow=workflow_1)
    workflow_2 = data_fixture.create_automation_workflow(user=user)
    node_2 = data_fixture.create_automation_node(user=user, workflow=workflow_2)

    with pytest.raises(AutomationNodeNotInWorkflow) as e:
        AutomationNodeHandler().order_nodes(workflow_1, [node_2.id, node_1.id])

    assert str(e.value) == f"The node {node_2.id} does not belong to the workflow."


@pytest.mark.django_db
def test_duplicate_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, previous_node_output="foo"
    )
    assert node.previous_node_output == "foo"

    assert workflow.automation_workflow_nodes.count() == 1

    new_node = AutomationNodeHandler().duplicate_node(node)
    assert new_node.workflow == workflow
    assert new_node.previous_node_output == "foo"
    assert workflow.automation_workflow_nodes.count() == 2


@pytest.mark.django_db
def test_export_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, previous_node_output="foo")

    result = AutomationNodeHandler().export_node(node)

    assert result == {
        "id": node.id,
        "order": str(node.order),
        "parent_node_id": None,
        "previous_node_id": None,
        "previous_node_output": "foo",
        "service": AnyDict(),
        "type": "create_row",
        "workflow_id": node.workflow.id,
    }


@pytest.mark.django_db
def test_import_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, previous_node_output="foo"
    )
    assert workflow.automation_workflow_nodes.count() == 1

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {"integrations": MirrorDict()}

    result = AutomationNodeHandler().import_node(workflow, exported_node, id_mapping)
    assert workflow.automation_workflow_nodes.count() == 2

    assert result == workflow.automation_workflow_nodes.all()[1].specific


@pytest.mark.django_db
def test_import_nodes(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, previous_node_output="foo"
    )
    assert workflow.automation_workflow_nodes.count() == 1

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {"integrations": MirrorDict()}

    result = AutomationNodeHandler().import_nodes(workflow, [exported_node], id_mapping)
    assert workflow.automation_workflow_nodes.count() == 2

    assert result[0] == workflow.automation_workflow_nodes.all()[1].specific


@pytest.mark.django_db
def test_import_node_only(data_fixture):
    user, _ = data_fixture.create_user_and_token()

    workflow = data_fixture.create_automation_workflow(user=user)
    node = data_fixture.create_automation_node(
        user=user, workflow=workflow, previous_node_output="foo"
    )
    assert workflow.automation_workflow_nodes.count() == 1

    exported_node = AutomationNodeHandler().export_node(node)

    id_mapping = {"integrations": MirrorDict()}
    new_node = AutomationNodeHandler().import_node_only(
        workflow, exported_node, id_mapping
    )
    assert workflow.automation_workflow_nodes.count() == 2

    assert new_node == workflow.automation_workflow_nodes.all()[1].specific
    assert id_mapping == {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": {node.id: new_node.id},
        "services": {node.service_id: new_node.service_id},
    }
