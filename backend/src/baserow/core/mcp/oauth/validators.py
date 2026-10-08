import re
from typing import Iterable

from oauth2_provider.oauth2_validators import OAuth2Validator

MCP_SCOPE = "mcp"
OFFLINE_ACCESS_SCOPE = "offline_access"
ENDPOINT_SCOPE_RE = re.compile(r"^endpoint:(\d+)$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def endpoint_scope(endpoint_id: int) -> str:
    return f"endpoint:{endpoint_id}"


def endpoint_id_from_scopes(scopes: Iterable[str]) -> int | None:
    for scope in scopes:
        match = ENDPOINT_SCOPE_RE.match(scope)
        if match:
            return int(match.group(1))
    return None


# Every token must come out of the consent page, so only the authorization code
# grant (and refreshing what it issued) is allowed, whatever the application says.
ALLOWED_GRANT_TYPES = {"authorization_code", "refresh_token"}
ALLOWED_RESPONSE_TYPES = {"code"}

# Set as a credential by the consent view when it issues the code, see `issue_code`.
CONSENT_CREDENTIAL = "mcp_endpoint_consent"


class MCPOAuth2Validator(OAuth2Validator):
    """
    Accepts the static `mcp` and `offline_access` scopes plus one `endpoint:<id>`
    scope. The endpoint scope is never requested by clients; only the consent view
    adds it when issuing the code. A refresh can only narrow the scopes of the grant
    it refreshes. A refresh token is only issued when `offline_access` is granted.
    """

    def validate_grant_type(
        self, client_id, grant_type, client, request, *args, **kwargs
    ):
        if grant_type not in ALLOWED_GRANT_TYPES:
            return False
        return super().validate_grant_type(
            client_id, grant_type, client, request, *args, **kwargs
        )

    def validate_response_type(
        self, client_id, response_type, client, request, *args, **kwargs
    ):
        if response_type not in ALLOWED_RESPONSE_TYPES:
            return False
        return super().validate_response_type(
            client_id, response_type, client, request, *args, **kwargs
        )

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        scopes = list(scopes)
        endpoint_scopes = [s for s in scopes if ENDPOINT_SCOPE_RE.match(s)]
        others = [s for s in scopes if not ENDPOINT_SCOPE_RE.match(s)]
        # Read from the instance attributes: request parameters are reachable through
        # `getattr` too, so a client could otherwise send the flag itself.
        consent = vars(request).get(CONSENT_CREDENTIAL) is True
        max_endpoint_scopes = 1 if consent else 0
        return len(endpoint_scopes) <= max_endpoint_scopes and set(others) <= {
            MCP_SCOPE,
            OFFLINE_ACCESS_SCOPE,
        }

    def _save_bearer_token(self, token, request, *args, **kwargs):
        # Refresh tokens are only issued for `offline_access`. The token dict is
        # also the response body, so the client gets none either. Refreshes are
        # left alone: without a new refresh token the old one would not be rotated.
        if (
            request.grant_type == "authorization_code"
            and OFFLINE_ACCESS_SCOPE not in token.get("scope", "").split()
        ):
            token.pop("refresh_token", None)
        return super()._save_bearer_token(token, request, *args, **kwargs)
