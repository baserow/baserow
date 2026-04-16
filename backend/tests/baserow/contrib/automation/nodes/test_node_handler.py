import pytest

from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowRowsCreatedTriggerNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.local_baserow.models import LocalBaserowRowsCreated
from baserow.core.cache import local_cache
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyDict


@pytest.mark.django_db
def test_create_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(create_trigger=False)

    node_type = automation_node_type_registry.get("local_baserow_rows_created")
    prepared_values = node_type.prepare_values({"workflow": workflow}, user)

    node = AutomationNodeHandler().create_node(node_type, **prepared_values)

    assert isinstance(node, LocalBaserowRowsCreatedTriggerNode)


@pytest.mark.django_db
def test_get_nodes(data_fixture, django_assert_num_queries):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()

    local_cache.clear()

    with django_assert_num_queries(1):
        nodes_qs = AutomationNodeHandler().get_nodes(workflow, specific=False)
        assert [n.id for n in nodes_qs.all()] == [trigger.id]

    with django_assert_num_queries(6):
        nodes = AutomationNodeHandler().get_nodes(workflow, specific=True)
        assert [n.id for n in nodes] == [trigger.id]
        assert isinstance(nodes[0].service, LocalBaserowRowsCreated)


@pytest.mark.django_db
def test_get_nodes_excludes_trashed_application(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node()
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
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node()
    workflow = node.workflow
    automation = workflow.automation

    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationNodeDoesNotExist) as e:
        AutomationNodeHandler().get_node(node.id)

    assert str(e.value) == f"The node {node.id} does not exist."


@pytest.mark.django_db
def test_update_node(data_fixture):
    user = data_fixture.create_user()
    node = data_fixture.create_automation_node(user=user)

    assert node.label == ""

    updated_node = AutomationNodeHandler().update_node(node, label="foo result")

    assert updated_node.label == "foo result"


@pytest.mark.django_db
def test_export_prepared_values(data_fixture):
    node = data_fixture.create_automation_node(label="My node")

    values = node.get_type().export_prepared_values(node)

    assert values == {
        "label": "My node",
        "service": AnyDict(),
        "workflow": node.workflow_id,
    }


@pytest.mark.django_db
def test_duplicate_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    action1 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="test"
    )
    duplicated_node = AutomationNodeHandler().duplicate_node(action1)

    assert duplicated_node.label == "test"


@pytest.mark.django_db
def test_export_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_automation_node(
        workflow=workflow,
    )

    result = AutomationNodeHandler().export_node(node)

    assert result == {
        "id": node.id,
        "label": node.label,
        "service": AnyDict(),
        "type": "local_baserow_create_row",
        "workflow_id": node.workflow.id,
    }


@pytest.mark.django_db
def test_import_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    exported_node["label"] = "Imported"
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }

    result = AutomationNodeHandler().import_node(workflow, exported_node, id_mapping)

    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(result.automationnode_ptr)


@pytest.mark.django_db
def test_import_nodes(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    exported_node["label"] = "Imported"
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }

    result = AutomationNodeHandler().import_nodes(workflow, [exported_node], id_mapping)
    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(result[0].automationnode_ptr)


@pytest.mark.django_db
def test_import_node_only(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    node = data_fixture.create_automation_node(workflow=workflow)

    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    exported_node["label"] = "Imported"
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    new_node = AutomationNodeHandler().import_node_only(
        workflow, exported_node, id_mapping
    )
    assert workflow.automation_workflow_nodes.contains(trigger.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(new_node.automationnode_ptr)

    assert id_mapping == {
        "integrations": MirrorDict(),
        "automation_edge_outputs": {},
        "automation_workflow_nodes": {node.id: new_node.id},
        "services": {node.service_id: new_node.service_id},
    }
