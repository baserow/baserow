import pytest

from baserow.contrib.automation.nodes.constants import ERROR_POLICY_FIELDS
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import LocalBaserowRowsCreatedTriggerNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.local_baserow.models import LocalBaserowRowsCreated
from baserow.core.cache import local_cache
from baserow.core.constants import NOTE_MAX_LEN
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
def test_workflow_point_map_is_invalidated_after_node_creation(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(create_trigger=False)
    node_type = automation_node_type_registry.get("local_baserow_rows_created")

    with local_cache.context():
        graph = workflow.get_graph()
        with pytest.raises(AutomationNodeDoesNotExist):
            graph.get_point(0)
        node = AutomationNodeHandler().create_node(
            node_type, **node_type.prepare_values({"workflow": workflow}, user)
        )
        assert graph.get_point(node.id) == node


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
        "note": "",
        "on_failure": "stop",
        "max_retries": 2,
        "retry_condition": {"formula": "", "mode": "simple", "version": "0.1"},
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
        "note": "",
        "on_failure": "stop",
        "max_retries": 2,
        "retry_condition": {"formula": "", "mode": "simple", "version": "0.1"},
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


@pytest.mark.django_db
def test_import_node_only_ignores_integration_from_another_application(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    other_integration = data_fixture.create_local_baserow_integration()

    exported_node = AutomationNodeHandler().export_node(trigger)
    exported_node["service"]["integration_id"] = other_integration.id
    id_mapping = {
        "integrations": {},
        "automation_workflow_nodes": MirrorDict(),
    }

    imported_node = AutomationNodeHandler().import_node_only(
        workflow, exported_node, id_mapping
    )

    assert imported_node.service.specific.integration_id is None


@pytest.mark.django_db
def test_update_node_error_policy(data_fixture):
    node = data_fixture.create_automation_node()

    updated_node = AutomationNodeHandler().update_node(
        node,
        on_failure="retry",
        max_retries=5,
        retry_condition="get('current_node.status_code') = 429",
    )

    assert updated_node.on_failure == "retry"
    node.refresh_from_db()
    assert node.on_failure == "retry"
    assert node.max_retries == 5
    assert node.retry_condition["formula"] == "get('current_node.status_code') = 429"


@pytest.mark.django_db
def test_update_node_ignores_error_policy_on_triggers(data_fixture):
    """
    The node type decides what can be updated: a trigger does not list the
    error policy fields, so they are dropped.
    """

    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()

    updated_node = AutomationNodeHandler().update_node(
        trigger, label="Rows", on_failure="retry", max_retries=5
    )

    assert updated_node.label == "Rows"
    trigger.refresh_from_db()
    assert trigger.label == "Rows"
    assert trigger.on_failure == "stop"
    assert trigger.max_retries == 2


@pytest.mark.parametrize(
    "node_type", ["wait", "iterator", "router", "goto", "response"]
)
def test_action_nodes_that_cannot_benefit_from_a_retry_have_no_error_policy(
    node_type,
):
    """
    These nodes only fail on values computed from the data of earlier nodes,
    which a retry evaluates the same way, so they do not accept the error policy
    fields and the update drops them, like for a trigger.
    """

    automation_node_type = automation_node_type_registry.get(node_type)

    assert automation_node_type.is_workflow_action
    assert not automation_node_type.has_error_policy
    assert not set(ERROR_POLICY_FIELDS) & set(automation_node_type.allowed_fields)


@pytest.mark.parametrize(
    "node_type", ["http_request", "local_baserow_create_row", "smtp_email"]
)
def test_action_nodes_that_can_fail_transiently_have_an_error_policy(node_type):
    automation_node_type = automation_node_type_registry.get(node_type)

    assert automation_node_type.has_error_policy
    assert set(ERROR_POLICY_FIELDS) <= set(automation_node_type.allowed_fields)


@pytest.mark.django_db
def test_import_node_keeps_the_error_policy(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    retry_condition = {
        "formula": "get('current_node.id') = 1",
        "mode": "advanced",
        "version": "0.1",
    }
    node = data_fixture.create_automation_node(
        workflow=workflow,
        on_failure="retry",
        max_retries=4,
        retry_condition=retry_condition,
    )

    exported_node = AutomationNodeHandler().export_node(node)
    assert exported_node["on_failure"] == "retry"
    assert exported_node["max_retries"] == 4
    assert exported_node["retry_condition"] == retry_condition

    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    imported_node = AutomationNodeHandler().import_node(
        workflow, exported_node, id_mapping
    )

    assert imported_node.id != node.id
    imported_node.refresh_from_db()
    assert imported_node.on_failure == "retry"
    assert imported_node.max_retries == 4
    assert imported_node.retry_condition == retry_condition


@pytest.mark.django_db
def test_import_node_remaps_the_retry_condition(data_fixture):
    """
    The condition reads the node's own result through `current_node`, whose
    path carries no node id: its field ids are remapped against the imported
    node's service.
    """

    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_automation_node(
        workflow=workflow,
        on_failure="retry",
        retry_condition="get('current_node.field_1') = 'done'",
    )

    exported_node = AutomationNodeHandler().export_node(node)
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
        "database_fields": {1: 2},
    }
    imported_node = AutomationNodeHandler().import_nodes(
        workflow, [exported_node], id_mapping
    )[0]

    imported_node.refresh_from_db()
    assert "current_node.field_2" in imported_node.retry_condition["formula"]
    assert "field_1" not in imported_node.retry_condition["formula"]

    # The source node is left as it was.
    node.refresh_from_db()
    assert "current_node.field_1" in node.retry_condition["formula"]


@pytest.mark.django_db
def test_duplicate_node_keeps_the_error_policy(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        label="test",
        on_failure="retry",
        max_retries=3,
        retry_condition="get('current_node.id') = 1",
    )

    duplicated_node = AutomationNodeHandler().duplicate_node(action)

    assert duplicated_node.id != action.id
    assert duplicated_node.on_failure == "retry"
    assert duplicated_node.max_retries == 3
    assert "current_node.id" in duplicated_node.retry_condition["formula"]


@pytest.mark.django_db
def test_update_node_note(data_fixture):
    node = data_fixture.create_automation_node()

    assert node.note == ""

    updated_node = AutomationNodeHandler().update_node(node, note="Why **this** step")

    updated_node.refresh_from_db()
    assert updated_node.note == "Why **this** step"


@pytest.mark.django_db
def test_export_and_import_node_keeps_the_note(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, note="Creates the invoice row"
    )

    exported = AutomationNodeHandler().export_node(node)
    assert exported["note"] == "Creates the invoice row"

    target_workflow = data_fixture.create_automation_workflow(
        automation=workflow.automation
    )
    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    imported = AutomationNodeHandler().import_node(
        target_workflow, exported, id_mapping
    )

    assert imported.note == "Creates the invoice row"


@pytest.mark.django_db
def test_import_node_without_a_note(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)

    exported = AutomationNodeHandler().export_node(node)
    del exported["note"]

    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    imported = AutomationNodeHandler().import_node(workflow, exported, id_mapping)

    assert imported.note == ""


@pytest.mark.django_db
def test_duplicate_node_keeps_the_note(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, note="Creates the invoice row"
    )

    duplicated_node = AutomationNodeHandler().duplicate_node(action)

    assert duplicated_node.id != action.id
    assert duplicated_node.note == "Creates the invoice row"


@pytest.mark.django_db
def test_import_node_cuts_a_note_that_is_too_long(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)

    exported = AutomationNodeHandler().export_node(node)
    exported["note"] = "a" * (NOTE_MAX_LEN + 50)

    id_mapping = {
        "integrations": MirrorDict(),
        "automation_workflow_nodes": MirrorDict(),
    }
    imported = AutomationNodeHandler().import_node(workflow, exported, id_mapping)

    assert imported.note == "a" * NOTE_MAX_LEN
