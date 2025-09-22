from unittest.mock import patch

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
from baserow.test_utils.helpers import AnyDict, AnyInt, AnyStr


@pytest.mark.django_db
def test_create_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()

    node_type = automation_node_type_registry.get("create_row")
    prepared_values = node_type.prepare_values({}, user)

    node = AutomationNodeHandler().create_node(
        node_type, workflow=workflow, **prepared_values
    )

    assert isinstance(node, LocalBaserowCreateRowActionNode)


@pytest.mark.django_db
def test_create_node_at_the_end(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node_type = automation_node_type_registry.get("create_row")

    prepared_values = node_type.prepare_values({}, user)

    node = AutomationNodeHandler().create_node(
        node_type, workflow=workflow, **prepared_values
    )

    assert node.previous_node.id == trigger.id


@pytest.mark.django_db
def test_create_node_applies_previous_node_id(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    first = data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)
    second = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    assert trigger.previous_node_id is None
    assert first.previous_node_id == trigger.id
    assert second.previous_node_id == first.id

    before_second = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, before=second
    )
    trigger.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()

    assert trigger.previous_node_id is None
    assert first.previous_node_id == trigger.id
    assert before_second.previous_node_id == first.id
    assert second.previous_node_id == before_second.id


@pytest.mark.django_db
def test_get_nodes(data_fixture, django_assert_num_queries):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)

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

    assert node.previous_node_output == ""

    updated_node = AutomationNodeHandler().update_node(
        node, previous_node_output="foo result"
    )

    assert updated_node.node.previous_node_output == "foo result"


@pytest.mark.django_db
def test_export_prepared_values(data_fixture):
    node = data_fixture.create_automation_node(label="My node")

    values = node.get_type().export_prepared_values(node)

    assert values == {
        "label": "My node",
        "service": AnyDict(),
        "workflow": node.workflow_id,
        "previous_node_id": node.previous_node_id,
        "previous_node_output": node.previous_node_output,
    }


