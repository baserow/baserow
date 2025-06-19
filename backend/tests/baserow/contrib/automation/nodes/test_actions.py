import uuid

import pytest

from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
from baserow.contrib.automation.nodes.actions import UpdateAutomationNodeActionType
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.core.action.handler import ActionHandler


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_automation_node_type_change(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowCreateRowNodeType.type,
    )
    updated_node = UpdateAutomationNodeActionType.do(
        user, node.id, {"type": LocalBaserowUpdateRowNodeType.type}
    )

    # The original node is trashed, we have a new node of the new type.
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed
    assert isinstance(updated_node, LocalBaserowUpdateRowNodeType.model_class)

    ActionHandler.undo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    # The original node is restored, the new node is trashed.
    node.refresh_from_db(fields=["trashed"])
    assert not node.trashed
    updated_node.refresh_from_db(fields=["trashed"])
    assert updated_node.trashed

    ActionHandler.redo(user, [WorkflowActionScopeType.value(workflow.id)], session_id)

    # The original node is trashed again, the new node is restored.
    node.refresh_from_db(fields=["trashed"])
    assert node.trashed
    updated_node.refresh_from_db(fields=["trashed"])
    assert not updated_node.trashed
