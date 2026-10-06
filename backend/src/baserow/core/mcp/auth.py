import hashlib

from django.conf import settings

from asgiref.sync import sync_to_async

from baserow.core.mcp.models import MCPEndpoint

INVALID_TOKEN = "invalid_token"
INSUFFICIENT_SCOPE = "insufficient_scope"


def www_authenticate(error: str | None = None) -> str:
    """
    The `WWW-Authenticate` header value for a rejected `/mcp` request. It points MCP
    clients at the protected resource metadata so they can start the OAuth flow.
    """

    metadata = f"{settings.PUBLIC_BACKEND_URL}/.well-known/oauth-protected-resource/mcp"
    value = f'Bearer resource_metadata="{metadata}"'
    if error == INSUFFICIENT_SCOPE:
        value += f', error="{INSUFFICIENT_SCOPE}", scope="mcp"'
    elif error:
        value += f', error="{error}"'
    return value


def _resolve_oauth_token(value: str):
    """
    Returns `(endpoint, error)` for an OAuth access token, or `None` if `value` is
    not a known access token. Revoked tokens are deleted by django-oauth-toolkit, so
    they are not found.
    """

    from oauth2_provider.models import AccessToken

    from baserow.core.mcp.oauth.validators import endpoint_id_from_scopes

    checksum = hashlib.sha256(value.encode("utf-8")).hexdigest()
    token = AccessToken.objects.filter(token_checksum=checksum).first()
    if token is None:
        return None
    # `allows_audience` accepts tokens without any resource, so require the MCP
    # resource explicitly.
    if token.is_expired() or settings.MCP_RESOURCE_URL not in (token.resource or []):
        return None, INVALID_TOKEN
    endpoint_id = endpoint_id_from_scopes(token.scope.split())
    if endpoint_id is None:
        return None, INSUFFICIENT_SCOPE
    endpoint = MCPEndpoint.objects.filter(id=endpoint_id, user_id=token.user_id).first()
    if endpoint is None:
        return None, INVALID_TOKEN
    return endpoint, None


def _resolve_bearer_sync(value: str):
    if settings.BASEROW_MCP_OAUTH_ENABLED:
        result = _resolve_oauth_token(value)
        if result is not None:
            return result

    # OAuth grants' endpoints only accept their OAuth tokens, never their key.
    endpoint = MCPEndpoint.objects.filter(
        key=value, oauth_client_id__isnull=True
    ).first()
    if endpoint is None:
        return None, INVALID_TOKEN
    return endpoint, None


async def resolve_bearer(value: str) -> tuple[MCPEndpoint | None, str | None]:
    """
    Resolves a bearer value to an MCP endpoint. The value is either an OAuth access
    token (when `BASEROW_MCP_OAUTH_ENABLED`) or an endpoint key. Returns the endpoint
    and `None`, or `None` and an error code (`invalid_token` or
    `insufficient_scope`). Workspace membership is checked separately by
    `BaserowMCPServer.get_endpoint()`.
    """

    return await sync_to_async(_resolve_bearer_sync)(value)
