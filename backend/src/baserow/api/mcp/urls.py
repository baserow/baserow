from django.urls import re_path

from .oauth_views import MCPOAuthConsentView
from .views import MCPEndpointsView, MCPEndpointView

app_name = "baserow.api.mcp"

urlpatterns = [
    re_path(r"^endpoints/$", MCPEndpointsView.as_view(), name="list_endpoints"),
    re_path(
        r"^endpoint/(?P<endpoint_id>[0-9]+)/$",
        MCPEndpointView.as_view(),
        name="endpoint",
    ),
    re_path(r"^oauth/consent/$", MCPOAuthConsentView.as_view(), name="oauth_consent"),
]
