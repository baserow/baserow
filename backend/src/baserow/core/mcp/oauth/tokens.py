from oauth2_provider.models import AccessToken, RefreshToken


def revoke_endpoint_tokens(endpoint_id: int) -> None:
    """
    Deletes every OAuth access and refresh token bound to the given MCP endpoint.
    The scope is matched as a whole space-separated word so `endpoint:1` never
    matches `endpoint:12`.
    """

    pattern = rf"(^| )endpoint:{int(endpoint_id)}( |$)"
    access_ids = list(
        AccessToken.objects.filter(scope__regex=pattern).values_list("id", flat=True)
    )
    RefreshToken.objects.filter(access_token_id__in=access_ids).delete()
    AccessToken.objects.filter(id__in=access_ids).delete()
