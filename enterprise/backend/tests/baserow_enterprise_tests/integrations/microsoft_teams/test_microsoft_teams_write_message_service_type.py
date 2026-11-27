from unittest.mock import ANY

from django.shortcuts import reverse
from django.test import override_settings

import pytest
from requests import exceptions as request_exceptions
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.core.services.exceptions import (
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.builder.workflow_actions.models import (
    MicrosoftTeamsWriteMessageWorkflowAction,
)
from baserow_enterprise.integrations.microsoft_teams.service_types import (
    message_to_html,
)

from .utils import (
    GRAPH_REQUEST,
    MICROSOFT_SETTINGS,
    OAUTH_REQUEST,
    PERSONAL_TENANT_ID,
    FakeResponse,
    create_teams_integration,
)

GRAPH = "https://graph.microsoft.com/v1.0"
SENT = {
    "id": "1616990032035",
    "createdDateTime": "2026-11-20T12:00:00.000Z",
    "webUrl": "https://teams.microsoft.com/l/message/1616990032035",
    "body": {"contentType": "html", "content": "Hello"},
}

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("enterprise"),
]


@pytest.fixture
def enterprise(enterprise_data_fixture):
    with override_settings(DEBUG=True, **MICROSOFT_SETTINGS):
        enterprise_data_fixture.enable_enterprise()
        yield


def create_service(data_fixture, integration=None, **kwargs):
    if integration is None:
        integration = create_teams_integration(data_fixture)
    kwargs.setdefault("destination_type", "channel")
    kwargs.setdefault("team_id", "'team-1'")
    kwargs.setdefault("channel_id", "'19:general@thread.tacv2'")
    kwargs.setdefault("message", "'Hello'")
    return data_fixture.create_microsoft_teams_write_message_service(
        integration=integration, **kwargs
    )


def dispatch(service):
    return service.get_type().dispatch(
        service,
        FakeDispatchContext(workspace=service.integration.application.workspace),
    )


def test_message_to_html_escapes_markup_and_keeps_line_breaks():
    assert message_to_html('<b>Hi</b> & "you"\nLine 2\r\nLine 3') == (
        "&lt;b&gt;Hi&lt;/b&gt; &amp; &quot;you&quot;<br>Line 2<br>Line 3"
    )


def test_send_to_a_channel(enterprise_data_fixture, mocker):
    service = create_service(enterprise_data_fixture)
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(201, SENT))

    result = dispatch(service)

    request.assert_called_once_with(
        method="POST",
        url=f"{GRAPH}/teams/team-1/channels/19%3Ageneral%40thread.tacv2/messages",
        headers={"Authorization": "Bearer access-token"},
        json={"body": {"contentType": "html", "content": "Hello"}},
        deadline=ANY,
        operation_timeout=10,
        allow_redirects=False,
        send_netrc_credentials=False,
    )
    assert result.data == {
        "message_id": "1616990032035",
        "created_at": "2026-11-20T12:00:00.000Z",
        "web_url": "https://teams.microsoft.com/l/message/1616990032035",
        "destination_type": "channel",
        "team_id": "team-1",
        "channel_id": "19:general@thread.tacv2",
        "chat_id": "",
    }


def test_send_to_a_chat_ignores_the_channel(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture,
        destination_type="chat",
        chat_id="'19:abc_def@unq.gbl.spaces'",
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(201, SENT))

    result = dispatch(service)

    assert request.call_args.kwargs["url"] == (
        f"{GRAPH}/chats/19%3Aabc_def%40unq.gbl.spaces/messages"
    )
    assert result.data["destination_type"] == "chat"
    assert result.data["chat_id"] == "19:abc_def@unq.gbl.spaces"
    assert result.data["team_id"] == ""
    assert result.data["channel_id"] == ""


def test_an_id_stays_one_path_segment(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture,
        destination_type="chat",
        chat_id="'../me/sendMail?x=1#'",
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(201, SENT))

    dispatch(service)

    assert request.call_args.kwargs["url"] == (
        f"{GRAPH}/chats/..%2Fme%2FsendMail%3Fx%3D1%23/messages"
    )


@pytest.mark.parametrize("chat_id", ["'..'", "'.'"])
def test_a_dot_id_is_refused(enterprise_data_fixture, mocker, chat_id):
    service = create_service(
        enterprise_data_fixture, destination_type="chat", chat_id=chat_id
    )
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        dispatch(service)
    request.assert_not_called()


def test_the_message_is_sent_escaped(enterprise_data_fixture, mocker):
    service = create_service(
        enterprise_data_fixture, message="'<img src=x onerror=alert(1)> & hi'"
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(201, SENT))

    dispatch(service)

    assert request.call_args.kwargs["json"]["body"] == {
        "contentType": "html",
        "content": "&lt;img src=x onerror=alert(1)&gt; &amp; hi",
    }


