import pytest

from baserow.contrib.automation.nodes.trash_types import AutomationNodeTrashableItemType
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_trashing_and_restoring_node_updates_next_node_previous_node_id(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow
    )
    first = data_fixture.create_local_baserow_create_row_action_node(workflow=workflow)
    second = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    assert trigger.previous_node_id is None
    assert first.previous_node_id == trigger.id
    assert second.previous_node_id == first.id

    automation = workflow.automation
    TrashHandler.trash(user, automation.workspace, automation, first)

    trigger.refresh_from_db()
    second.refresh_from_db()

    assert trigger.previous_node_id is None
    assert second.previous_node_id == trigger.id

    TrashHandler.restore_item(
        user,
        AutomationNodeTrashableItemType.type,
        first.id,
    )

    trigger.refresh_from_db()
    second.refresh_from_db()

    assert trigger.previous_node_id is None
    assert first.previous_node_id == trigger.id
    assert second.previous_node_id == first.id
