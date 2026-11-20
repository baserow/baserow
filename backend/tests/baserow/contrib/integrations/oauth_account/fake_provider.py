"""
A test-only OAuth provider, its integration type and a service type using it.
The model is in `fake_model`, see there.
"""

import base64
import json

from django.conf import settings

from baserow.contrib.integrations.oauth_account.exceptions import (
    AdminConsentRequired,
    OAuthFailed,
    TenantNotAllowed,
)
from baserow.contrib.integrations.oauth_account.integration_types import (
    OAuthAccountIntegrationDict,
    OAuthAccountIntegrationTypeMixin,
)
from baserow.contrib.integrations.oauth_account.providers import (
    AccountIdentity,
    OAuthClient,
    OAuthProvider,
)
from baserow.contrib.integrations.oauth_account.service_types import (
    OAuthAccountServiceTypeMixin,
    quote_path_segments,
)
from baserow.core.integrations.registries import IntegrationType
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType

FAKE_TYPE = "test_oauth"
FAKE_SERVICE_TYPE = "test_oauth_send_message"
ACCOUNT_ID = "account-alice"
TOKEN_ENDPOINT = "https://login.example.com/token"  # nosec B105
AUTHORIZE_ENDPOINT = "https://login.example.com/authorize"
API_URL = "https://api.example.com/v1"
PROVIDER_REQUEST = (
    "baserow.contrib.integrations.oauth_account.providers.send_http_request"
)
API_REQUEST = (
    "baserow.contrib.integrations.oauth_account.service_types.send_http_request"
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = b"" if payload is None else json.dumps(payload).encode()

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON")
        return self._payload


def make_id_token(**claims) -> str:
    def encode(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {
        "sub": ACCOUNT_ID,
        "email": "alice@example.com",
        "name": "Alice",
        "tenant": "contoso",
        **claims,
    }
    return f"{encode({'alg': 'none'})}.{encode(claims)}.signature"


def token_response(
    access_token="new-access",  # noqa: S107
    refresh_token="new-refresh",  # noqa: S107
    scope="openid email Profile.Read",
    id_token=True,
    **claims,
):
    payload = {
        "token_type": "Bearer",
        "access_token": access_token,
        "expires_in": 3600,
        "scope": scope,
    }
    if refresh_token:
        payload["refresh_token"] = refresh_token
    if id_token:
        payload["id_token"] = make_id_token(**claims)
    return FakeResponse(200, payload)


def token_error(error, status_code=400, **extra):
    return FakeResponse(status_code, {"error": error, **extra})


class FakeOAuthProvider(OAuthProvider):
    name = "Example"
    base_scopes = ["openid", "email", "Profile.Read"]
    scopes_case_sensitive = False

    def get_client(self, integration=None):
        if integration is not None and integration.own_client_id:
            return OAuthClient(integration.own_client_id, integration.own_client_secret)
        return self.get_instance_client()

    def get_instance_client(self):
        return OAuthClient(
            getattr(settings, "TEST_OAUTH_CLIENT_ID", "client-id"),
            getattr(settings, "TEST_OAUTH_CLIENT_SECRET", "client-secret"),
        )

    def get_authorization_endpoint(self, client):
        return AUTHORIZE_ENDPOINT

    def get_token_endpoint(self, client):
        return TOKEN_ENDPOINT

    def get_extra_authorization_params(self):
        return {"prompt": "select_account"}

    def get_extra_refresh_params(self, scopes):
        return {"scope": " ".join(self.normalize_scopes([*self.base_scopes, *scopes]))}

    def identify(self, client, token_set, deadline):
        claims = token_set.claims
        if not claims.get("sub"):
            raise OAuthFailed("Example didn't say which account signed in.")
        return AccountIdentity(
            account_id=str(claims["sub"]),
            email=str(claims.get("email", "")),
            name=str(claims.get("name", "")),
            extra={"tenant": str(claims.get("tenant", ""))[:64]},
        )

    def classify_callback_error(self, error, error_description, client, scopes):
        if "ADMIN_ONLY" in error_description:
            return AdminConsentRequired(self.admin_consent_url(client, scopes))
        if "TENANT_BLOCKED" in error_description:
            return TenantNotAllowed()
        return super().classify_callback_error(error, error_description, client, scopes)

    def admin_consent_url(self, client, scopes):
        return f"https://login.example.com/adminconsent?client_id={client.client_id}"


class FakeOAuthIntegrationType(OAuthAccountIntegrationTypeMixin, IntegrationType):
    type = FAKE_TYPE

    class SerializedDict(OAuthAccountIntegrationDict):
        tenant: str

    def __init__(self, model_class):
        self.model_class = model_class
        self.provider = FakeOAuthProvider()
        super().__init__()


class StubOAuthServiceType(OAuthAccountServiceTypeMixin, ServiceType):
    type = FAKE_SERVICE_TYPE
    model_class = Service
    integration_type = FAKE_TYPE
    required_scopes = ["Messages.Send"]
    permission_description = "send messages"

    def dispatch_data(self, service, resolved_values, dispatch_context):
        chat = resolved_values.get("chat", "c1")
        response = self.request_as_account(
            service,
            "POST",
            f"{API_URL}/{quote_path_segments('chats', chat, 'messages')}",
            json={"body": "hi"},
        )
        return response.json()
