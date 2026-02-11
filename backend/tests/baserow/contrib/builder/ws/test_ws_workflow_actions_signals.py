from unittest.mock import patch

import pytest

from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.builder.ws.workflow_actions.signals.broadcast_to_permitted_users"
)
def test_workflow_action_created(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action_type = builder_workflow_action_type_registry.get("notification")
    workflow_action = BuilderWorkflowActionService().create_workflow_action(
        user=user,
        workflow_action_type=workflow_action_type,
        page=page,
        element=element,
        event="click",
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "workflow_action_created"
    assert args[0][4]["workflow_action"]["id"] == workflow_action.id
    assert args[0][4]["page_id"] == page.id


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.builder.ws.workflow_actions.signals.broadcast_to_permitted_users"
)
def test_workflow_action_updated(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element
    )

    BuilderWorkflowActionService().update_workflow_action(
        user=user,
        workflow_action=workflow_action,
        title="'Updated title'",
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "workflow_action_updated"
    assert args[0][4]["workflow_action"]["id"] == workflow_action.id
    assert args[0][4]["page_id"] == page.id


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.builder.ws.workflow_actions.signals.broadcast_to_permitted_users"
)
def test_workflow_action_deleted(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element
    )
    workflow_action_id = workflow_action.id

    BuilderWorkflowActionService().delete_workflow_action(
        user=user, workflow_action=workflow_action
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "workflow_action_deleted"
    assert args[0][4]["workflow_action_id"] == workflow_action_id
    assert args[0][4]["page_id"] == page.id
