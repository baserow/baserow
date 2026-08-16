from unittest.mock import patch

import pytest

from baserow.contrib.database.workflow_actions.models import OpenUrlWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)


def _last_field_message(mock_broadcast):
    args = mock_broadcast.delay.call_args
    return args[0][0], args[0][1]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_first_action_tells_the_table_the_button_now_does_something(
    mock_broadcast_to_channel_group, data_fixture
):
    """Whether a cell renders a working button or an inert one comes from
    `has_workflow_actions`, so everyone watching the table has to be told when
    the first action arrives."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action_type = database_workflow_action_type_registry.get("open_url")

    DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    group, message = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "field_updated"
    assert message["field"]["id"] == button_field.id
    assert message["field"]["has_workflow_actions"] is True


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_removing_the_last_action_tells_the_table_the_button_is_inert(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().delete_workflow_action(user, action)

    group, message = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "field_updated"
    assert message["field"]["id"] == button_field.id
    assert message["field"]["has_workflow_actions"] is False


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_reordering_the_actions_is_broadcast_too(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    first = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().order_workflow_actions(
        user, button_field, [second.id, first.id]
    )

    group, message = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "field_updated"
    assert message["field"]["id"] == button_field.id
