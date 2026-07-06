import uuid

import pytest

from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import MoveAutomationNodeActionType
from baserow.contrib.automation.nodes.node_types import CoreGotoActionNodeType
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.integrations.core.models import CoreGotoService
from baserow.core.action.handler import ActionHandler


def _root_goto_workflow(data_fixture, user=None):
    """
    Builds a workflow whose root level is:
        trigger -> destination -> iterator -> goto (destination_service=destination.service)
    """

    user = user or data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    destination = data_fixture.create_automation_node(
        workflow=workflow, label="destination"
    )
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow, label="iterator"
    )
    goto = data_fixture.create_core_goto_node(workflow=workflow, label="goto")

    service = goto.service.specific
    service.condition = "'true'"
    service.destination_service = destination.service
    service.save()

    # Sanity check: same root level, so the link is valid to begin with.
    assert CoreGotoActionNodeType.validate_goto_destination(goto, destination) is None

    return {
        "user": user,
        "workflow": workflow,
        "trigger": trigger,
        "destination": destination,
        "iterator": iterator,
        "goto": goto,
        "service": service,
    }


@pytest.mark.django_db
def test_move_destination_into_container_clears_goto_link(data_fixture):
    data = _root_goto_workflow(data_fixture)

    # Moving the destination inside the iterator breaks the same-level rule.
    AutomationNodeService().move_node(
        data["user"], data["destination"].id, data["iterator"].id, "child", ""
    )

    data["service"].refresh_from_db()
    assert data["service"].destination_service_id is None


@pytest.mark.django_db
def test_move_goto_into_container_clears_goto_link(data_fixture):
    data = _root_goto_workflow(data_fixture)

    # Moving the goto node itself inside the iterator breaks the rule too.
    AutomationNodeService().move_node(
        data["user"], data["goto"].id, data["iterator"].id, "child", ""
    )

    data["service"].refresh_from_db()
    assert data["service"].destination_service_id is None


@pytest.mark.django_db
def test_move_goto_before_destination_keeps_goto_link(data_fixture):
    data = _root_goto_workflow(data_fixture)

    # Moving the goto node before its destination turns the backward jump into a
    # forward jump (trigger -> goto -> destination -> iterator). Forward jumps are
    # valid - the destination is still on the goto's path - so the link survives.
    AutomationNodeService().move_node(
        data["user"], data["goto"].id, data["trigger"].id, "south", ""
    )

    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id


@pytest.mark.django_db
def test_move_unrelated_node_keeps_goto_link(data_fixture):
    data = _root_goto_workflow(data_fixture)
    other = data_fixture.create_automation_node(
        workflow=data["workflow"], label="other"
    )

    # A reorder that doesn't change either endpoint's level leaves the link be.
    AutomationNodeService().move_node(
        data["user"], other.id, data["trigger"].id, "south", ""
    )

    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id


@pytest.mark.django_db
def test_move_container_holding_both_endpoints_keeps_goto_link(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    workflow.get_trigger()
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow, label="iterator"
    )
    after = data_fixture.create_automation_node(workflow=workflow, label="after")

    # Both endpoints live inside the iterator, at the same level as each other.
    destination = data_fixture.create_automation_node(
        workflow=workflow,
        label="destination",
        reference_node=iterator,
        position="child",
    )
    goto = data_fixture.create_core_goto_node(
        workflow=workflow, label="goto", reference_node=destination, position="south"
    )
    service = goto.service.specific
    service.destination_service = destination.service
    service.save()
    assert CoreGotoActionNodeType.validate_goto_destination(goto, destination) is None

    # Moving the whole container carries both endpoints together, so their
    # relative level is unchanged and the link must survive.
    AutomationNodeService().move_node(user, iterator.id, after.id, "south", "")

    service.refresh_from_db()
    assert service.destination_service_id == destination.service_id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_redo_move_restores_and_reclears_goto_link(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    data = _root_goto_workflow(data_fixture, user=user)
    workflow = data["workflow"]
    scope = WorkflowActionScopeType.value(workflow.id)

    MoveAutomationNodeActionType.do(
        user, data["destination"].id, data["iterator"].id, "child", ""
    )
    data["service"].refresh_from_db()
    assert data["service"].destination_service_id is None

    # Undo returns the destination to the root, so the link is restored.
    ActionHandler.undo(user, [scope], session_id)
    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id

    # Redo breaks it again.
    ActionHandler.redo(user, [scope], session_id)
    data["service"].refresh_from_db()
    assert data["service"].destination_service_id is None


@pytest.mark.django_db
def test_duplicate_goto_node_copies_its_destination(data_fixture):
    data = _root_goto_workflow(data_fixture)

    duplicated = AutomationNodeService().duplicate_node(data["user"], data["goto"].id)

    # A single-node duplicate leaves the destination node in place, so the copy
    # keeps jumping to the same destination as the original.
    duplicated_service = duplicated.service.specific
    assert duplicated_service.destination_service_id == data["destination"].service_id
    # The original link is untouched.
    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id


@pytest.mark.django_db
def test_duplicate_destination_node_is_not_referenced_by_any_goto(data_fixture):
    data = _root_goto_workflow(data_fixture)

    duplicated_destination = AutomationNodeService().duplicate_node(
        data["user"], data["destination"].id
    )

    # The copy is a standalone node: no goto points at it, and the original
    # link is untouched.
    assert not CoreGotoService.objects.filter(
        destination_service=duplicated_destination.service
    ).exists()
    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id


@pytest.mark.django_db
def test_deleting_destination_preserves_link_for_restore(data_fixture):
    data = _root_goto_workflow(data_fixture)

    # Deleting trashes the node (soft delete), which must NOT fire SET_NULL, so
    # the link survives and an undo/restore brings the jump back.
    AutomationNodeService().delete_node(data["user"], data["destination"].id)

    data["service"].refresh_from_db()
    assert data["service"].destination_service_id == data["destination"].service_id
