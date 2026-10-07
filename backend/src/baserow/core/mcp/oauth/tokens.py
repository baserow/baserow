from oauth2_provider.models import AccessToken, RefreshToken

from baserow.core.mcp.models import MCPEndpoint


def revoke_endpoint_tokens(endpoint: MCPEndpoint) -> None:
    """
    Deletes every OAuth access and refresh token bound to the given grant. Endpoints
    without an OAuth client never have tokens. The scope is matched as a whole
    space-separated word so `endpoint:1` never matches `endpoint:12`.
    """

    if endpoint.oauth_client_id is None:
        return
    pattern = rf"(^| )endpoint:{int(endpoint.id)}( |$)"
    access_ids = list(
        AccessToken.objects.filter(
            user_id=endpoint.user_id,
            application__client_id=endpoint.oauth_client_id,
            scope__regex=pattern,
        ).values_list("id", flat=True)
    )
    RefreshToken.objects.filter(access_token_id__in=access_ids).delete()
    AccessToken.objects.filter(id__in=access_ids).delete()
