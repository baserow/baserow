import hashlib

from django.conf import settings

from asgiref.sync import sync_to_async

from baserow.core.mcp.models import MCPEndpoint

INVALID_TOKEN = "invalid_token"
INSUFFICIENT_SCOPE = "insufficient_scope"


def www_authenticate(error: str | None = None) -> str:
    """
    The `WWW-Authenticate` header value for a rejected `/mcp` request. With OAuth on,
    it points MCP clients at the protected resource metadata so they can start the
    OAuth flow. With it off, that metadata isn't served, so it isn't mentioned.
    """

    params = []
    if settings.BASEROW_MCP_OAUTH_ENABLED:
        metadata = (
            f"{settings.MCP_AUTHORIZATION_SERVER_URL}"
            "/.well-known/oauth-protected-resource/mcp"
        )
        params.append(f'resource_metadata="{metadata}"')
    if error == INSUFFICIENT_SCOPE:
        params += [f'error="{INSUFFICIENT_SCOPE}"', 'scope="mcp"']
    elif error:
        params.append(f'error="{error}"')
    return "Bearer " + ", ".join(params) if params else "Bearer"


def _load_member_endpoint(**lookup) -> MCPEndpoint | None:
    """
    The endpoint with its user and workspace loaded, or None when it doesn't exist
    or its user is no longer an active member of its workspace.
    """

    from baserow.core.subjects import UserSubjectType

    endpoint = (
        MCPEndpoint.objects.select_related("user", "user__profile", "workspace")
        .filter(**lookup)
        .first()
    )
    if endpoint is None:
        return None
    if not UserSubjectType().is_in_workspace(endpoint.user, endpoint.workspace):
        return None
    return endpoint


def _resolve_oauth_token(value: str):
    """
    Returns `(endpoint, error)` for an OAuth access token, or `None` if `value` is
    not a known access token. Revoked tokens are deleted by django-oauth-toolkit, so
    they are not found.
    """

    from oauth2_provider.models import AccessToken

    from baserow.core.mcp.oauth.validators import endpoint_id_from_scopes

    checksum = hashlib.sha256(value.encode("utf-8")).hexdigest()
    token = (
        AccessToken.objects.select_related("application")
        .filter(token_checksum=checksum)
        .first()
    )
    if token is None:
        return None
    # `allows_audience` accepts tokens without any resource, so require the MCP
    # resource explicitly.
    if token.is_expired() or settings.MCP_RESOURCE_URL not in (token.resource or []):
        return None, INVALID_TOKEN
    endpoint_id = endpoint_id_from_scopes(token.scope.split())
    if endpoint_id is None:
        return None, INSUFFICIENT_SCOPE
    # The scope is only trusted for a grant of the client the token was issued to,
    # so a token without a client matches no grant.
    if token.application_id is None:
        return None, INVALID_TOKEN
    endpoint = _load_member_endpoint(
        id=endpoint_id,
        user_id=token.user_id,
        oauth_client_id=token.application.client_id,
    )
    if endpoint is None:
        return None, INVALID_TOKEN
    return endpoint, None


def _resolve_bearer_sync(value: str):
    if settings.BASEROW_MCP_OAUTH_ENABLED:
        result = _resolve_oauth_token(value)
        if result is not None:
            return result

    endpoint = _load_member_endpoint(key=value)
    if endpoint is None:
        return None, INVALID_TOKEN
    return endpoint, None


async def resolve_bearer(value: str) -> tuple[MCPEndpoint | None, str | None]:
    """
    Resolves a bearer value to an MCP endpoint. The value is either an OAuth access
    token (when `BASEROW_MCP_OAUTH_ENABLED`) or an endpoint key. Returns the endpoint
    and `None`, or `None` and an error code (`invalid_token` or
    `insufficient_scope`). The endpoint is returned only while its user is a member
    of its workspace.
    """

    return await sync_to_async(_resolve_bearer_sync)(value)
