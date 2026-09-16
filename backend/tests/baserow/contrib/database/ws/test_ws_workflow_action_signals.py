from unittest.mock import patch

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler


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


def _button_messages(mock_broadcast, button_field):
    """Every `field_updated` sent for this button, as (group, message)."""

    return [
        (call.args[0], call.args[1])
        for call in mock_broadcast.delay.call_args_list
        if call.args[1].get("type") == "field_updated"
        and call.args[1]["field"]["id"] == button_field.id
    ]


def _button_writing_to(data_fixture, user, target_table, mapped_field=None):
    """A button in its own table whose create row action targets another."""

    button_table = data_fixture.create_database_table(
        user=user, database=target_table.database
    )
    button_field = data_fixture.create_button_field(table=button_table, label="Go")
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = target_table
    service.save()
    if mapped_field is not None:
        service.field_mappings.create(field=mapped_field, value="'x'", enabled=True)
    return button_field


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_and_restoring_a_mapped_field_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    mapped = data_fixture.create_text_field(table=target, name="Mapped")
    button_field = _button_writing_to(data_fixture, user, target, mapped)
    unrelated = _button_writing_to(data_fixture, user, target)

    FieldHandler().delete_field(user, mapped)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is True
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "field", mapped.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["field"]["requires_reconfiguration"] is False


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_and_restoring_a_target_table_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    button_field = _button_writing_to(data_fixture, user, target)

    TableHandler().delete_table(user, target)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "table", target.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["field"]["requires_reconfiguration"] is False


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_and_restoring_the_target_database_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    button_table = data_fixture.create_database_table(user=user)
    other_database = data_fixture.create_database_application(
        user=user, workspace=button_table.database.workspace
    )
    target = data_fixture.create_database_table(user=user, database=other_database)
    button_field = data_fixture.create_button_field(table=button_table, label="Go")
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = target
    service.save()

    CoreHandler().delete_application(user, other_database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_table.id}"
    assert message["field"]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "application", other_database.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["field"]["requires_reconfiguration"] is False


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_the_buttons_own_table_sends_the_button_nowhere(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()

    TableHandler().delete_table(user, table)

    assert _button_messages(mock_broadcast_to_channel_group, button_field) == []
