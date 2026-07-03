from collections import defaultdict

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.utils import MirrorDict
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_create_core_goto_node_service(data_fixture):
    user = data_fixture.create_user()
    service_type = service_type_registry.get("goto")
    values = service_type.prepare_values({"condition": "'true'"}, user)
    service = ServiceHandler().create_service(service_type, **values)
    assert service.condition["formula"] == "'true'"
    assert service.destination_node_id is None


@pytest.mark.django_db
def test_update_core_goto_node_service_sets_destination(data_fixture):
    user = data_fixture.create_user()
    goto_node = data_fixture.create_core_goto_node(user=user)
    workflow = goto_node.workflow
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=goto_node, label="destination"
    )

    service = goto_node.service.specific
    service_type = service.get_type()
    values = service_type.prepare_values(
        {"condition": "'true'", "destination_node_id": destination.id}, user
    )
    result = ServiceHandler().update_service(service_type, service, **values)

    assert result.service.destination_node_id == destination.id


@pytest.mark.django_db
@pytest.mark.parametrize("truthful_condition", ["'true'", "1", "'yes'"])
def test_core_goto_node_dispatch_condition_true(data_fixture, truthful_condition):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    # The destination must run before the Go to node (a backward jump), so it is
    # placed between the trigger and the Go to node.
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger, position="south", label="destination"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination, position="south"
    )

    service = goto_node.service.specific
    service.condition = truthful_condition
    service.destination_node = destination
    service.save()

    dispatch_result = service.get_type().dispatch(service, FakeDispatchContext())

    assert dispatch_result.output_node_id == destination.id
    assert dispatch_result.data == {"condition": True}


@pytest.mark.django_db
def test_core_goto_node_dispatch_condition_false(data_fixture):
    user = data_fixture.create_user()
    goto_node = data_fixture.create_core_goto_node(user=user)
    workflow = goto_node.workflow
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=goto_node, label="destination"
    )

    service = goto_node.service.specific
    service.condition = "'false'"
    service.destination_node = destination
    service.save()

    dispatch_result = service.get_type().dispatch(service, FakeDispatchContext())

    assert dispatch_result.output_node_id is None
    assert dispatch_result.data == {"condition": False}


@pytest.mark.django_db
@pytest.mark.parametrize("empty_condition", ["", None])
def test_core_goto_node_dispatch_empty_condition_jumps(data_fixture, empty_condition):
    """
    An unset condition means the jump is unconditional, so it is followed even
    though the condition resolves to a falsy value. This is what distinguishes
    it from an explicitly configured condition that resolves to false.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    # The destination must run before the Go to node (a backward jump), so it is
    # placed between the trigger and the Go to node.
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger, position="south", label="destination"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination, position="south"
    )

    service = goto_node.service.specific
    service.condition = empty_condition
    service.destination_node = destination
    service.save()

    dispatch_result = service.get_type().dispatch(service, FakeDispatchContext())

    assert dispatch_result.output_node_id == destination.id
    assert dispatch_result.data == {"condition": True}


@pytest.mark.django_db
def test_core_goto_node_dispatch_missing_destination_raises(data_fixture):
    user = data_fixture.create_user()
    goto_node = data_fixture.create_core_goto_node(user=user)
    service = goto_node.service.specific
    service.condition = "'true'"
    service.save()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service.get_type().dispatch(service, FakeDispatchContext())


@pytest.mark.django_db
def test_core_goto_node_generate_schema(data_fixture):
    service = data_fixture.create_core_goto_service()
    assert service.get_type().generate_schema(service) == {
        "title": f"CoreGoto{service.id}Schema",
        "type": "object",
        "properties": {
            "condition": {
                "type": "boolean",
                "title": "Condition",
                "description": "Whether the condition evaluated to true and the "
                "jump was followed.",
            }
        },
    }


@pytest.mark.django_db
def test_core_goto_node_destination_set_null_on_delete(data_fixture):
    user = data_fixture.create_user()
    goto_node = data_fixture.create_core_goto_node(user=user)
    workflow = goto_node.workflow
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=goto_node, label="destination"
    )

    service = goto_node.service.specific
    service.destination_node = destination
    service.save()

    # A hard delete of the destination node should null the FK (on_delete=SET_NULL).
    destination.delete()

    service.refresh_from_db()
    assert service.destination_node_id is None


@pytest.mark.django_db
def test_core_goto_node_import_export_remaps_destination(data_fixture):
    """
    Exporting then importing the workflow's nodes should remap the goto node's
    `destination_node` reference to the newly-imported destination node id.
    """

    user = data_fixture.create_user()
    source_workflow = data_fixture.create_automation_workflow(user=user)
    trigger = source_workflow.get_trigger()

    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=source_workflow, reference_node=trigger, label="destination"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=source_workflow, reference_node=destination
    )
    service = goto_node.service.specific
    service.condition = "'true'"
    service.destination_node = destination
    service.save()

    handler = AutomationNodeHandler()
    serialized_destination = handler.export_node(destination)
    serialized_goto = handler.export_node(goto_node)

    target_workflow = data_fixture.create_automation_workflow(user=user)
    id_mapping = defaultdict(MirrorDict)
    id_mapping["automation_workflow_nodes"] = {}

    imported_destination, imported_goto = handler.import_nodes(
        target_workflow,
        [serialized_destination, serialized_goto],
        id_mapping,
    )

    assert imported_goto.service.specific.destination_node_id == imported_destination.id
    assert imported_goto.service.specific.destination_node_id != destination.id


@pytest.mark.django_db
def test_core_goto_node_single_node_duplicate_keeps_destination(data_fixture):
    """
    A single-node duplicate copies only the Go to node and leaves the
    destination node in place, so the import (seeded with a MirrorDict node
    mapping) should carry the original destination over unchanged.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()

    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger, label="destination"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination
    )
    service = goto_node.service.specific
    service.condition = "'true'"
    service.destination_node = destination
    service.save()

    handler = AutomationNodeHandler()
    serialized_goto = handler.export_node(goto_node)

    # A single-node duplicate seeds the node mapping with a MirrorDict.
    id_mapping = defaultdict(MirrorDict)
    id_mapping["automation_workflow_nodes"] = MirrorDict()

    imported_goto = handler.import_node(workflow, serialized_goto, id_mapping)

    assert imported_goto.service.specific.destination_node_id == destination.id