@pytest.mark.django_db
def test_get_nodes_order(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node_1 = data_fixture.create_automation_node(workflow=workflow)
    node_2 = data_fixture.create_automation_node(workflow=workflow)

    order = AutomationNodeHandler().get_nodes_order(workflow)

    assert order == [trigger.id, node_1.id, node_2.id]


@pytest.mark.django_db
def test_order_nodes(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node_1 = data_fixture.create_automation_node(workflow=workflow)
    node_2 = data_fixture.create_automation_node(workflow=workflow)

    order = AutomationNodeHandler().get_nodes_order(workflow)
    assert order == [trigger.id, node_1.id, node_2.id]

    new_order = AutomationNodeHandler().order_nodes(
        workflow, [trigger.id, node_2.id, node_1.id]
    )
    assert new_order == [trigger.id, node_2.id, node_1.id]

    order = AutomationNodeHandler().get_nodes_order(workflow)
    assert order == [trigger.id, node_2.id, node_1.id]


@pytest.mark.django_db
def test_order_nodes_excludes_trashed_application(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow()
    node_1 = data_fixture.create_automation_node(workflow=workflow)
    node_2 = data_fixture.create_automation_node(workflow=workflow)
    automation = workflow.automation

    TrashHandler.trash(user, automation.workspace, automation, automation)

    with pytest.raises(AutomationNodeNotInWorkflow) as e:
        AutomationNodeHandler().order_nodes(workflow, [node_2.id, node_1.id])

    assert str(e.value) == f"The node {node_2.id} does not belong to the workflow."


@pytest.mark.django_db
def test_order_nodes_invalid_node(data_fixture):
    workflow_1 = data_fixture.create_automation_workflow()
    node_1 = data_fixture.create_automation_node(workflow=workflow_1)
    workflow_2 = data_fixture.create_automation_workflow()
    node_2 = data_fixture.create_automation_node(workflow=workflow_2)

    with pytest.raises(AutomationNodeNotInWorkflow) as e:
        AutomationNodeHandler().order_nodes(workflow_1, [node_2.id, node_1.id])

    assert str(e.value) == f"The node {node_2.id} does not belong to the workflow."


@pytest.mark.django_db
def test_duplicate_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    action1 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    action2 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    duplication = AutomationNodeHandler().duplicate_node(action1)
    action2.refresh_from_db()
    assert duplication.duplicated_node.previous_node_id == action1.id
    assert action2.previous_node_id == duplication.duplicated_node.id


@pytest.mark.django_db
def test_export_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node = data_fixture.create_automation_node(
        workflow=workflow,
    )

    result = AutomationNodeHandler().export_node(node)

    assert result == {
        "id": node.id,
        "label": node.label,
        "order": str(node.order),
        "parent_node_id": None,
        "previous_node_id": trigger.id,
        "previous_node_output": "",
        "service": AnyDict(),
        "type": "create_row",
        "workflow_id": node.workflow.id,
    }


@pytest.mark.django_db
def test_import_node(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node = data_fixture.create_automation_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }

    result = AutomationNodeHandler().import_node(workflow, exported_node, id_mapping)
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(result.automationnode_ptr)


@pytest.mark.django_db
def test_import_nodes(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node = data_fixture.create_automation_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }

    result = AutomationNodeHandler().import_nodes(workflow, [exported_node], id_mapping)
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(result[0].automationnode_ptr)


@pytest.mark.django_db
def test_import_node_only(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger(specific=False)
    node = data_fixture.create_automation_node(workflow=workflow)
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    new_node = AutomationNodeHandler().import_node_only(
        workflow, exported_node, id_mapping
    )
    assert workflow.automation_workflow_nodes.contains(trigger)
    assert workflow.automation_workflow_nodes.contains(node.automationnode_ptr)
    assert workflow.automation_workflow_nodes.contains(new_node.automationnode_ptr)

    assert id_mapping == {
        "integrations": MirrorDict(),
        "automation_edge_outputs": {},
        "automation_workflow_nodes": {node.id: new_node.id},
        "services": {node.service_id: new_node.service_id},
    }


@pytest.mark.django_db
@patch("baserow.contrib.automation.nodes.handler.AutomationWorkflowRunner.run")
def test_simulate_dispatch_node_trigger(mock_run, data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger_node = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow
    )
    assert workflow.simulate_until_node is None
    action_node = data_fixture.create_automation_node(
        workflow=workflow,
        type="create_row",
        previous_node_id=trigger_node.id,
    )

    # Set initial fake data for the action_node, since we want to test
    # that it is not affected.
    action_node.service.sample_data = {"foo": "bar"}
    action_node.service.save()

    AutomationNodeHandler().simulate_dispatch_node(trigger_node)

    mock_run.assert_not_called()

    workflow.refresh_from_db()
    assert workflow.simulate_until_node.id is trigger_node.id

    trigger_node.refresh_from_db()
    assert trigger_node.service.sample_data is None

    action_node.refresh_from_db()
    assert action_node.service.sample_data == {"foo": "bar"}


def create_action_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(user=user, automation=automation)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=automation
    )

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", "text")],
        rows=[],
    )
    action_service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
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

    return {
        "action_node": action_node,
        "table": table,
        "fields": fields,
        "user": user,
    }


@pytest.mark.django_db
def test_simulate_dispatch_node_action(data_fixture):
    data = create_action_node(data_fixture)
    action_node = data["action_node"]
    table = data["table"]
    fields = data["fields"]

    assert action_node.service.sample_data is None

    AutomationNodeHandler().simulate_dispatch_node(action_node)

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
@patch("baserow.core.services.registries.ServiceType.get_sample_data")
def test_simulate_dispatch_node_action_with_update_sample_data(
    mock_get_sample_data, data_fixture
):
    data = create_action_node(data_fixture)
    action_node = data["action_node"]
    fields = data["fields"]

    assert action_node.service.sample_data is None

    mock_get_sample_data.return_value = None

    AutomationNodeHandler().simulate_dispatch_node(action_node)

    action_node.refresh_from_db()

    assert action_node.service.sample_data == {
        "data": {
            f"field_{fields[0].id}": "A new row",
            "id": AnyInt(),
            "order": AnyStr(),
        },
        "output_uid": "",
        "status": 200,
    }


@pytest.mark.django_db
def test_simulate_dispatch_node_action_with_simulate_until_node(data_fixture):
    data = create_action_node(data_fixture)
    action_node_1 = data["action_node"]
    table = data["table"]
    fields = data["fields"]

    action_node_2 = data_fixture.create_automation_node(
        workflow=action_node_1.workflow,
        type="create_row",
    )

    action_node_3 = data_fixture.create_automation_node(
        workflow=action_node_1.workflow,
        type="create_row",
    )

    nodes = [action_node_1, action_node_2, action_node_3]
    for node in nodes:
        assert node.service.sample_data is None

    AutomationNodeHandler().simulate_dispatch_node(action_node_1)

    # Only the first action nodes dispatch should be simulated
    action_node_1.refresh_from_db()
    row = table.get_model().objects.first()
    assert action_node_1.service.sample_data == {
        "data": {
            f"field_{fields[0].id}": "A new row",
            "id": row.id,
            "order": str(row.order),
        },
        "output_uid": "",
        "status": 200,
    }

    # Due to the simulate_until_node param in the dispatch context, the
    # other nodes should not be dispatched.
    for node in [action_node_2, action_node_3]:
        node.refresh_from_db()
        assert node.service.sample_data is None


def create_action_node_service(data_fixture, user, automation, value):
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=automation
    )
    database = data_fixture.create_database_application(
        user=user, workspace=automation.workspace
    )
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Name", "text")],
        rows=[],
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    service.field_mappings.create(
        field=fields[0],
        value=f"'{value}'",
    )

    return service


@pytest.mark.django_db
def test_simulate_dispatch_node_dispatches_correct_edge_node(data_fixture):
    """
    Ensure that when simulating a dispatch for a node that is an edge,
    it is correctly dispatched.
    """

    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user, create_trigger=False)
    trigger_node = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow
    )

    router_a = data_fixture.create_core_router_action_node(
        workflow=workflow, previous_node_id=trigger_node.id
    )
    router_a_edge_1 = data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A, Edge 1",
        condition="'true'",
        skip_output_node=True,
    )
    router_a_edge_2 = data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A, Edge 2",
        condition="'false'",
        skip_output_node=True,
    )

    router_b = data_fixture.create_core_router_action_node(
        workflow=workflow,
        previous_node_id=router_a.id,
        previous_node_output=router_a_edge_1.uid,
    )
    router_b_edge_1 = data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B, Edge 1",
        condition="'false'",
        skip_output_node=True,
    )
    router_b_edge_2 = data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B, Edge 2",
        condition="'true'",
        skip_output_node=True,
    )

    node_b_service = create_action_node_service(
        data_fixture, user, workflow.automation, "apple"
    )
    node_b = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, service=node_b_service, previous_node_id=router_a.id
    )

    node_c_1_service = create_action_node_service(
        data_fixture, user, workflow.automation, "banana"
    )
    node_c_1 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, service=node_c_1_service, previous_node_id=router_b.id
    )
    node_c_2_service = create_action_node_service(
        data_fixture, user, workflow.automation, "cherry"
    )
    node_c_2 = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=node_c_2_service,
        previous_node_id=router_b.id,
        previous_node_output=router_b_edge_2.uid,
    )

    nodes = [trigger_node, router_a, router_b, node_b, node_c_1, node_c_2]
    for node in nodes:
        assert node.service.sample_data is None

    AutomationNodeHandler().simulate_dispatch_node(node_c_2)

    # node_c_2 is intentionally excluded. here
    nodes = [trigger_node, router_a, router_b, node_b, node_c_1]
    for node in nodes:
        node.service.refresh_from_db()
        assert node.service.sample_data is None

    node_c_2.refresh_from_db()
    node_c_2.service.refresh_from_db()
    field_id = node_c_2.service.specific.table.field_set.all()[0].id
    assert node_c_2.service.sample_data == {
        "data": {f"field_{field_id}": "cherry", "id": AnyInt(), "order": AnyStr()},
        "output_uid": AnyStr(),
        "status": 200,
    }
