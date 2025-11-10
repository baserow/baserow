import pytest

from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_trashing_and_restoring_node_updates_graph(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    first = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="first action"
    )
    second = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="second action"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "first action": {"next": {"": ["second action"]}},
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "second action": {},
        }
    )

    automation = workflow.automation
    trash_entry = TrashHandler.trash(user, automation.workspace, automation, first)

    assert trash_entry.additional_restoration_data == (
        str(trigger.id),
        "south",
        "",
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["second action"]}},
            "second action": {},
        }
    )

    TrashHandler.restore_item(
        user,
        AutomationNodeTrashableItemType.type,
        first.id,
    )
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "first action": {"next": {"": ["second action"]}},
            "local_baserow_rows_created": {"next": {"": ["first action"]}},
            "second action": {},
        }
    )


@pytest.mark.django_db
def test_trashing_and_restoring_node_updates_graph_with_router(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    initial_router = data_fixture.create_core_router_action_node(
        workflow=workflow,
        label="First router",
    )
    initial_router_edge = data_fixture.create_core_router_service_edge(
        label="To second router",
        condition="'true'",
        service=initial_router.service,
        skip_output_node=True,
    )

    # Second router
    second_router = data_fixture.create_core_router_action_node(
        workflow=workflow,
        label="Second router",
        reference_node=initial_router,
        position="south",
        output=initial_router_edge.uid,
    )

    second_router_edge = data_fixture.create_core_router_service_edge(
        label="To create row",
        condition="'true'",
        service=second_router.service,
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["First router"]}},
            "First router": {"next": {"To second router": ["Second router"]}},
            "Second router": {"next": {"To create row": ["To create row output node"]}},
            "To create row output node": {},
        }
    )

    automation = workflow.automation

    trash_entry = TrashHandler.trash(
        user, automation.workspace, automation, second_router
    )

    assert trash_entry.additional_restoration_data == (
        str(initial_router.id),
        "south",
        str(initial_router_edge.uid),
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["First router"]}},
            "First router": {
                "next": {"To second router": ["To create row output node"]}
            },
            "To create row output node": {},
        }
    )

    TrashHandler.restore_item(
        user,
        AutomationNodeTrashableItemType.type,
        second_router.id,
    )
    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "First router": {"next": {"To second router": ["Second router"]}},
            "Second router": {"next": {"": ["To create row output node"]}},
            "To create row output node": {},
            "local_baserow_rows_created": {"next": {"": ["First router"]}},
        }
    )


@pytest.mark.django_db
def test_restoring_a_trashed_output_node_after_its_edge_is_destroyed_is_disallowed(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    router = data_fixture.create_core_router_action_node(workflow=workflow)

    edge = data_fixture.create_core_router_service_edge(
        service=router.service, label="Edge 1", condition="'false'"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {"next": {"Edge 1": ["Edge 1 output node"]}},
            "Edge 1 output node": {},
        }
    )

    output_node = workflow.get_graph().get_node_at_position(
        router, "south", str(edge.uid)
    )

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
