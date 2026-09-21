from unittest.mock import patch

from django.db import OperationalError, connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
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
from baserow.core.models import WorkspaceUser
from baserow.core.signals import workspace_restored
from baserow.core.trash.handler import TrashHandler


def _last_field_message(mock_broadcast):
    """The last broadcast, as (group, message, web socket id left out)."""

    args = mock_broadcast.delay.call_args
    return args[0][0], args[0][1], args[0][2]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_first_action_tells_the_table_the_button_now_does_something(
    mock_broadcast_to_channel_group, data_fixture
):
    """Whether a cell renders a working button or an inert one comes from
    `has_workflow_actions`, so everyone watching the table has to be told when
    the first action arrives."""

    user = data_fixture.create_user(web_socket_id="editor-session")
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action_type = database_workflow_action_type_registry.get("open_url")

    DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    group, message, left_out = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "button_fields_updated"
    assert message["fields"][0]["id"] == button_field.id
    assert message["fields"][0]["has_workflow_actions"] is True
    # The editor's own session already knows: it made the change.
    assert left_out == "editor-session"


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

    group, message, _ = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "button_fields_updated"
    assert message["fields"][0]["id"] == button_field.id
    assert message["fields"][0]["has_workflow_actions"] is False


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

    group, message, _ = _last_field_message(mock_broadcast_to_channel_group)
    assert group == f"table-{table.id}"
    assert message["type"] == "button_fields_updated"
    assert message["fields"][0]["id"] == button_field.id


def _button_calls(mock_broadcast, button_field):
    """Every `button_fields_updated` broadcast carrying this button."""

    return [
        call
        for call in mock_broadcast.delay.call_args_list
        if call.args[1].get("type") == "button_fields_updated"
        and any(field["id"] == button_field.id for field in call.args[1]["fields"])
    ]


def _button_messages(mock_broadcast, button_field):
    """Every message sent for this button, as (group, message)."""

    return [
        (call.args[0], call.args[1])
        for call in _button_calls(mock_broadcast, button_field)
    ]


def _sessions_left_out(mock_broadcast, button_field):
    """The web socket id each of this button's messages leaves out."""

    return [call.args[2] for call in _button_calls(mock_broadcast, button_field)]


def _button_writing_to(
    data_fixture, user, target_table, mapped_field=None, button_table=None
):
    """A button, in a new table by default, whose create row action targets another."""

    if button_table is None:
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
    user = data_fixture.create_user(web_socket_id="trashing-session")
    target = data_fixture.create_database_table(user=user)
    mapped = data_fixture.create_text_field(table=target, name="Mapped")
    button_field = _button_writing_to(data_fixture, user, target, mapped)
    unrelated = _button_writing_to(data_fixture, user, target)

    FieldHandler().delete_field(user, mapped)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["fields"][0]["requires_reconfiguration"] is True
    # Whoever trashed the field may be looking at the button's table too, and
    # nothing else updates their copy.
    assert _sessions_left_out(mock_broadcast_to_channel_group, button_field) == [None]
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "field", mapped.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


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
    assert message["fields"][0]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "table", target.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


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
    assert message["fields"][0]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "application", other_database.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


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
    assert message["fields"][0]["requires_reconfiguration"] is True
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "integration", bot.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


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
    assert message["fields"][0]["requires_reconfiguration"] is False
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mapped_side", ["link", "related"])
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_permanently_deleting_a_link_field_updates_a_button_mapping_its_related_field(
    mock_broadcast_to_channel_group, data_fixture, mapped_side
):
    """
    Trashing a link field trashes its related field under the same trash entry,
    and deleting it deletes the related field and its mappings too.
    """

    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user, name="A")
    table_b = data_fixture.create_database_table(
        user=user, database=table_a.database, name="B"
    )
    link = FieldHandler().create_field(
        user, table_a, "link_row", name="AtoB", link_row_table=table_b
    )
    related = link.link_row_related_field
    mapped, trashed = (link, related) if mapped_side == "link" else (related, link)
    button_field = _button_writing_to(data_fixture, user, mapped.table, mapped)
    unrelated = _button_writing_to(data_fixture, user, mapped.table)
    FieldHandler().delete_field(user, trashed)
    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is True
    mock_broadcast_to_channel_group.reset_mock()

    _empty_the_trash(user, table_a.database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["fields"][0]["requires_reconfiguration"] is False
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
    assert message["fields"][0]["requires_reconfiguration"] is True
    assert _button_messages(mock_broadcast_to_channel_group, unrelated) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_purging_a_workspace_that_was_never_trashed_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    """`delete_expired_users` and the admin panel delete a workspace outright,
    without the `workspace_deleted` that would have flagged the buttons
    pointing into it."""

    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=other_user)
    button_table = data_fixture.create_database_table(user=user)
    button_field = _button_writing_to(
        data_fixture, other_user, target, button_table=button_table
    )
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        TrashHandler.permanently_delete(target.database.workspace)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_table.id}"
    assert message["fields"][0]["requires_reconfiguration"] is True


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_purging_a_database_that_was_never_trashed_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    """A snapshot's application is dropped the same way when it expires."""

    user = data_fixture.create_user()
    button_table = data_fixture.create_database_table(user=user)
    other_database = data_fixture.create_database_application(
        user=user, workspace=button_table.database.workspace
    )
    target = data_fixture.create_database_table(user=user, database=other_database)
    button_field = _button_writing_to(
        data_fixture, user, target, button_table=button_table
    )
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        TrashHandler.permanently_delete(other_database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_table.id}"
    assert message["fields"][0]["requires_reconfiguration"] is True


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

    with (
        patch(
            "baserow.contrib.database.ws.workflow_actions.signals."
            "button_fields_depending_on"
        ) as lookup,
        django_capture_on_commit_callbacks(execute=True) as callbacks,
    ):
        integration = IntegrationService().create_integration(
            user, integration_type, builder
        )
        IntegrationService().delete_integration(user, integration)
        TrashHandler.restore_item(user, "integration", integration.id)
        IntegrationService().delete_integration(user, integration)
        TrashHandler.empty(user, builder.workspace_id, builder.id)
        TrashHandler.permanently_delete_marked_trash()

    assert [
        c for c in callbacks if "_broadcast_dependent_buttons" in c.__qualname__
    ] == []
    lookup.assert_not_called()


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
    assert message["fields"][0]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "table", linked.id)

    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("has_related_field", [True, False])
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_permanently_deleting_a_table_updates_a_button_mapping_a_link_to_it(
    mock_broadcast_to_channel_group, data_fixture, has_related_field
):
    """The link field to the table is deleted with it, and so is its mapping."""

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
    mock_broadcast_to_channel_group.reset_mock()

    _empty_the_trash(user, linked.database)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_field.table_id}"
    assert message["fields"][0]["requires_reconfiguration"] is False


