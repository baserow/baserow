import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
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

    assert trash_entry.additional_restoration_data == {
        "position": [str(trigger.id), "south", ""],
        "hierarchical_parent_id": None,
        "children": [],
    }

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

    assert trash_entry.additional_restoration_data == {
        "position": [str(initial_router.id), "south", str(initial_router_edge.uid)],
        "hierarchical_parent_id": None,
        "children": [],
    }

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

    output_node = workflow.get_graph().get_point_at_position(
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


@pytest.mark.django_db
def test_restoring_node_whose_reference_is_still_trashed_is_disallowed(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    first = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="first action"
    )
    second = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, label="second action"
    )

    automation = workflow.automation

    # Trash the second node first (its reference is the first node), then trash the
    # first node too. Both have their own trash entry.
    TrashHandler.trash(user, automation.workspace, automation, second)
    TrashHandler.trash(user, automation.workspace, automation, first)

    # The second node cannot be restored while its reference node is still trashed.
    # The message names the node that must be restored first rather than misleadingly
    # claiming the reference was deleted.
    with pytest.raises(TrashItemRestorationDisallowed) as exc:
        TrashHandler.restore_item(
            user,
            AutomationNodeTrashableItemType.type,
            second.id,
        )

    assert exc.value.args[0] == (
        f"This record cannot be restored until {first} ({first.id}) is restored first."
    )

    second.refresh_from_db()
    assert second.trashed is True

    # Once the reference node is restored, the second node can be restored too.
    TrashHandler.restore_item(user, AutomationNodeTrashableItemType.type, first.id)
    TrashHandler.restore_item(user, AutomationNodeTrashableItemType.type, second.id)

    second.refresh_from_db()
    first.refresh_from_db()
    assert second.trashed is False
    assert first.trashed is False


@pytest.mark.django_db
def test_trashing_container_node_cascades_children_and_restore_brings_them_back(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow, label="iterator"
    )
    child = data_fixture.create_automation_node(
        workflow=workflow, label="child", reference_node=iterator, position="child"
    )

    automation = workflow.automation
    trash_entry = TrashHandler.trash(user, automation.workspace, automation, iterator)

    # Container is trashed; the child is soft-deleted alongside it (cascade).
    iterator.refresh_from_db()
    assert iterator.trashed is True
    assert not AutomationNode.objects.filter(id=child.id).exists()
    assert AutomationNode.trash.filter(id=child.id).exists()

    # Restoration data records the child so it can be restored with the container.
    child_ids = [row[0] for row in trash_entry.additional_restoration_data["children"]]
    assert child.id in child_ids

    # Restore brings the container and its child back into the graph.
    TrashHandler.restore_item(user, AutomationNodeTrashableItemType.type, iterator.id)

    iterator.refresh_from_db()
    child.refresh_from_db()
    assert iterator.trashed is False
    assert child.trashed is False

    workflow.refresh_from_db(fields=["graph"])
    assert str(iterator.id) in workflow.graph
    assert str(child.id) in workflow.graph
