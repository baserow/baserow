import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowRowCreatedTriggerNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry


@pytest.mark.django_db
def test_create_node(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)

    node_type = automation_node_type_registry.get("row_created")
    prepared_values = node_type.prepare_values({}, user)

    node = AutomationNodeHandler().create_node(
        user, node_type, workflow=workflow, **prepared_values
    )

    assert isinstance(node, LocalBaserowRowCreatedTriggerNode)


@pytest.mark.django_db
def test_nodes(data_fixture):
    node = data_fixture.create_automation_node()

    nodes_qs = AutomationNodeHandler().get_nodes(node.workflow)

    assert [n.id for n in nodes_qs.all()] == [node.id]
