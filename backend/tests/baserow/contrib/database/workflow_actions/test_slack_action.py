from unittest.mock import Mock, patch

import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionInvalidIntegration,
)
from baserow.contrib.database.workflow_actions.models import (
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
from baserow.core.exceptions import PermissionException
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


def _slack_answer(**overrides):
    response = Mock()
    response.json.return_value = {
        "ok": True,
        "channel": "C123",
        "ts": "1503435956.000247",
        **overrides,
    }
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
        action_type.dispatch(action, None)


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
    assert call["params"] == {"channel": "#general", "text": "Hello Ada"}
    (dispatched,) = result.dispatched
    assert dispatched.result.data["ts"] == "1503435956.000247"


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
                    "value": f"get('previous_action.{slack_action.id}.ts')",
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
