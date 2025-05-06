import pytest

from baserow.contrib.automation.nodes.exceptions import AutomationNodeNotInWorkflow
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowRowCreatedTriggerNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.types import UpdatedAutomationNode


@pytest.mark.django_db
def test_create_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    node_type = automation_node_type_registry.get("row_created")
    prepared_values = node_type.prepare_values({}, user)

    node = AutomationNodeHandler().create_node(
        node_type, workflow=workflow, **prepared_values
    )

    assert isinstance(node, LocalBaserowRowCreatedTriggerNode)


@pytest.mark.django_db
def test_get_nodes(data_fixture):
    node = data_fixture.create_automation_node()

    nodes_qs = AutomationNodeHandler().get_nodes(node.workflow)

    assert [n.id for n in nodes_qs.all()] == [node.id]


@pytest.mark.django_db
def test_get_node(data_fixture):
    node = data_fixture.create_automation_node()

    node_instance = AutomationNodeHandler().get_node(node.id)

    assert node_instance.specific == node


@pytest.mark.django_db
def test_update_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    assert node.previous_node_output == ""

    node_instance = AutomationNodeHandler().update_node(
        node, previous_node_output="foo result"
    )

    assert node_instance == UpdatedAutomationNode(
        node=node,
        original_values={"previous_node_output": ""},
        new_values={"previous_node_output": "foo result"},
    )
    assert node.previous_node_output == "foo result"


@pytest.mark.django_db
def test_export_prepared_values(data_fixture):
    node = data_fixture.create_automation_node()

    values = AutomationNodeHandler().export_prepared_values(node)

    assert values == {"previous_node_output": ""}


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
        "order": node.order,
        "parent_node_id": None,
        "previous_node_id": None,
        "previous_node_output": "foo",
        "service_id": node.service.id,
        "type": "row_created",
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

    result = AutomationNodeHandler().import_node(workflow, exported_node, {})
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

    result = AutomationNodeHandler().import_nodes(workflow, [exported_node], {})
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

    id_mapping = {}
    new_node = AutomationNodeHandler().import_node_only(
        workflow, exported_node, id_mapping
    )
    assert workflow.automation_workflow_nodes.count() == 2

    assert new_node == workflow.automation_workflow_nodes.all()[1].specific
    assert id_mapping == {"automation_nodes": {node.id: new_node.id}}
