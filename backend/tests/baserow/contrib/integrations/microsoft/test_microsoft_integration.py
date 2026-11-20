"""
The Microsoft integration through the shared OAuth account endpoints and
mixins. The shared behaviour itself is tested in `../oauth_account/`: these
tests show the Microsoft type is wired into it.
"""

from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.integrations.microsoft.models import (
    PERSONAL_ACCOUNT_TENANT_ID,
    MicrosoftIntegration,
)
from baserow.contrib.integrations.microsoft.service_types import (
    MicrosoftServiceTypeMixin,
    graph_url,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry

from ..oauth_account.fake_provider import FakeResponse
from .utils import (
    ACCOUNT_ID,
    API_REQUEST,
    MICROSOFT_SETTINGS,
    PROVIDER_REQUEST,
    TENANT_ID,
    token_response,
)


def oauth_url(name, **kwargs):
    return reverse(
        f"api:oauth_account:{name}",
        kwargs={"integration_type": "microsoft", **kwargs},
    )


def post(api_client, token, name, body=None, **kwargs):
    return api_client.post(
        oauth_url(name, **kwargs),
        body or {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


class StubTeamsServiceType(MicrosoftServiceTypeMixin, ServiceType):
    type = "test_microsoft_teams"
    model_class = Service
    required_scopes = ["ChannelMessage.Send", "ChatMessage.Send"]
    permission_description = "send Teams messages"

    def dispatch_data(self, service, resolved_values, dispatch_context):
        return self.graph_request(
            service, "POST", "chats", resolved_values["chat_id"], "messages"
        )


@contextmanager
def registered_teams_service_type():
    service_type = StubTeamsServiceType()
    service_type_registry.register(service_type)
    try:
        yield service_type
    finally:
        service_type_registry.unregister(service_type.type)


@pytest.mark.django_db
@override_settings(**MICROSOFT_SETTINGS, PUBLIC_WEB_FRONTEND_URL="https://b.io")
def test_signing_in_with_microsoft_creates_a_connected_integration(
    api_client, data_fixture, mocker
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    config = api_client.get(
        oauth_url("config"), HTTP_AUTHORIZATION=f"JWT {token}"
    ).json()
    assert config["configured"] is True
    assert (
        config["redirect_uri"] == "https://b.io/integrations/microsoft/oauth-callback"
    )

    response = post(api_client, token, "start", {"application_id": application.id})
    assert response.status_code == 200, response.json()
    url = urlparse(response.json()["authorization_url"])
    assert url.path == "/common/oauth2/v2.0/authorize"
    state = parse_qs(url.query)["state"][0]

    mocker.patch(PROVIDER_REQUEST, return_value=token_response())
    response = post(api_client, token, "complete", {"state": state, "code": "code"})

    assert response.status_code == 200, response.json()
    serialized = response.json()["integration"]
    assert serialized["type"] == "microsoft"
    assert serialized["name"] == "Microsoft (alice@contoso.com)"
    assert serialized["connected"] is True
    assert serialized["account_type"] == "work_or_school"
    assert "new-access" not in str(response.json())
    integration = MicrosoftIntegration.objects.get(id=serialized["id"])
    assert integration.account_id == ACCOUNT_ID
    assert integration.tenant_id == TENANT_ID
    assert integration.refresh_token == "new-refresh"  # nosec B105


@pytest.mark.django_db
def test_the_account_type_tells_personal_accounts_apart(data_fixture):
    work = data_fixture.create_microsoft_integration()
    personal = data_fixture.create_microsoft_integration(
        tenant_id=PERSONAL_ACCOUNT_TENANT_ID
    )
    never_connected = data_fixture.create_microsoft_integration(connected=False)

    assert work.account_type == "work_or_school"
    assert personal.is_personal_account is True
    assert personal.account_type == "personal"
    assert never_connected.account_type == ""


@pytest.mark.django_db
def test_exports_drop_the_account_and_tenant_and_duplicates_keep_them(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_microsoft_integration(
        application=builder, connected_by=user
    )
    integration_type = integration_type_registry.get("microsoft")

    exported = integration_type.export_serialized(
        integration,
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )
    assert exported["tenant_id"] is None
    assert exported["refresh_token"] is None

    clone = CoreHandler().duplicate_application(user, builder)
    copied = MicrosoftIntegration.objects.get(application=clone)
    assert copied.connected is True
    assert copied.tenant_id == integration.tenant_id


@pytest.mark.django_db
def test_a_member_leaving_disconnects_their_microsoft_integrations(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    integration = data_fixture.create_microsoft_integration(
        application=data_fixture.create_builder_application(workspace=workspace),
        connected_by=member,
    )

    CoreHandler().leave_workspace(member, workspace)

    integration.refresh_from_db()
    assert integration.connected is False
    # Who it was stays, so editors know whom to sign in as.
    assert integration.account_email == "alice@contoso.com"


def test_graph_urls_quote_each_segment():
    with override_settings(**MICROSOFT_SETTINGS):
        assert graph_url("chats", "19:a/b@thread.v2", "messages") == (
            "https://graph.microsoft.com/v1.0/chats/19%3Aa%2Fb%40thread.v2/messages"
        )
        with pytest.raises(ValueError):
            graph_url("teams", "..", "channels")


@pytest.mark.django_db
@override_settings(**MICROSOFT_SETTINGS)
def test_graph_requests_act_as_the_account_with_safe_errors(data_fixture, mocker):
    integration = data_fixture.create_microsoft_integration(
        scopes=["User.Read", "ChannelMessage.Send", "ChatMessage.Send"]
    )
    service = data_fixture.create_local_baserow_get_row_service(integration=integration)

    with registered_teams_service_type() as service_type:
        api = mocker.patch(API_REQUEST, return_value=FakeResponse(201, {"id": "m1"}))
        assert service_type.dispatch_data(service, {"chat_id": "c/1"}, None) == {
            "id": "m1"
        }
        sent = api.call_args.kwargs
        assert sent["url"] == "https://graph.microsoft.com/v1.0/chats/c%2F1/messages"
        assert sent["headers"]["Authorization"] == "Bearer access-token"

        with pytest.raises(ServiceImproperlyConfiguredDispatchException):
            service_type.dispatch_data(service, {"chat_id": ".."}, None)

        mocker.patch(
            API_REQUEST,
            return_value=FakeResponse(403, {"error": {"code": "Forbidden"}}),
        )
        with pytest.raises(RemoteRefusedDispatchException) as exc_info:
            service_type.dispatch_data(service, {"chat_id": "c1"}, None)
        assert "Microsoft" in str(exc_info.value)

        # Missing scopes name what the service needs.
        without_teams = data_fixture.create_local_baserow_get_row_service(
            integration=data_fixture.create_microsoft_integration()
        )
        with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
            service_type.dispatch_data(without_teams, {"chat_id": "c1"}, None)
        assert "send Teams messages" in str(exc_info.value)
