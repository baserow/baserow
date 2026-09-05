import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionInvalidIntegration,
)
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    SlackWriteMessageWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.deferred_callbacks import deferred_callback_context
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)


def _button(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    return data_fixture.create_button_field(table=table)


def _bot(data_fixture, database):
    return data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Bot", token="xoxb-secret"
    )


def _denying(operation_name: str):
    """A `check_permissions` that refuses one operation and defers the rest."""

    real = CoreHandler.check_permissions

    def check_permissions(self, actor, name, *args, **kwargs):
        if name == operation_name:
            raise PermissionException(f"cannot {name}")
        return real(self, actor, name, *args, **kwargs)

    return check_permissions


def _slack_answer(**overrides):
    body = {
        "ok": True,
        "channel": "C123",
        "ts": "1503435956.000247",
        **overrides,
    }
    response = Mock()
    response.json.return_value = body
    # The service streams the body in, so it can stop an endpoint that sends
    # more than this installation accepts.
    response.iter_content.return_value = iter([json.dumps(body).encode()])
    return Mock(return_value=response)


def test_the_slack_action_is_registered():
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    assert action_type.model_class is SlackWriteMessageWorkflowAction
    assert action_type.service_type == "slack_write_message"
    assert action_type.is_external is True


@pytest.mark.django_db
def test_a_slack_action_attaches_a_bot_of_its_own_database(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    assert action.service.integration_id == bot.id


@pytest.mark.django_db
def test_a_slack_action_refuses_a_bot_of_another_application(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    other_database = data_fixture.create_database_application(
        workspace=button_field.table.database.workspace
    )
    bot = _bot(data_fixture, other_database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    with pytest.raises(WorkflowActionInvalidIntegration):
        DatabaseWorkflowActionService().create_workflow_action(
            user, action_type, button_field, service={"integration_id": bot.id}
        )


@pytest.mark.django_db
def test_a_slack_action_refuses_a_bot_the_user_cannot_read(data_fixture):
    # RBAC can grant a table without its database, and the button editor must
    # not be a way to use what the sidebar would not list.
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    refused = PermissionException("cannot read")

    with patch(
        "baserow.core.integrations.service.CoreHandler.check_permissions",
        side_effect=refused,
    ):
        with pytest.raises(PermissionException) as raised:
            action_type.prepare_values(
                {"service": {"integration_id": bot.id}, "field": button_field},
                user,
                None,
            )

    assert raised.value is refused


@pytest.mark.django_db
def test_a_slack_action_refuses_a_local_baserow_integration(data_fixture):
    # ADR 006 section 5: a database click never runs as an integration's user.
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    local = data_fixture.create_local_baserow_integration(
        user=user, application=button_field.table.database, authorized_user=user
    )
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    with pytest.raises(WorkflowActionInvalidIntegration):
        DatabaseWorkflowActionService().create_workflow_action(
            user, action_type, button_field, service={"integration_id": local.id}
        )


@pytest.mark.django_db
def test_a_row_action_refuses_a_slack_bot(data_fixture):
    # The allow-list is per type: a row action still carries nothing.
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(WorkflowActionInvalidIntegration):
        DatabaseWorkflowActionService().create_workflow_action(
            user, action_type, button_field, service={"integration_id": bot.id}
        )


@pytest.mark.django_db
def test_dispatching_refuses_a_row_service_carrying_a_bot(data_fixture):
    # Defence in depth: the guard on dispatch uses the same allow-list.
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.integration = bot
    service.save()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        action_type.dispatch(action, SimpleNamespace(field=button_field))


@pytest.mark.django_db
def test_a_click_posts_the_resolved_text_through_the_bot(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    table = button_field.table
    name_field = table.field_set.get(name="Name")
    bot = _bot(data_fixture, table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={
            "integration_id": bot.id,
            "channel": "general",
            "text": f"concat('Hello ', get('row.field_{name_field.id}'))",
        },
    )
    row = table.get_model().objects.create(**{f"field_{name_field.id}": "Ada"})
    slack = _slack_answer()

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=slack,
    ):
        result = DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    slack.assert_called_once()
    call = slack.call_args.kwargs
    assert call["headers"] == {"Authorization": "Bearer xoxb-secret"}
    assert call["data"] == {"channel": "#general", "text": "Hello Ada"}
    assert "params" not in call
    (dispatched,) = result.dispatched
    assert dispatched.result.data["data"]["ts"] == "1503435956.000247"


@pytest.mark.django_db
def test_a_later_action_can_write_the_message_timestamp(data_fixture):
    # What the explorer offers under the Slack action has to be where the
    # provider reads it, or the second action fails on every click.
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    table = button_field.table
    ts_field = data_fixture.create_text_field(table=table, name="Slack ts")
    bot = _bot(data_fixture, table.database)
    slack_type = database_workflow_action_type_registry.get("slack_write_message")
    slack_action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        slack_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    update_type = database_workflow_action_type_registry.get("local_baserow_update_row")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        update_type,
        button_field,
        service={
            "table_id": table.id,
            "row_id": "get('row.id')",
            "field_mappings": [
                {
                    "field_id": ts_field.id,
                    "value": f"get('previous_action.{slack_action.id}.data.ts')",
                    "enabled": True,
                }
            ],
        },
    )
    row = table.get_model().objects.create()

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=_slack_answer(),
    ):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    row.refresh_from_db()
    assert getattr(row, f"field_{ts_field.id}") == "1503435956.000247"


@pytest.mark.django_db
def test_a_slack_refusal_reaches_the_clicker_without_the_token(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    table = button_field.table
    bot = _bot(data_fixture, table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    row = table.get_model().objects.create()
    slack = _slack_answer(ok=False, error="not_in_channel")

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=slack,
    ):
        with pytest.raises(Exception) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert "invited to channel #general" in str(raised.value)
    assert "xoxb-secret" not in str(raised.value)


@pytest.mark.django_db
def test_a_refused_integration_answers_the_same_whatever_it_is(data_fixture):
    """
    The refusal must not say whether the id names something, or what type it
    is, or the endpoint becomes a way to enumerate the whole installation.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    stranger = data_fixture.create_user()
    elsewhere = data_fixture.create_database_application(user=stranger)
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    reasons = set()
    for integration_id in [
        _bot(data_fixture, elsewhere).id,  # someone else's, of the right type
        data_fixture.create_local_baserow_integration(
            user=user, application=button_field.table.database, authorized_user=user
        ).id,  # this database's, of a refused type
        99999999,  # names nothing at all
    ]:
        with pytest.raises(WorkflowActionInvalidIntegration) as raised:
            action_type.prepare_values(
                {"service": {"integration_id": integration_id}, "field": button_field},
                user,
                None,
            )
        reasons.add(str(raised.value))

    assert len(reasons) == 1, f"the refusals differ and can be told apart: {reasons}"


@pytest.mark.django_db
def test_dispatching_refuses_a_bot_of_another_database(data_fixture):
    """
    The guard on dispatch reads the same rule as the one on save, so a service
    that reached this state some other way still cannot post.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    elsewhere = data_fixture.create_database_application(user=user)
    action = data_fixture.create_database_workflow_action(
        SlackWriteMessageWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.integration = _bot(data_fixture, elsewhere)
    service.save()
    action_type = database_workflow_action_type_registry.get("slack_write_message")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        action_type.dispatch(action, SimpleNamespace(field=button_field))


@pytest.mark.django_db
def test_editing_an_action_still_checks_the_integration_it_already_carries(
    data_fixture,
):
    """
    Someone who may edit the field but not read the bot must not be able to
    retarget it by editing only the channel and the message. The check has to
    run on every save, not just the one that attaches the id.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    refused = PermissionException("cannot read this integration")

    # The id is not resent: only the channel and the message are.
    with patch(
        "baserow.contrib.database.workflow_actions.workflow_action_types."
        "CoreHandler.check_permissions",
        side_effect=refused,
    ):
        with pytest.raises(PermissionException) as raised:
            action_type.prepare_values(
                {"service": {"channel": "board-private", "text": "'psst'"}},
                user,
                action,
            )

    assert raised.value is refused


@pytest.mark.django_db
def test_duplicating_a_field_drops_a_bot_the_duplicator_cannot_read(data_fixture):
    """
    Duplication copies the action without going through the endpoint that
    checks permissions, so without a check here it hands someone a button
    that posts through a credential they may not read.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    real = CoreHandler.check_permissions

    def deny_only_reading_the_integration(self, actor, operation_name, *args, **kwargs):
        if operation_name == ReadIntegrationOperationType.type:
            raise PermissionException("cannot read this integration")
        return real(self, actor, operation_name, *args, **kwargs)

    with patch.object(
        CoreHandler, "check_permissions", deny_only_reading_the_integration
    ):
        duplicated, _ = FieldHandler().duplicate_field(user, button_field)

    (copied,) = DatabaseWorkflowAction.objects.filter(field=duplicated)
    assert copied.specific.service.integration_id is None


@pytest.mark.django_db
def test_duplicating_a_table_drops_a_bot_the_duplicator_cannot_read(data_fixture):
    """
    A table duplication copies the action through the serialized import path,
    which has no actor of its own unless the config carries one.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    with patch.object(
        CoreHandler, "check_permissions", _denying(ReadIntegrationOperationType.type)
    ):
        duplicated = TableHandler().duplicate_table(user, button_field.table)

    (copied,) = DatabaseWorkflowAction.objects.filter(field__table=duplicated)
    assert copied.specific.service.integration_id is None


@pytest.mark.django_db
def test_duplicating_a_table_keeps_a_bot_the_duplicator_can_read(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    duplicated = TableHandler().duplicate_table(user, button_field.table)

    (copied,) = DatabaseWorkflowAction.objects.filter(field__table=duplicated)
    assert copied.specific.service.integration_id == bot.id


@pytest.mark.django_db
def test_duplicating_a_database_drops_a_bot_the_duplicator_cannot_read(data_fixture):
    """
    The database duplication clones the bot too, token and all, so the copied
    action would carry a credential its owner may not read.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    database = button_field.table.database
    bot = _bot(data_fixture, database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    with patch.object(
        CoreHandler, "check_permissions", _denying(ReadIntegrationOperationType.type)
    ):
        duplicated = CoreHandler().duplicate_application(user, database)

    (copied,) = DatabaseWorkflowAction.objects.filter(field__table__database=duplicated)
    assert copied.specific.service.integration_id is None


@pytest.mark.django_db
def test_duplicating_a_database_keeps_a_bot_the_duplicator_can_read(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    database = button_field.table.database
    bot = _bot(data_fixture, database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    duplicated = CoreHandler().duplicate_application(user, database)

    (copied,) = DatabaseWorkflowAction.objects.filter(field__table__database=duplicated)
    # The copy of the bot this duplication made, not the original.
    assert copied.specific.service.integration_id not in (None, bot.id)
    assert copied.specific.service.integration.application_id == duplicated.id


@pytest.mark.django_db
def test_duplicating_a_field_keeps_a_bot_the_duplicator_can_read(data_fixture):
    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    duplicated, _ = FieldHandler().duplicate_field(user, button_field)

    (copied,) = DatabaseWorkflowAction.objects.filter(field=duplicated)
    assert copied.specific.service.integration_id == bot.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "integration_id",
    ["not-a-number", "", None, 0, [], {}, [1], {"id": 1}, True, False, 1.5],
)
def test_an_imported_action_survives_an_integration_id_that_is_not_a_number(
    data_fixture, integration_id
):
    """
    Nothing coerces the value on the import path the way the endpoint's
    serializer does, so a hand-edited export must not fail the job with a
    database error, and must not key the id mapping with something that
    cannot be a key.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    exported = action_type.export_serialized(action)
    exported["service"]["integration_id"] = integration_id

    with deferred_callback_context():
        imported = action_type.import_serialized(button_field, exported, {})

    assert imported.service.integration_id is None


@pytest.mark.django_db
def test_an_imported_action_refuses_a_boolean_integration_id(data_fixture):
    """
    `True` hashes equal to `1`, so an unguarded lookup hands it whatever
    integration 1 was remapped to.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    exported = action_type.export_serialized(action)
    exported["service"]["integration_id"] = True

    with deferred_callback_context():
        imported = action_type.import_serialized(
            button_field, exported, {"integrations": {1: bot.id}}
        )

    assert imported.service.integration_id is None


@pytest.mark.django_db
def test_an_imported_integration_id_is_remapped_when_it_arrives_as_a_string(
    data_fixture,
):
    """
    JSON round trips turn keys into strings. Coercing after the lookup rather
    than before misses the mapping and resolves the id the export was written
    with, which is another database's.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    database = button_field.table.database
    bot = _bot(data_fixture, database)
    copy = data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Copy", token="xoxb-copy"
    )
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )
    exported = action_type.export_serialized(action)
    exported["service"]["integration_id"] = str(bot.id)

    with deferred_callback_context():
        imported = action_type.import_serialized(
            button_field, exported, {"integrations": {bot.id: copy.id}}
        )

    assert imported.service.integration_id == copy.id


@pytest.mark.django_db
def test_a_click_does_not_read_the_field_again_for_every_action(data_fixture):
    """
    The dispatch already holds the field and hands it to the context. Reading
    it back through each action costs two cold queries apiece, inside the lock
    that guards the row.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    table = button_field.table
    bot = _bot(data_fixture, table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    for _ in range(3):
        DatabaseWorkflowActionService().create_workflow_action(
            user,
            action_type,
            button_field,
            service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
        )
    row = table.get_model().objects.create()

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=_slack_answer(),
    ):
        with CaptureQueriesContext(connection) as queries:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    # The guard reads the field and then its table for every action, so this
    # grows with the number of actions unless it uses the one the context
    # already holds.
    read_the_field = [
        q
        for q in queries.captured_queries
        if '"database_field"' in q["sql"] or '"database_table"' in q["sql"]
    ]
    assert len(read_the_field) <= 2, (
        f"the field and its table were read {len(read_the_field)} times for "
        f"three actions: " + "\n".join(q["sql"][:120] for q in read_the_field)
    )


@pytest.mark.django_db
def test_a_click_reads_the_bot_once_however_many_actions_share_it(data_fixture):
    """
    `select_related("integration")` only saves the base row. Resolving the
    subtype for the token costs a query apiece unless the click resolves them
    together, and it pays that inside the lock that guards the row.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    table = button_field.table
    bot = _bot(data_fixture, table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    for _ in range(3):
        DatabaseWorkflowActionService().create_workflow_action(
            user,
            action_type,
            button_field,
            service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
        )
    row = table.get_model().objects.create()

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=_slack_answer(),
    ):
        with CaptureQueriesContext(connection) as queries:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    read_the_bot = [
        q
        for q in queries.captured_queries
        if '"integrations_slackbotintegration"' in q["sql"]
    ]
    assert len(read_the_bot) == 1, (
        f"the bot was read {len(read_the_bot)} times for three actions "
        f"sharing it: " + "\n".join(q["sql"][:120] for q in read_the_bot)
    )


@pytest.mark.django_db
def test_an_action_can_have_its_bot_cleared_without_reading_it(data_fixture):
    """
    Removing a credential takes nothing away from anyone, so it must not need
    permission to read the one being removed. An explicit null has to be told
    apart from a key the request never sent.
    """

    user = data_fixture.create_user()
    button_field = _button(data_fixture, user)
    bot = _bot(data_fixture, button_field.table.database)
    action_type = database_workflow_action_type_registry.get("slack_write_message")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        action_type,
        button_field,
        service={"integration_id": bot.id, "channel": "general", "text": "'hi'"},
    )

    with patch.object(
        CoreHandler, "check_permissions", _denying(ReadIntegrationOperationType.type)
    ):
        DatabaseWorkflowActionService().update_workflow_action(
            user, action, service={"integration_id": None}
        )

    action.refresh_from_db()
    assert action.service.specific.integration_id is None
