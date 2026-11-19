from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.service import ElementService
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
    user.web_socket_id = "requester-tab"

    BuilderWorkflowActionService().delete_workflow_action(
        user=user, workflow_action=workflow_action
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "workflow_action_deleted"
    assert args[0][4]["workflow_action_id"] == workflow_action_id
    assert args[0][4]["page_id"] == page.id
    # The requester's tab removed it itself.
    assert args[0][5] == "requester-tab"


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.builder.ws.workflow_actions.signals.broadcast_to_permitted_users"
)
def test_workflow_action_trashed_by_an_element_update_reaches_the_requester(
    mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {"name": "Go", "type": "button", "config": {"label": "'Go'"}},
            {"name": "Name", "type": "text", "config": {"value": "'Name'"}},
        ],
    )
    go, name = table.fields.order_by("order")
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=table, event=f"{go.uid}_click"
    )
    user.web_socket_id = "requester-tab"

    ElementService().update_element(
        user,
        table,
        fields=[
            {
                "uid": str(name.uid),
                "name": name.name,
                "type": name.type,
                "config": name.config,
            }
        ],
    )

    deleted = [
        call
        for call in mock_broadcast_to_permitted_users.delay.call_args_list
        if call[0][4]["type"] == "workflow_action_deleted"
    ]
    assert [call[0][4]["workflow_action_id"] for call in deleted] == [
        workflow_action.id
    ]
    # The requester's tab doesn't know the action went with the column.
    assert deleted[0][0][5] is None


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.builder.ws.workflow_actions.signals.broadcast_to_permitted_users"
)
def test_workflow_actions_reordered(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    wa1 = data_fixture.create_notification_workflow_action(
        page=page, element=element, event="click", order=1
    )
    wa2 = data_fixture.create_notification_workflow_action(
        page=page, element=element, event="click", order=2
    )

    BuilderWorkflowActionService().order_workflow_actions(
        user, page, [wa2.id, wa1.id], element=element
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "workflow_actions_reordered"
    assert args[0][4]["page_id"] == page.id
    assert args[0][4]["element_id"] == element.id
    assert args[0][4]["order"] == [wa2.id, wa1.id]
