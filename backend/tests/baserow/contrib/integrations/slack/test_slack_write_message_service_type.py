import json
from unittest.mock import Mock, patch

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.formula_importer import import_formula
from baserow.contrib.integrations.slack.service_types import (
    SlackWriteMessageServiceType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.types import DispatchResult
from baserow.test_utils.helpers import AnyInt
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_dispatch_slack_write_message_basic(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello from Baserow!'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    # Mock the HTTP request
    mock_response = Mock()
    mock_response.json.return_value = {
        "ok": True,
        "channel": "C123456",
        "ts": "1503435956.000247",
        "message": {"text": "Hello from Baserow!", "username": "baserow_bot"},
    }

    mock_request = Mock(return_value=mock_response)

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=mock_request,
    ):
        dispatch_data = service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            method="POST",
            url="https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer xoxb-test-token-12345"},
            params={
                "channel": "#general",
                "text": "Hello from Baserow!",
            },
            timeout=10,
        )

    assert dispatch_data.data["data"]["ok"] is True
    assert "channel" in dispatch_data.data["data"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error_code,expected_message",
    [
        ("no_text", "The message text is missing."),
        ("invalid_auth", "Invalid bot user token."),
        ("channel_not_found", "The channel #general was not found."),
        ("not_in_channel", "Your app has not been invited to channel #general."),
        (
            "rate_limited",
            "Your app has sent too many requests in a short period of time.",
        ),
        (
            "some_unknown_error",
            "An unknown error occurred while sending the message, the error code was: some_unknown_error",
        ),
    ],
)
def test_dispatch_slack_write_message_api_errors(
    data_fixture, error_code, expected_message
):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello from Baserow!'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    mock_response = Mock()
    mock_response.json.return_value = {
        "ok": False,
        "error": error_code,
    }

    mock_request = Mock(return_value=mock_response)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        with patch(
            "baserow.contrib.integrations.slack.service_types.get_http_request_function",
            return_value=mock_request,
        ):
            service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == expected_message


@pytest.mark.django_db
def test_dispatch_slack_write_message_with_formulas(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=application)
    trigger = workflow.get_trigger()

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text=f"concat('User ', get('previous_node.{trigger.id}.0.name'), ' has joined!')",
    )

    service_type = service.get_type()
    dispatch_context = AutomationDispatchContext(workflow)
    dispatch_context.after_dispatch(
        trigger, DispatchResult(data={"results": [{"name": "John"}]})
    )

    mock_response = Mock()
    mock_response.json.return_value = {
        "ok": True,
        "channel": "C123456",
        "ts": "1503435956.000247",
    }
    mock_request = Mock(return_value=mock_response)

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=mock_request,
    ):
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            method="POST",
            url="https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer xoxb-test-token-12345"},
            params={
                "channel": "#general",
                "text": "User John has joined!",
            },
            timeout=10,
        )


@pytest.mark.django_db
def test_slack_write_message_create(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello Slack!'",
    )

    assert service.channel == "general"
    assert service.text["formula"] == "'Hello Slack!'"
    assert service.integration.specific.token == "xoxb-test-token-12345"


@pytest.mark.django_db
def test_slack_write_message_update(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello Slack!'",
    )

    service_type = service.get_type()

    ServiceHandler().update_service(
        service_type,
        service,
        channel="announcements",
        text="'Updated message!'",
    )

    service.refresh_from_db()

    assert service.channel == "announcements"
    assert service.text["formula"] == "'Updated message!'"


@pytest.mark.django_db
def test_slack_write_message_formula_generator(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello Slack!'",
    )

    service_type = service.get_type()

    formulas = list(service_type.formula_generator(service))
    assert formulas == [
        {"mode": "simple", "version": "0.1", "formula": "'Hello Slack!'"},
    ]


@pytest.mark.django_db
def test_slack_write_message_export_import(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(automation=application)
    old_trigger = workflow.get_trigger()

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )

    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text=f"get('previous_node.{old_trigger.id}.0.field_123')",
    )

    service_type = service.get_type()

    serialized = json.loads(json.dumps(service_type.export_serialized(service)))
    assert serialized == {
        "id": AnyInt(),
        "integration_id": integration.id,
        "sample_data": None,
        "type": "slack_write_message",
        "channel": "general",
        "text": {
            "formula": f"get('previous_node.{old_trigger.id}.0.field_123')",
            "version": "0.1",
            "mode": "simple",
        },
    }

    new_workflow = data_fixture.create_automation_workflow(automation=application)
    new_trigger = new_workflow.get_trigger()
    id_mapping = {"automation_workflow_nodes": {old_trigger.id: new_trigger.id}}
    new_service = service_type.import_serialized(
        None, serialized, id_mapping, import_formula
    )
    assert new_service.channel == "general"
    assert (
        new_service.text["formula"]
        == f"get('previous_node.{new_trigger.id}.0.field_123')"
    )


@pytest.mark.django_db
def test_slack_write_message_generate_schema(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_automation_application(user=user)
    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=application,
        token="xoxb-test-token-12345",
    )
    service = ServiceHandler().create_service(
        SlackWriteMessageServiceType(),
        integration=integration,
        channel="general",
        text="'Hello Slack!'",
    )
    schema = service.get_type().generate_schema(service)
    assert schema == {
        "title": f"SlackWriteMessage{service.id}Schema",
        "type": "object",
        "properties": {
            "ok": {
                "type": "boolean",
                "title": "OK",
            },
        },
    }
