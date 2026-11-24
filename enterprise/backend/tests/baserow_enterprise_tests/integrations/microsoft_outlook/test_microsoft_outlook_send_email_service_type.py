from unittest.mock import ANY

from django.shortcuts import reverse
from django.test import override_settings

import pytest
from requests import exceptions as request_exceptions
from rest_framework.status import HTTP_200_OK

from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.builder.workflow_actions.models import (
    MicrosoftOutlookSendEmailWorkflowAction,
)
from baserow_enterprise.integrations.microsoft_outlook.service_types import (
    MicrosoftOutlookSendEmailServiceType,
)
from baserow_enterprise_tests.integrations.microsoft_teams.utils import (
    GRAPH_REQUEST,
    MICROSOFT_SETTINGS,
    OAUTH_REQUEST,
    PERSONAL_TENANT_ID,
    FakeResponse,
)

GRAPH = "https://graph.microsoft.com/v1.0"
OUTLOOK_SCOPES = [
    "openid",
    "profile",
    "email",
    "User.Read",
    *MicrosoftOutlookSendEmailServiceType.required_scopes,
]

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("enterprise"),
]


@pytest.fixture
def enterprise(enterprise_data_fixture):
    with override_settings(DEBUG=True, **MICROSOFT_SETTINGS):
        enterprise_data_fixture.enable_enterprise()
        yield


def create_outlook_integration(data_fixture, **kwargs):
    kwargs.setdefault("scopes", OUTLOOK_SCOPES)
    return data_fixture.create_microsoft_integration(**kwargs)


def create_service(data_fixture, integration=None, **kwargs):
    if integration is None:
        integration = create_outlook_integration(data_fixture)
    kwargs.setdefault("to_emails", "'bob@example.com'")
    kwargs.setdefault("subject", "'Hello'")
    kwargs.setdefault("body", "'Hi Bob'")
    return data_fixture.create_microsoft_outlook_send_email_service(
        integration=integration, **kwargs
    )


def dispatch(service):
    return service.get_type().dispatch(
        service,
        FakeDispatchContext(workspace=service.integration.application.workspace),
    )


