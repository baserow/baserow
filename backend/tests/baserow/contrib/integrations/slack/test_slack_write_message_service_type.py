import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import override_settings
from django.utils import timezone

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

import baserow.contrib.integrations.slack.service_types as service_types_module
from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.formula_importer import import_formula
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.integrations.slack.models import (
    SlackBotIntegration,
    SlackWriteMessageService,
)
from baserow.contrib.integrations.slack.service_types import (
    SlackWriteMessageServiceType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    ResponseTooLargeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
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
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    mock_response.iter_content.return_value = iter([b"{}"])

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
            stream=True,
        )

    # Unwrapped like the HTTP and email services, so `ok`, `channel` and
    # `ts` sit where the schema says a later step can read them.
    assert dispatch_data.data["ok"] is True
    assert dispatch_data.data["channel"] == "C123456"
    assert dispatch_data.data["ts"] == "1503435956.000247"


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
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    mock_response.iter_content.return_value = iter([b"{}"])

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
    workflow_history = AutomationHistoryHandler().create_workflow_history(
        workflow,
        workflow,
        timezone.now(),
        False,
    )

    trigger = workflow.get_trigger()
    trigger_node_history = AutomationHistoryHandler().create_node_history(
        workflow_history=workflow_history,
        node=trigger,
        started_on=timezone.now(),
    )
    AutomationHistoryHandler().create_node_result(
        node_history=trigger_node_history,
        result={"results": [{"name": "John"}]},
    )

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
    dispatch_context = AutomationDispatchContext(
        workflow,
        workflow_history,
    )

    mock_response = Mock()
    mock_response.json.return_value = {
        "ok": True,
        "channel": "C123456",
        "ts": "1503435956.000247",
    }
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    mock_response.iter_content.return_value = iter([b"{}"])
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
            stream=True,
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
            "channel": {
                "type": "string",
                "title": "Channel",
            },
            "ts": {
                "type": "string",
                "title": "Message timestamp",
            },
        },
    }


@pytest.mark.django_db
def test_slack_write_message_generate_schema_respects_allowed_fields(data_fixture):
    service = data_fixture.create_slack_write_message_service()

    schema = service.get_type().generate_schema(service, allowed_fields=["ts"])

    assert list(schema["properties"]) == ["ts"]


@pytest.mark.django_db
def test_slack_write_message_waits_as_long_as_its_request(data_fixture):
    # A lock held over the dispatch has to outlive the request timeout.
    service = data_fixture.create_slack_write_message_service()

    assert service.get_type().max_dispatch_seconds(service) == 10


@pytest.mark.django_db
@override_settings(INTEGRATIONS_SLACK_API_URL="http://slack-stub:8080/api")
def test_slack_write_message_posts_to_the_configured_api(data_fixture):
    """
    The e2e stack has no way to reach slack.com, so it points the service at a
    stub of its own through this setting.
    """

    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )
    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "channel": "C1", "ts": "1.2"}
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    mock_response.iter_content.return_value = iter([b"{}"])
    mock_request = Mock(return_value=mock_response)

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=mock_request,
    ):
        service.get_type().dispatch(service, FakeDispatchContext())

    assert mock_request.call_args.kwargs["url"] == (
        "http://slack-stub:8080/api/chat.postMessage"
    )


@pytest.mark.django_db
def test_slack_write_message_refusal_without_an_error_code(data_fixture):
    """
    The endpoint is configurable, so the body is not guaranteed to be Slack's.
    A refusal that names no code must still reach the clicker as a message
    rather than a 500.
    """

    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )
    answered = Mock()
    answered.json.return_value = {"message": "forbidden"}
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    answered.iter_content.return_value = iter([b"{}"])

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=Mock(return_value=answered),
    ):
        with pytest.raises(ServiceImproperlyConfiguredDispatchException) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert "xoxb-test" not in str(raised.value)


def test_slack_write_message_channel_cannot_outgrow_its_column():
    """
    The API validates through this field, so without a limit an over-long
    channel reaches the insert and answers 500 instead of 400.
    """

    field = SlackWriteMessageServiceType().serializer_field_overrides["channel"]
    column = SlackWriteMessageService._meta.get_field("channel")

    assert field.max_length == column.max_length

    with pytest.raises(DRFValidationError):
        field.run_validation("a" * (column.max_length + 1))


@pytest.mark.django_db
def test_slack_write_message_refused_address_is_not_charged(data_fixture):
    """
    Advocate refuses the address before anything is sent, so a caller
    counting outbound traffic must not count it. The HTTP service answers the
    same way.
    """

    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )
    refuses = Mock(side_effect=UnacceptableAddressException("10.0.0.5"))

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=refuses,
    ):
        with pytest.raises(AddressNotAllowedDispatchException):
            service.get_type().dispatch(service, FakeDispatchContext())


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body", [[], "forbidden", 12, {"ok": False, "error": {"code": "denied"}}]
)
def test_slack_write_message_answer_that_is_not_an_object(data_fixture, body):
    """
    The endpoint is configurable, so a proxy or a gateway can answer with
    valid JSON that is not Slack's. The clicker gets a message, not a 500.
    """

    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )
    answered = Mock()
    answered.json.return_value = body
    # The service streams the body in, so it can stop an endpoint
    # that sends more than this installation accepts.
    answered.iter_content.return_value = iter([b"{}"])

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=Mock(return_value=answered),
    ):
        with pytest.raises(ServiceImproperlyConfiguredDispatchException) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert "xoxb-test" not in str(raised.value)


def test_slack_write_message_does_not_log_what_the_request_carried():
    """
    The dispatch frame holds the bot token, and loguru prints frame locals
    beside a traceback. The HTTP service refuses to log its own exception for
    the same reason.
    """

    source = Path(service_types_module.__file__).read_text()

    assert "logger.exception(" not in source


def _streamed(body, chunks=None):
    """A response the service can pull in the way it pulls a real one."""

    answered = Mock()
    answered.json.return_value = body
    answered.iter_content.return_value = iter(
        chunks if chunks is not None else [json.dumps(body).encode()]
    )
    return answered


@pytest.mark.django_db
def test_slack_write_message_refuses_an_answer_past_the_ceiling(data_fixture, settings):
    """
    The endpoint is configurable, so its answer is not bounded by Slack's own
    limits. Buffering it whole and measuring afterwards spends the memory
    first.
    """

    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024
    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )
    flood = _streamed({"ok": True}, chunks=iter([b"x" * 512] * 10))

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=Mock(return_value=flood),
    ):
        with pytest.raises(ResponseTooLargeDispatchException):
            service.get_type().dispatch(service, FakeDispatchContext())


@pytest.mark.django_db
def test_slack_write_message_hangs_up_on_a_body_that_drips(data_fixture):
    """
    The request timeout restarts on every byte, so a server sending one every
    few seconds would hold the dispatch open past the lock that guards the
    row. The deadline is wall clock.
    """

    service = data_fixture.create_slack_write_message_service(
        integration=data_fixture.create_integration(
            SlackBotIntegration, token="xoxb-test"
        ),
        channel="general",
        text="'hi'",
    )

    def drip():
        yield b"{"
        # Past the service's own deadline, without ever going quiet.
        with patch("time.monotonic", return_value=time.monotonic() + 3600):
            yield b'"ok": true}'

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=Mock(return_value=_streamed({"ok": True}, chunks=drip())),
    ):
        with pytest.raises(UnexpectedDispatchException):
            service.get_type().dispatch(service, FakeDispatchContext())
