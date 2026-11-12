import re
from datetime import timedelta
from typing import Iterable
from urllib.parse import urlparse

from django.utils import timezone

from oauth2_provider.models import get_application_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from oauthlib.oauth2.rfc6749.utils import scope_to_list

from baserow.core.user.identity import is_human

MCP_SCOPE = "mcp"
OFFLINE_ACCESS_SCOPE = "offline_access"
ENDPOINT_SCOPE_RE = re.compile(r"^endpoint:(\d+)$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
# How stale an application's `updated` may be before a token issue bumps it.
LAST_USED_RESOLUTION = timedelta(hours=1)


def is_allowed_redirect_uri(uri) -> bool:
    """https anywhere, or http to a loopback address."""

    # DOT stores the URIs space-joined and splits them on any whitespace, so a
    # URI containing whitespace would be stored as several.
    if not isinstance(uri, str) or uri.split() != [uri]:
        return False
    parsed = urlparse(uri)
    if parsed.scheme == "https":
        return bool(parsed.hostname)
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS


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


class RefreshTokenAlreadyUsed(InvalidGrantError):
    """
    Raised while saving tokens, after oauthlib has set the response headers, so
    it brings the headers of a token endpoint error response itself.
    """

    description = "The refresh token was already used."

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        }


class MCPOAuth2Validator(OAuth2Validator):
    """
    Accepts the static `mcp` and `offline_access` scopes plus one `endpoint:<id>`
    scope. The endpoint scope is never requested by clients; only the consent view
    adds it when issuing the code. A refresh can only narrow the scopes of the grant
    it refreshes, and always keeps its `mcp` and endpoint scopes. `offline_access`
    is accepted because some clients ask for it, but a refresh token is issued
    either way.
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
        if not is_human(request.user):
            return False
        # A refresh that narrows the scopes would otherwise get a token without
        # `mcp` or the endpoint scope, so it wouldn't work on /mcp, and without the
        # endpoint scope Disconnect couldn't revoke it. Both are added back.
        # `request.scope` is still the raw string here, oauthlib parses it next.
        original = scope_to_list(self.get_original_scopes(refresh_token, request))
        endpoint_id = endpoint_id_from_scopes(original)
        if request.scope and endpoint_id is not None:
            requested = request.scope.split()
            kept = [MCP_SCOPE, endpoint_scope(endpoint_id)]
            missing = [s for s in kept if s in original and s not in requested]
            request.scope = " ".join([*requested, *missing])
        return True

    def _save_bearer_token(self, token, request, *args, **kwargs):
        result = super()._save_bearer_token(token, request, *args, **kwargs)
        # A refresh that lost a race with another one using the same token gets
        # the tokens that one issued, but only their hashes are stored, so the
        # library hands back a blank token.
        if not token.get("access_token"):
            raise RefreshTokenAlreadyUsed(request=request)
        # Marks the client as used, so the unused client cleanup keeps it. Only
        # bumped once an hour, so busy clients don't write on every refresh. Done
        # after saving the tokens so this, like the cleanup, locks tokens before
        # the application row.
        now = timezone.now()
        get_application_model().objects.filter(
            pk=request.client.pk, updated__lt=now - LAST_USED_RESOLUTION
        ).update(updated=now)
        return result
