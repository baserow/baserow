from django.urls import include, path

from oauth2_provider import urls as oauth2_urls
from oauth2_provider import views as oauth2_views

from .token_view import MCPTokenView
from .views import MCPAuthorizeRedirectView, MCPProtectedResourceMetadataView

oauth_patterns = [
    path("authorize/", MCPAuthorizeRedirectView.as_view(), name="authorize"),
    path("token/", MCPTokenView.as_view(), name="token"),
    path("revoke_token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]

# The library's resource metadata views take `scopes_supported` from `SCOPES`, which
# includes `offline_access`, so they are swapped for ones listing only `mcp`.
metadata_patterns = [
    pattern
    for pattern in oauth2_urls.metadata_urlpatterns
    if not pattern.name.startswith("oauth-resource-metadata")
] + [
    path(
        ".well-known/oauth-protected-resource",
        MCPProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource/<path:resource_path>",
        MCPProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata-path",
    ),
]

# One include with namespace "oauth2_provider": the metadata views reverse
# "oauth2_provider:<name>" to build endpoint URLs, and two includes with the same
# namespace would collide.
urlpatterns = [
    path(
        "",
        include(
            (
                metadata_patterns + [path("oauth/", include(oauth_patterns))],
                "oauth2_provider",
            )
        ),
    ),
]
