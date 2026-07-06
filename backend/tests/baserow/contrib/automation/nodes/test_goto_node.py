import pytest

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def _build_goto_workflow(data_fixture, condition="'false'", with_destination=True):
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
    service.condition = condition
    if with_destination:
        service.destination_service = destination.service
    service.save()

    return {
        "user": user,
        "workflow": workflow,
        "trigger": trigger,
        "destination": destination,
        "goto_node": goto_node,
    }


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_trigger_destination(data_fixture):
    data = _build_goto_workflow(data_fixture)
    goto_node = data["goto_node"]
    trigger = data["trigger"]

    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": trigger.service_id}},
            data["user"],
            instance=goto_node,
        )


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_cross_level_destination(data_fixture):
    iterator_data = data_fixture.iterator_graph_fixture()
    workflow = iterator_data["workflow"]
    trigger = iterator_data["trigger_node"]
    iterator_child = iterator_data["iterator_child_1_node"]

    user = data_fixture.create_user()
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=trigger, position="south", output=""
    )

    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": iterator_child.service_id}},
            user,
            instance=goto_node,
        )


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_cross_workflow_destination(data_fixture):
    data = _build_goto_workflow(data_fixture)
    goto_node = data["goto_node"]

    # A destination node belonging to a different workflow is not eligible.
    other_workflow = data_fixture.create_automation_workflow(user=data["user"])
    other_destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=other_workflow,
        reference_node=other_workflow.get_trigger(),
        label="other workflow destination",
    )

    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": other_destination.service_id}},
            data["user"],
            instance=goto_node,
        )


@pytest.mark.django_db
def test_goto_node_prepare_values_allows_same_level_destination(data_fixture):
    data = _build_goto_workflow(data_fixture)
    goto_node = data["goto_node"]
    destination = data["destination"]

    values = goto_node.get_type().prepare_values(
        {"service": {"destination_service_id": destination.service_id}},
        data["user"],
        instance=goto_node,
    )
    assert values["service"].destination_service_id == destination.service_id


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_forward_jump(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()

    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=trigger, position="south", output=""
    )
    # A node placed after the Go to node would be a forward jump: it has not run
    # yet when the Go to node is reached, so jumping to it would skip nothing but
    # would leave the nodes between unexecuted.
    forward_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=goto_node, label="forward", position="south"
    )

    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": forward_node.service_id}},
            user,
            instance=goto_node,
        )


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_cross_branch_destination(data_fixture):
    # A node in one router branch cannot jump to a node in a sibling branch:
    # that node never runs before the Go to node, so it's a forward jump. The
    # two branches share the same level, so the same-level rule alone wouldn't
    # catch this - the backward-jump rule does.
    user = data_fixture.create_user()
    router_data = data_fixture.create_core_router_action_node_with_edges(user=user)
    workflow = router_data.router.workflow
    branch_a_node = router_data.edge1_output
    branch_b_node = router_data.edge2_output

    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=branch_a_node, position="south", output=""
    )

    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": branch_b_node.service_id}},
            user,
            instance=goto_node,
        )

    # ...but jumping back to an earlier node in its own branch is allowed.
    values = goto_node.get_type().prepare_values(
        {"service": {"destination_service_id": branch_a_node.service_id}},
        user,
        instance=goto_node,
    )
    assert values["service"].destination_service_id == branch_a_node.service_id


@pytest.mark.django_db
def test_goto_node_prepare_values_rejects_self_target(data_fixture):
    data = _build_goto_workflow(data_fixture)
    goto_node = data["goto_node"]

    # Self-targeting is rejected: an empty loop body re-evaluates the same condition
    # against unchanged state, so it can only be a no-op or a guaranteed infinite loop.
    with pytest.raises(AutomationNodeMisconfiguredService):
        goto_node.get_type().prepare_values(
            {"service": {"destination_service_id": goto_node.service_id}},
            data["user"],
            instance=goto_node,
        )


@pytest.mark.django_db
def test_dispatch_node_jumps_to_destination_when_condition_true(data_fixture):
    data = _build_goto_workflow(data_fixture, condition="'true'")
    workflow = data["workflow"]
    goto_node = data["goto_node"]
    destination = data["destination"]

    history = data_fixture.create_automation_workflow_history(
        workflow=workflow.get_original(),
        event_payload={"results": [], "has_next_page": False},
    )

    result = AutomationNodeHandler().dispatch_node(goto_node.id, history.id)

    # The runner should redirect to the destination node rather than the natural
    # next node (there is none after the goto node).
    assert result is not None
    leaf = result.tasks[0]
    if hasattr(leaf, "tasks"):
        leaf = leaf.tasks[0]
    assert leaf.args[0] == destination.id


@pytest.mark.django_db
def test_dispatch_node_falls_through_when_condition_false(data_fixture):
    data = _build_goto_workflow(data_fixture, condition="'false'")
    workflow = data["workflow"]
    goto_node = data["goto_node"]

    history = data_fixture.create_automation_workflow_history(
        workflow=workflow.get_original(),
        event_payload={"results": [], "has_next_page": False},
    )

    # The goto node is the last node in the graph, so falling through ends the branch.
    result = AutomationNodeHandler().dispatch_node(goto_node.id, history.id)
    assert result is None


@pytest.mark.django_db
def test_goto_node_dispatch_skips_jump_when_simulating(data_fixture):
    # The node type owns the simulation gate: while simulating, the jump is never
    # followed (it would loop the simulated path), so no destination is emitted.
    data = _build_goto_workflow(data_fixture, condition="'true'")
    goto_node = data["goto_node"]

    dispatch_context = FakeDispatchContext(simulate_until_node=goto_node)
    dispatch_result = goto_node.get_type().dispatch(goto_node, dispatch_context)

    assert dispatch_result.output_service_id is None


@pytest.mark.django_db
def test_goto_node_dispatch_rejects_cross_level_destination(data_fixture):
    """
    When the destination has been moved into a container (becomes cross-level)
    after being configured, the node type's dispatch-time guard should raise a
    clean misconfigured error rather than a 500/KeyError.
    """

    data = data_fixture.iterator_graph_fixture()
    workflow = data["workflow"]
    iterator_child = data["iterator_child_1_node"]
    trigger = data["trigger_node"]

    # The goto node sits at the root level (right after the trigger)...
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=trigger, position="south", output=""
    )
    service = goto_node.service.specific
    service.condition = "'true'"
    # ...but the destination lives inside the iterator (a different level).
    service.destination_service = iterator_child.service
    service.save()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        goto_node.get_type().dispatch(goto_node, FakeDispatchContext())
