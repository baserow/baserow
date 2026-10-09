import re
from datetime import timedelta
from typing import Iterable

from django.utils import timezone

from oauth2_provider.models import get_application_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2.rfc6749.utils import scope_to_list

MCP_SCOPE = "mcp"
OFFLINE_ACCESS_SCOPE = "offline_access"
ENDPOINT_SCOPE_RE = re.compile(r"^endpoint:(\d+)$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
# How stale an application's `updated` may be before a token issue bumps it.
LAST_USED_RESOLUTION = timedelta(hours=1)


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
    it refreshes, and always keeps its endpoint scope. `offline_access` is accepted
    because some clients ask for it, but a refresh token is issued either way.
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

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        if not super().validate_refresh_token(
            refresh_token, client, request, *args, **kwargs
        ):
            return False
        # A refresh that asks for `scope=mcp` would otherwise get a token without the
        # endpoint scope: it wouldn't work on /mcp and Disconnect couldn't revoke it.
        # `request.scope` is still the raw string here, oauthlib parses it next.
        original = scope_to_list(self.get_original_scopes(refresh_token, request))
        endpoint_id = endpoint_id_from_scopes(original)
        if request.scope and endpoint_id is not None:
            requested = request.scope.split()
            if endpoint_scope(endpoint_id) not in requested:
                request.scope = " ".join([*requested, endpoint_scope(endpoint_id)])
        return True

    def _save_bearer_token(self, token, request, *args, **kwargs):
        result = super()._save_bearer_token(token, request, *args, **kwargs)
        # Marks the client as used, so the unused client cleanup keeps it. Only
        # bumped once an hour, so busy clients don't write on every refresh. Done
        # after saving the tokens so this, like the cleanup, locks tokens before
        # the application row.
        now = timezone.now()
        get_application_model().objects.filter(
            pk=request.client.pk, updated__lt=now - LAST_USED_RESOLUTION
        ).update(updated=now)
        return result
