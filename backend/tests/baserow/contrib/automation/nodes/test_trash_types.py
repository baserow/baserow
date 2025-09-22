import pytest

from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_trashing_and_restoring_node_updates_next_node_values(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    initial_router_service = data_fixture.create_core_router_service()
    initial_router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=initial_router_service
    )
    second_router_service = data_fixture.create_core_router_service()
    second_router = data_fixture.create_core_router_action_node(
        workflow=workflow, service=second_router_service
    )
    initial_router_edge = data_fixture.create_core_router_service_edge(
        label="To second router",
        condition="'true'",
        service=initial_router_service,
        output_node=second_router,
    )
    second_router.previous_node_output = str(initial_router_edge.uid)
    second_router.save()
    second_router_edge = data_fixture.create_core_router_service_edge(
        label="To create row",
        condition="'true'",
        service=second_router_service,
    )
    second_router_edge_output_node = workflow.automation_workflow_nodes.get(
        previous_node_output=second_router_edge.uid
    )

    assert trigger.previous_node_id is None
    assert trigger.previous_node_output == ""

    assert initial_router.previous_node_id == trigger.id
    assert initial_router.previous_node_output == ""

    assert second_router.previous_node_id == initial_router.id
    assert second_router.previous_node_output == str(initial_router_edge.uid)

    assert second_router_edge_output_node.previous_node_id == second_router.id
    assert second_router_edge_output_node.previous_node_output == str(
        second_router_edge.uid
    )

    automation = workflow.automation
    trash_entry = TrashHandler.trash(
        user, automation.workspace, automation, second_router
    )
    assert trash_entry.additional_restoration_data == {
        second_router_edge_output_node.id: {
            "previous_node_output": str(second_router_edge.uid)
        }
    }

    second_router_edge_output_node.refresh_from_db()

    # We've trashed the second router, so that *output node* of
    # the second router becomes the output node of the first router.
    assert second_router_edge_output_node.previous_node_id == initial_router.id
    assert second_router_edge_output_node.previous_node_output == str(
        initial_router_edge.uid
    )

    TrashHandler.restore_item(
        user,
        AutomationNodeTrashableItemType.type,
        second_router.id,
    )

    second_router.refresh_from_db()
    assert second_router.previous_node_id == initial_router.id
    assert second_router.previous_node_output == str(initial_router_edge.uid)

    second_router_edge_output_node.refresh_from_db()
    assert second_router_edge_output_node.previous_node_id == second_router.id
    assert second_router_edge_output_node.previous_node_output == str(
        second_router_edge.uid
    )


@pytest.mark.django_db
def test_restoring_a_trashed_output_node_after_its_edge_is_destroyed_is_disallowed(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(workflow=workflow)
    service = data_fixture.create_core_router_service()
    data_fixture.create_core_router_action_node(service=service, workflow=workflow)
    edge = data_fixture.create_core_router_service_edge(
        service=service, label="Edge 1", condition="'false'"
    )
    output_node = workflow.automation_workflow_nodes.get(previous_node_output=edge.uid)

    automation = workflow.automation
    TrashHandler.trash(user, automation.workspace, automation, output_node)

    edge.delete()

    with pytest.raises(TrashItemRestorationDisallowed) as exc:
        TrashHandler.restore_item(
            user,
            AutomationNodeTrashableItemType.type,
            output_node.id,
        )
    assert (
        exc.value.args[0] == "This automation node cannot "
        "be restored as its branch has been deleted."
    )
