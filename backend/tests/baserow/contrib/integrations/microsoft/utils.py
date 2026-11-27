import base64
import json

from ..oauth_account.fake_provider import FakeResponse

TENANT_ID = "11111111-1111-1111-1111-111111111111"
ACCOUNT_ID = "00000000-0000-0000-0000-00000000a11c"

PROVIDER_REQUEST = (
    "baserow.contrib.integrations.oauth_account.providers.send_http_request"
)
API_REQUEST = (
    "baserow.contrib.integrations.oauth_account.service_types.send_http_request"
)

MICROSOFT_SETTINGS = {
    "INTEGRATIONS_MICROSOFT_CLIENT_ID": "client-id",
    "INTEGRATIONS_MICROSOFT_CLIENT_SECRET": "client-secret",
    "INTEGRATIONS_MICROSOFT_TENANT": "common",
    "INTEGRATIONS_MICROSOFT_LOGIN_URL": "https://login.microsoftonline.com",
    "INTEGRATIONS_MICROSOFT_GRAPH_URL": "https://graph.microsoft.com",
}


def make_id_token(**claims) -> str:
    """An id token with the claims Microsoft sends."""

    def encode(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {
        "oid": ACCOUNT_ID,
        "tid": TENANT_ID,
        "preferred_username": "alice@contoso.com",
        "name": "Alice",
        **claims,
    }
    return f"{encode({'alg': 'none'})}.{encode(claims)}.signature"


def token_response(
    access_token="new-access",  # noqa: S107
    refresh_token="new-refresh",  # noqa: S107
    scope="openid profile email offline_access User.Read",
    **claims,
):
    return FakeResponse(
        200,
        {
            "token_type": "Bearer",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 3600,
            "scope": scope,
            "id_token": make_id_token(**claims),
        },
    )
