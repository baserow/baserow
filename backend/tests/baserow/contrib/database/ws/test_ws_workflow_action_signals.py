from unittest.mock import patch

from django.db import OperationalError, connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.trash.trash_types import FieldTrashableItemType
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    OpenUrlWorkflowAction,
    SlackWriteMessageWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
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


def _button_sending_through(data_fixture, user, bot):
    """A button whose Slack action posts through this bot."""

    button_table = data_fixture.create_database_table(
        user=user, database=bot.application
    )
    button_field = data_fixture.create_button_field(table=button_table, label="Go")
    action = data_fixture.create_database_workflow_action(
        SlackWriteMessageWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.integration = bot
    service.save()
    return button_field


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_and_restoring_an_integration_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    bot = data_fixture.create_slack_bot_integration(application=database, user=user)
    button_field = _button_sending_through(data_fixture, user, bot)
    other_bot = data_fixture.create_slack_bot_integration(
        application=database, user=user
    )
    unrelated = _button_sending_through(data_fixture, user, other_bot)

    IntegrationService().delete_integration(user, bot)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is True
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "integration", bot.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["field"]["requires_reconfiguration"] is False


def _empty_the_trash(user, database):
    """Marks the database's trash for deletion and deletes it, as Celery does."""

    TrashHandler.empty(user, database.workspace_id, database.id)
    TrashHandler.permanently_delete_marked_trash()


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_permanently_deleting_a_mapped_field_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    mapped = data_fixture.create_text_field(table=target, name="Mapped")
    button_field = _button_writing_to(data_fixture, user, target, mapped)
    unrelated = _button_writing_to(data_fixture, user, target)
    FieldHandler().delete_field(user, mapped)
    mock_broadcast_to_channel_group.reset_mock()

    _empty_the_trash(user, target.database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is False
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_permanently_deleting_an_integration_leaves_the_button_needing_one(
    mock_broadcast_to_channel_group, data_fixture
):
    """The service is left with no integration, which Slack still needs."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    bot = data_fixture.create_slack_bot_integration(application=database, user=user)
    button_field = _button_sending_through(data_fixture, user, bot)
    other_bot = data_fixture.create_slack_bot_integration(
        application=database, user=user
    )
    unrelated = _button_sending_through(data_fixture, user, other_bot)
    IntegrationService().delete_integration(user, bot)
    mock_broadcast_to_channel_group.reset_mock()

    _empty_the_trash(user, database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is True
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_permanent_deletion_that_rolls_back_sends_nothing(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    mapped = data_fixture.create_text_field(table=target, name="Mapped")
    button_field = _button_writing_to(data_fixture, user, target, mapped)
    FieldHandler().delete_field(user, mapped)
    mock_broadcast_to_channel_group.reset_mock()

    with (
        patch.object(
            FieldTrashableItemType,
            "permanently_delete_item",
            side_effect=OperationalError("Lost the connection."),
        ),
        pytest.raises(OperationalError),
    ):
        _empty_the_trash(user, target.database)

    assert _button_messages(mock_broadcast_to_channel_group, button_field) == []


@pytest.mark.django_db
def test_an_integration_outside_a_database_is_never_looked_up(
    data_fixture, django_capture_on_commit_callbacks
):
    """No button can use a builder's or an automation's integration."""

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    with django_capture_on_commit_callbacks() as callbacks:
        integration = IntegrationService().create_integration(
            user, integration_type, builder
        )
        IntegrationService().delete_integration(user, integration)
        TrashHandler.restore_item(user, "integration", integration.id)

    assert [
        c for c in callbacks if "_broadcast_dependent_buttons" in c.__qualname__
    ] == []


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


@pytest.mark.django_db
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_table_no_action_targets_stops_at_one_lookup(
    mock_broadcast_to_channel_group, data_fixture, django_capture_on_commit_callbacks
):
    """
    Every table and application created runs this check, so when no service
    points at it the buttons and their actions are never looked at.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    # A button elsewhere, so there is something a careless lookup could join.
    _button_writing_to(
        data_fixture, user, data_fixture.create_database_table(database=database)
    )

    with django_capture_on_commit_callbacks() as callbacks:
        TableHandler().create_table(user, database, name="New")
    [check] = [c for c in callbacks if "_broadcast_dependent_buttons" in c.__qualname__]

    with CaptureQueriesContext(connection) as captured:
        check()

    assert len(captured) == 1
    assert "database_buttonfield" not in captured[0]["sql"]
    assert "database_databaseworkflowaction" not in captured[0]["sql"]
    mock_broadcast_to_channel_group.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("has_related_field", [True, False])
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_a_table_updates_a_button_mapping_a_link_to_it(
    mock_broadcast_to_channel_group, data_fixture, has_related_field
):
    """Trashing a table trashes the link fields to it in other tables too."""

    user = data_fixture.create_user()
    linked = data_fixture.create_database_table(user=user, name="A")
    target = data_fixture.create_database_table(
        user=user, database=linked.database, name="B"
    )
    link = FieldHandler().create_field(
        user,
        target,
        "link_row",
        name="Link",
        link_row_table=linked,
        has_related_field=has_related_field,
    )
    button_field = _button_writing_to(data_fixture, user, target, link)

    TableHandler().delete_table(user, linked)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["field"]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "table", linked.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["field"]["requires_reconfiguration"] is False
