import pytest

from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import CreateAutomationNodeActionType
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.core.action.handler import ActionHandler


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_automation_node(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workflow = data_fixture.create_automation_workflow(user=user)
    # order: trigger -> first_action -> second_action
    trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow,
    )
    assert trigger.previous_node_id is None
    first_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    assert first_action.previous_node_id == trigger.id
    second_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    assert second_action.previous_node_id == first_action.id

    # Test `do`
    new_node = CreateAutomationNodeActionType().do(
        user,
        LocalBaserowRowsCreatedNodeTriggerType(),
        workflow,
        {"before_id": second_action.id},
    )

    # order: trigger -> first_action -> new_node -> second_action
    assert new_node.previous_node_id == first_action.id
    second_action.refresh_from_db(fields=["previous_node_id"])
    assert second_action.previous_node_id == new_node.id

    # Test `undo`
    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    # order: trigger -> first_action -> second_action
    new_node.refresh_from_db(fields=["trashed", "previous_node_id"])
    assert new_node.trashed
    second_action.refresh_from_db(fields=["previous_node_id"])
    assert second_action.previous_node_id == first_action.id

    # Test `redo`
    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    # order: trigger -> first_action -> new_node -> second_action
    new_node.refresh_from_db(fields=["trashed", "previous_node_id"])
    assert not new_node.trashed
    assert new_node.previous_node_id == first_action.id
    second_action.refresh_from_db(fields=["previous_node_id"])
    assert second_action.previous_node_id == new_node.id
