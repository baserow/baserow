from django.urls import re_path

from .oauth_views import (
    MCPOAuthConnectionsView,
    MCPOAuthConnectionView,
    MCPOAuthConsentView,
)
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
    re_path(
        r"^oauth/connections/$",
        MCPOAuthConnectionsView.as_view(),
        name="oauth_connections",
    ),
    re_path(
        r"^oauth/connections/(?P<connection_id>[0-9]+)/$",
        MCPOAuthConnectionView.as_view(),
        name="oauth_connection",
    ),
]