def _field_messages(mock_broadcast):
    """Every `button_fields_updated` sent, as (group, message)."""

    return [
        (call.args[0], call.args[1])
        for call in mock_broadcast.delay.call_args_list
        if call.args[1].get("type") == "button_fields_updated"
    ]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_buttons_in_one_table_are_sent_in_one_message(
    mock_broadcast_to_channel_group, data_fixture
):
    """A grid takes its buttons from one message, not one each."""

    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    mapped = data_fixture.create_text_field(table=target, name="Mapped")
    button_table = data_fixture.create_database_table(
        user=user, database=target.database
    )
    first, second = [
        _button_writing_to(data_fixture, user, target, mapped, button_table)
        for _ in range(2)
    ]
    elsewhere = _button_writing_to(data_fixture, user, target, mapped)

    FieldHandler().delete_field(user, mapped)

    messages = _field_messages(mock_broadcast_to_channel_group)
    assert sorted(group for group, _ in messages) == sorted(
        [f"table-{button_table.id}", f"table-{elsewhere.table_id}"]
    )
    message = dict(messages)[f"table-{button_table.id}"]
    sent = message["fields"]
    assert sorted(f["id"] for f in sent) == [first.id, second.id]
    assert all(f["requires_reconfiguration"] is True for f in sent)
    assert all(f["has_workflow_actions"] is True for f in sent)