@pytest.mark.parametrize(
    "values,message",
    [
        ({"team_id": "''"}, "Choose the team"),
        ({"channel_id": "''"}, "Choose the channel"),
        ({"destination_type": "chat", "chat_id": "''"}, "Choose the chat"),
        ({"message": "'  '"}, "The message is empty."),
    ],
)
def test_a_missing_destination_or_message_is_refused(
    enterprise_data_fixture, mocker, values, message
):
    service = create_service(enterprise_data_fixture, **values)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException, match=message):
        dispatch(service)
    request.assert_not_called()


def test_a_personal_account_is_refused(enterprise_data_fixture, mocker):
    integration = create_teams_integration(
        enterprise_data_fixture, tenant_id=PERSONAL_TENANT_ID
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="work or school"
    ):
        dispatch(service)
    request.assert_not_called()


def test_missing_teams_permissions_are_refused(enterprise_data_fixture, mocker):
    integration = create_teams_integration(
        enterprise_data_fixture, scopes=["openid", "profile", "email", "User.Read"]
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    request = mocker.patch(GRAPH_REQUEST)

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="send Teams messages"
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
    "status_code,payload,exception,message",
    [
        (403, None, RemoteRefusedDispatchException, "can't post in this channel"),
        (404, None, RemoteRefusedDispatchException, "wasn't found"),
        (429, None, RemoteBusyDispatchException, "again later"),
        (503, None, RemoteBusyDispatchException, "again later"),
        (504, None, RemoteBusyDispatchException, "again later"),
        (
            400,
            {"error": {"code": "BadRequest", "message": "Hello is not allowed"}},
            RemoteRefusedDispatchException,
            "BadRequest",
        ),
        (
            413,
            {"error": {"code": "RequestEntityTooLarge", "message": "Hello"}},
            RemoteRefusedDispatchException,
            "RequestEntityTooLarge",
        ),
    ],
)
def test_graph_errors(
    enterprise_data_fixture, mocker, status_code, payload, exception, message
):
    service = create_service(enterprise_data_fixture)
    mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(status_code, payload, {"Retry-After": "5"}),
    )

    with pytest.raises(exception, match=message) as exc_info:
        dispatch(service)
    # Graph's own message can repeat what was sent, so it's never shown.
    assert "Hello" not in str(exc_info.value)


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
    mocker.patch(GRAPH_REQUEST, side_effect=request_exceptions.ConnectTimeout("Hello"))

    with pytest.raises(RuntimeDispatchException) as exc_info:
        dispatch(service)
    assert "Hello" not in str(exc_info.value)


def test_the_schema_describes_the_output(enterprise_data_fixture):
    service = create_service(enterprise_data_fixture)
    service_type = service.get_type()

    schema = service_type.generate_schema(service)

    assert set(schema["properties"]) == {
        "message_id",
        "created_at",
        "web_url",
        "destination_type",
        "team_id",
        "channel_id",
        "chat_id",
    }
    assert list(
        service_type.generate_schema(service, ["message_id"])["properties"]
    ) == ["message_id"]


def test_configuration_errors(enterprise_data_fixture):
    service_type = service_type_registry.get("microsoft_teams_write_message")
    channel = create_service(enterprise_data_fixture, team_id="", message="")
    chat = create_service(enterprise_data_fixture, destination_type="chat")

    assert service_type.get_configuration_errors(channel) == {
        "team_id": "required",
        "message": "required",
    }
    assert service_type.get_configuration_errors(chat) == {"chat_id": "required"}


def test_dispatch_from_a_builder_button(api_client, enterprise_data_fixture, mocker):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    integration = create_teams_integration(
        enterprise_data_fixture, application=page.builder
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    workflow_action = MicrosoftTeamsWriteMessageWorkflowAction.objects.create(
        page=page, element=element, event=EventTypes.CLICK, service=service, order=0
    )
    request = mocker.patch(GRAPH_REQUEST, return_value=FakeResponse(201, SENT))

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


@pytest.mark.django_db
def test_the_editor_sees_the_permissions_teams_needs(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    integration = create_teams_integration(
        enterprise_data_fixture,
        application=page.builder,
        scopes=["User.Read", "ChannelMessage.Send"],
    )
    service = create_service(enterprise_data_fixture, integration=integration)
    MicrosoftTeamsWriteMessageWorkflowAction.objects.create(
        page=page, element=element, event=EventTypes.CLICK, service=service, order=0
    )

    response = api_client.get(
        reverse("api:builder:workflow_action:list", kwargs={"page_id": page.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    [workflow_action] = response.json()
    # The frontend compares them with the integration's granted `scopes`.
    assert workflow_action["service"]["required_scopes"] == [
        "Channel.ReadBasic.All",
        "ChannelMessage.Send",
        "Chat.ReadBasic",
        "ChatMessage.Send",
        "Team.ReadBasic.All",
    ]
