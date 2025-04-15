from django.urls import re_path

from .views import MCPEndpointsView, MCPEndpointView

app_name = "baserow.api.mcp"

urlpatterns = [
    re_path(r"^$", MCPEndpointsView.as_view(), name="list_endpoints"),
    re_path(r"^(?P<endpoint_id>[0-9]+)/$", MCPEndpointView.as_view(), name="endpoint"),
]