def test_send_an_email(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture,
        to_emails="'bob@example.com, carol@example.com'",
        cc_emails="'dave@example.com'",
        bcc_emails="'erin@example.com'",
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    result = dispatch(service)

    request.assert_called_once_with(
        method="POST",
        url=f"{GRAPH}/me/sendMail",
        headers={"Authorization": "Bearer access-token"},
        json={
            "message": {
                "subject": "Hello",
                "body": {"contentType": "Text", "content": "Hi Bob"},
                "toRecipients": [
                    {"emailAddress": {"address": "bob@example.com"}},
                    {"emailAddress": {"address": "carol@example.com"}},
                ],
                "ccRecipients": [{"emailAddress": {"address": "dave@example.com"}}],
                "bccRecipients": [{"emailAddress": {"address": "erin@example.com"}}],
            },
            "saveToSentItems": True,
        },
        deadline=ANY,
        operation_timeout=10,
        allow_redirects=False,
        send_netrc_credentials=False,
    )
    assert result.data == {
        "submitted": True,
        "submitted_at": ANY,
        "from_email": "alice@contoso.com",
        "to_emails": ["bob@example.com", "carol@example.com"],
        "cc_emails": ["dave@example.com"],
        "bcc_emails": ["erin@example.com"],
        "subject": "Hello",
    }


def test_an_html_body_is_sent_as_html(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture, body_type="html", body="'<p>Hi <b>Bob</b></p>'"
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    dispatch(service)

    message = request.call_args.kwargs["json"]["message"]
    assert message["body"] == {
        "contentType": "HTML",
        "content": "<p>Hi <b>Bob</b></p>",
    }


def test_empty_cc_and_bcc_are_left_out(enterprise_data_fixture, mocker):
    service = create_service(enterprise_data_fixture, cc_emails="", bcc_emails="''")
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    dispatch(service)

    message = request.call_args.kwargs["json"]["message"]
    assert "ccRecipients" not in message
    assert "bccRecipients" not in message


def test_recipients_from_a_list(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture,
        to_emails="split('bob@example.com;carol@example.com', ';')",
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    result = dispatch(service)

    assert request.call_args.kwargs["json"]["message"]["toRecipients"] == [
        {"emailAddress": {"address": "bob@example.com"}},
        {"emailAddress": {"address": "carol@example.com"}},
    ]
    assert result.data["to_emails"] == ["bob@example.com", "carol@example.com"]


@pytest.mark.parametrize(
    "values",
    [
        {"to_emails": "'not an email'"},
        {"to_emails": "'bob@example.com, nope'"},
        {"cc_emails": "'nope'"},
        {"bcc_emails": "'bob@'"},
    ],
)
def test_an_invalid_recipient_is_refused(enterprise_data_fixture, mocker, values):
    service = create_service(enterprise_data_fixture, **values)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(InvalidContextContentDispatchException):
        dispatch(service)
    request.assert_not_called()


def test_no_recipient_is_refused(enterprise_data_fixture, mocker):
    service = create_service(enterprise_data_fixture, to_emails="''")
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(
        InvalidContextContentDispatchException, match="At least one recipient"
    ):
        dispatch(service)
    request.assert_not_called()


def test_a_personal_account_can_send(enterprise_data_fixture, mocker):
    integration = create_outlook_integration(
        enterprise_data_fixture,
        tenant_id=PERSONAL_TENANT_ID,
        account_email="alice@outlook.com",
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    result = dispatch(service)

    assert request.call_count == 1
    assert result.data["from_email"] == "alice@outlook.com"


def test_missing_mail_permission_is_refused(enterprise_data_fixture, mocker):
    integration = create_outlook_integration(
        enterprise_data_fixture, scopes=["openid", "profile", "email", "User.Read"]
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="send email"
    ):
        dispatch(service)
    request.assert_not_called()


def test_a_disconnected_account_is_refused(enterprise_data_fixture, mocker):
    integration = enterprise_data_fixture.create_microsoft_integration(connected=False)
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException, match="Reconnect"):
        dispatch(service)
    request.assert_not_called()


def test_an_integration_of_another_type_is_refused(enterprise_data_fixture, mocker):
    integration = enterprise_data_fixture.create_slack_bot_integration(token="x")
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        dispatch(service)
    request.assert_not_called()


@pytest.mark.parametrize(
    "status_code,code,exception,message",
    [
        (400, "ErrorInvalidRecipients", RemoteRefusedDispatchException, "recipient"),
        (400, "ErrorInvalidRequest", RemoteRefusedDispatchException, "malformed"),
        (400, "", RemoteRefusedDispatchException, r"malformed or too large \(400\)"),
        (413, "", RemoteRefusedDispatchException, "too large"),
        (403, "ErrorAccessDenied", RemoteRefusedDispatchException, "isn't allowed"),
        (403, "ErrorSendAsDenied", RemoteRefusedDispatchException, "isn't allowed"),
        (
            404,
            "MailboxNotEnabledForRESTAPI",
            RemoteRefusedDispatchException,
            "Exchange Online mailbox",
        ),
        (
            403,
            "ErrorMessageSubmissionBlocked",
            RemoteRefusedDispatchException,
            "blocked",
        ),
        (
            400,
            "ErrorMessageSubmissionBlocked",
            RemoteRefusedDispatchException,
            "blocked",
        ),
        (429, "", RemoteBusyDispatchException, "sending limit"),
        (
            403,
            "ErrorExceededMessageLimit",
            RemoteBusyDispatchException,
            "sending limit",
        ),
        (
            400,
            "ErrorExceededMessageLimit",
            RemoteBusyDispatchException,
            "sending limit",
        ),
        (503, "", RemoteBusyDispatchException, "again later"),
        (504, "", RemoteBusyDispatchException, "again later"),
        (500, "InternalServerError", RemoteRefusedDispatchException, "Internal"),
    ],
)
def test_graph_errors(
    enterprise_data_fixture, mocker, status_code, code, exception, message
):
    service = create_service(enterprise_data_fixture)
    payload = (
        {"error": {"code": code, "message": "Hello bob@example.com"}} if code else None
    )
    mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(status_code, payload, {"Retry-After": "5"}),
    )

    with pytest.raises(exception, match=message) as exc_info:
        dispatch(service)
    # Graph's own message can repeat what was sent, so it's never shown.
    assert "bob@example.com" not in str(exc_info.value)


def test_a_token_refused_twice_asks_to_reconnect(enterprise_data_fixture, mocker):
    service = create_service(enterprise_data_fixture)
    graph = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(401))
    mocker.patch(
        OAUTH_REQUEST,
        return_value=FakeResponse(
            200,
            {
                "token_type": "Bearer",
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
        ),
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException, match="Reconnect"):
        dispatch(service)
    assert graph.call_count == 2
    assert graph.call_args.kwargs["headers"] == {"Authorization": "Bearer new-access"}


def test_a_network_failure_is_a_runtime_error(enterprise_data_fixture, mocker):
    service = create_service(enterprise_data_fixture)
    mocker.patch(
        GRAPH_REQUEST, side_effect=request_exceptions.ConnectTimeout("bob@example.com")
    )

    with pytest.raises(RuntimeDispatchException) as exc_info:
        dispatch(service)
    assert "bob@example.com" not in str(exc_info.value)


def test_the_schema_describes_the_output(enterprise_data_fixture):
    service = create_service(enterprise_data_fixture)
    service_type = service.get_type()

    schema = service_type.generate_schema(service)

    assert set(schema["properties"]) == {
        "submitted",
        "submitted_at",
        "from_email",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
    }
    # Outlook gives no message id.
    assert "message_id" not in schema["properties"]
    assert list(service_type.generate_schema(service, ["submitted"])["properties"]) == [
        "submitted"
    ]


def test_export_and_import(enterprise_data_fixture):
    service = create_service(
        enterprise_data_fixture,
        cc_emails="'carol@example.com'",
        bcc_emails="'dave@example.com'",
        body_type="html",
    )
    service_type = service.get_type()

    serialized = service_type.export_serialized(service)
    imported = service_type.import_serialized(
        None, serialized, {}, import_formula=lambda formula, _: formula
    )

    assert imported.id != service.id
    for field in [
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body",
        "body_type",
    ]:
        assert getattr(imported, field) == getattr(service, field), field


def test_an_export_without_sensitive_data_leaves_out_the_email(
    enterprise_data_fixture,
):
    service = create_service(enterprise_data_fixture, body_type="html")

    serialized = service.get_type().export_serialized(
        service,
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )

    for field in ["to_emails", "cc_emails", "bcc_emails", "subject", "body"]:
        assert serialized[field] is None, field
    assert serialized["body_type"] == "html"


def test_configuration_errors(enterprise_data_fixture):
    service_type = service_type_registry.get("microsoft_outlook_send_email")
    without_recipient = create_service(enterprise_data_fixture, to_emails="")
    complete = create_service(enterprise_data_fixture)

    assert service_type.get_configuration_errors(without_recipient) == {
        "to_emails": "required"
    }
    assert service_type.get_configuration_errors(complete) == {}


def test_dispatch_from_a_builder_button(api_client, enterprise_data_fixture, mocker):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    integration = create_outlook_integration(
        enterprise_data_fixture, application=page.builder
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    workflow_action = MicrosoftOutlookSendEmailWorkflowAction.objects.create(
        page=page, element=element, event=EventTypes.CLICK, service=service, order=0
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    response = api_client.post(
        reverse(
            "api:builder:workflow_action:dispatch",
            kwargs={"workflow_action_id": workflow_action.id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert request.call_count == 1


def test_dispatch_from_an_automation_node(enterprise_data_fixture, mocker):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE
    )
    integration = create_outlook_integration(
        enterprise_data_fixture, application=workflow.automation
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    node = enterprise_data_fixture.create_automation_node(
        workflow=workflow, type="microsoft_outlook_send_email", service=service
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(202))

    result = node.get_type().dispatch(
        node, FakeDispatchContext(workspace=workflow.automation.workspace)
    )

    assert request.call_count == 1
    assert result.data["submitted"] is True


def test_the_editor_sees_the_permission_outlook_needs(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    integration = create_outlook_integration(
        enterprise_data_fixture,
        application=page.builder,
        # Granted for Teams only.
        scopes=["User.Read", "ChannelMessage.Send", "ChatMessage.Send"],
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    MicrosoftOutlookSendEmailWorkflowAction.objects.create(
        page=page, element=element, event=EventTypes.CLICK, service=service, order=0
    )

    response = api_client.get(
        reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    [workflow_action] = response.json()
    # The frontend compares it with the integration's granted `scopes`.
    assert workflow_action["service"]["required_scopes"] == ["Mail.Send"]
    assert workflow_action["service"]["body_type"] == "plain"