@pytest.mark.django_db
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_sending_the_buttons_does_not_query_per_button(
    mock_broadcast_to_channel_group, data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=user)
    button_table = data_fixture.create_database_table(
        user=user, database=target.database
    )

    def broadcast_queries(button_count):
        mapped = data_fixture.create_text_field(table=target)
        for _ in range(button_count):
            _button_writing_to(data_fixture, user, target, mapped, button_table)
        with django_capture_on_commit_callbacks() as callbacks:
            FieldHandler().delete_field(user, mapped)
        [broadcast] = [
            c for c in callbacks if "_broadcast_dependent_buttons" in c.__qualname__
        ]
        broadcast()
        with CaptureQueriesContext(connection) as captured:
            broadcast()
        return len(captured)

    assert broadcast_queries(3) == broadcast_queries(1)


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_trashing_and_restoring_the_target_workspace_updates_the_button(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    button_table = data_fixture.create_database_table(user=user)
    other_workspace = data_fixture.create_workspace(
        users=[user, data_fixture.create_user()]
    )
    other_database = data_fixture.create_database_application(workspace=other_workspace)
    target = data_fixture.create_database_table(database=other_database)
    button_field = data_fixture.create_button_field(table=button_table, label="Go")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        database_workflow_action_type_registry.get("local_baserow_create_row"),
        button_field,
        service={"table_id": target.id},
    )
    mock_broadcast_to_channel_group.reset_mock()

    CoreHandler().delete_workspace(user, other_workspace)

    [(group, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert group == f"table-{button_table.id}"
    assert message["fields"][0]["requires_reconfiguration"] is True

    mock_broadcast_to_channel_group.reset_mock()
    TrashHandler.restore_item(user, "workspace", other_workspace.id)

    # Restoring tells each member of the workspace, but the button goes once.
    [(_, message)] = _button_messages(mock_broadcast_to_channel_group, button_field)
    assert message["fields"][0]["requires_reconfiguration"] is False


def _self_targeting_button(data_fixture, user):
    """A button whose create row action writes to its own table."""

    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        database_workflow_action_type_registry.get("local_baserow_create_row"),
        button_field,
        service={"table_id": table.id},
    )
    return button_field


def _button_messages_in(mock_broadcast, tables):
    """Every message sent for a button in one of these tables."""

    table_ids = {table.id for table in tables}
    return [
        (group, message)
        for group, message in _field_messages(mock_broadcast)
        for field in message["fields"]
        if field["table_id"] in table_ids
    ]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_duplicating_a_database_does_not_send_the_copied_buttons(
    mock_broadcast_to_channel_group, data_fixture
):
    """Nobody has the copy open yet, and it is loaded with its buttons."""

    user = data_fixture.create_user()
    button_field = _self_targeting_button(data_fixture, user)
    mock_broadcast_to_channel_group.reset_mock()

    copy = CoreHandler().duplicate_application(user, button_field.table.database)

    [copied_table] = copy.table_set.all()
    copied_button = ButtonField.objects.get(table=copied_table)
    assert copied_button.workflow_actions.get().specific.service.specific.table_id == (
        copied_table.id
    )
    assert _button_messages_in(mock_broadcast_to_channel_group, [copied_table]) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_duplicating_a_table_does_not_send_the_copied_buttons(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    button_field = _self_targeting_button(data_fixture, user)
    mock_broadcast_to_channel_group.reset_mock()

    copied_table = TableHandler().duplicate_table(user, button_field.table)

    copied_button = ButtonField.objects.get(table=copied_table)
    assert copied_button.workflow_actions.get().specific.service.specific.table_id == (
        copied_table.id
    )
    assert _button_messages_in(mock_broadcast_to_channel_group, [copied_table]) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_restoring_a_workspace_does_not_send_its_own_buttons(
    mock_broadcast_to_channel_group, data_fixture
):
    """Its members load it again, and nobody has one of its tables open."""

    user = data_fixture.create_user()
    button_field = _self_targeting_button(data_fixture, user)
    workspace = button_field.table.database.workspace
    CoreHandler().delete_workspace(user, workspace)
    mock_broadcast_to_channel_group.reset_mock()

    TrashHandler.restore_item(user, "workspace", workspace.id)

    assert (
        _button_messages_in(mock_broadcast_to_channel_group, [button_field.table]) == []
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_workspace_restored_for_each_member_sends_the_buttons_once(
    mock_broadcast_to_channel_group, data_fixture
):
    """However each member's copy of the workspace was loaded."""

    user = data_fixture.create_user()
    button_table = data_fixture.create_database_table(user=user)
    other_workspace = data_fixture.create_workspace(
        users=[user, data_fixture.create_user()]
    )
    target = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=other_workspace)
    )
    button_field = data_fixture.create_button_field(table=button_table, label="Go")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        database_workflow_action_type_registry.get("local_baserow_create_row"),
        button_field,
        service={"table_id": target.id},
    )
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        for workspace_user in WorkspaceUser.objects.filter(workspace=other_workspace):
            workspace_restored.send(None, workspace_user=workspace_user, user=None)

    assert len(_button_messages(mock_broadcast_to_channel_group, button_field)) == 1


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_purging_a_workspace_collects_only_the_buttons_outside_it_once(
    mock_broadcast_to_channel_group, data_fixture
):
    """Its own buttons are deleted with it, and each of its tables is purged
    too, so a button mapping a link to one of them is found twice."""

    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    target = data_fixture.create_database_table(user=other_user)
    linked = data_fixture.create_database_table(
        user=other_user, database=target.database
    )
    link = data_fixture.create_link_row_field(
        user=other_user, table=target, link_row_table=linked
    )
    button_table = data_fixture.create_database_table(user=user)
    outside = _button_writing_to(
        data_fixture, other_user, target, mapped_field=link, button_table=button_table
    )
    inside = _self_targeting_button(data_fixture, other_user)
    inside.table.database.workspace_id = target.database.workspace_id
    inside.table.database.save()
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        TrashHandler.permanently_delete(target.database.workspace)
        pending = [
            ids
            for _, callback, _ in connection.run_on_commit
            if (ids := getattr(callback, "purged_button_field_ids", None)) is not None
        ]

    assert pending == [{outside.id}]
    assert len(_button_messages(mock_broadcast_to_channel_group, outside)) == 1
