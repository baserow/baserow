import json

from baserow_enterprise.integrations.microsoft_teams.service_types import (
    MicrosoftTeamsWriteMessageServiceType,
)

GRAPH_REQUEST = (
    "baserow.contrib.integrations.oauth_account.service_types.send_http_request"
)
OAUTH_REQUEST = "baserow.contrib.integrations.oauth_account.providers.send_http_request"
PERSONAL_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"
TEAMS_SCOPES = [
    "openid",
    "profile",
    "email",
    "User.Read",
    *MicrosoftTeamsWriteMessageServiceType.required_scopes,
]
MICROSOFT_SETTINGS = {
    "INTEGRATIONS_MICROSOFT_CLIENT_ID": "client-id",
    "INTEGRATIONS_MICROSOFT_CLIENT_SECRET": "client-secret",
    "INTEGRATIONS_MICROSOFT_TENANT": "common",
    "INTEGRATIONS_MICROSOFT_LOGIN_URL": "https://login.microsoftonline.com",
    "INTEGRATIONS_MICROSOFT_GRAPH_URL": "https://graph.microsoft.com",
}


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


def create_teams_integration(data_fixture, **kwargs):
    kwargs.setdefault("scopes", TEAMS_SCOPES)
    return data_fixture.create_microsoft_integration(**kwargs)
