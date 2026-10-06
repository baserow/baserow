from django.urls import include, path

from oauth2_provider import urls as oauth2_urls
from oauth2_provider import views as oauth2_views

oauth_patterns = [
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke_token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
    *oauth2_urls.dcr_urlpatterns,
]

# One include with namespace "oauth2_provider": the metadata views reverse
# "oauth2_provider:<name>" to build endpoint URLs, and two includes with the same
# namespace would collide.
urlpatterns = [
    path(
        "",
        include(
            (
                oauth2_urls.metadata_urlpatterns
                + [path("oauth/", include(oauth_patterns))],
                "oauth2_provider",
            )
        ),
    ),
]
