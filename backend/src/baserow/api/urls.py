from django.urls import include, path

from drf_spectacular.views import SpectacularRedocView

from baserow.core.registries import (
    application_type_registry,
    auth_provider_type_registry,
    plugin_registry,
)
from baserow.core.services.registries import service_type_registry

from .admin import urls as admin_urls
from .applications import urls as application_urls
from .auth_provider import urls as auth_provider_urls
from .health import urls as health_urls
from .integrations import urls as integrations_urls
from .jobs import urls as jobs_urls
from .mcp import urls as mcp_urls
from .notifications import urls as notifications_urls
from .search import urls as search_urls
from .settings import urls as settings_urls
from .snapshots import urls as snapshots_urls
from .spectacular.views import CachedSpectacularJSONAPIView
from .templates import urls as templates_urls
from .trash import urls as trash_urls
from .two_factor_auth import urls as two_factor_urls
from .user import urls as user_urls
from .user_files import urls as user_files_urls
from .user_sources import urls as user_source_urls
from .workspaces import urls as workspace_urls

app_name = "baserow.api"


urlpatterns = (
    [
        path("schema.json", CachedSpectacularJSONAPIView.as_view(), name="json_schema"),
        path(
            "redoc/",
            SpectacularRedocView.as_view(url_name="api:json_schema"),
            name="redoc",
        ),
        path("settings/", include(settings_urls, namespace="settings")),
        path("auth-provider/", include(auth_provider_urls, namespace="auth_provider")),
        path("two-factor-auth/", include(two_factor_urls, namespace="two_factor_auth")),
        path("user/", include(user_urls, namespace="user")),
        path("user-files/", include(user_files_urls, namespace="user_files")),
        path("workspaces/", include(workspace_urls, namespace="workspaces")),
        path("templates/", include(templates_urls, namespace="templates")),
        path("applications/", include(application_urls, namespace="applications")),
        path("trash/", include(trash_urls, namespace="trash")),
        path("jobs/", include(jobs_urls, namespace="jobs")),
        path("snapshots/", include(snapshots_urls, namespace="snapshots")),
        path("_health/", include(health_urls, namespace="health")),
        path("notifications/", include(notifications_urls, namespace="notifications")),
        path("search/", include(search_urls, namespace="search")),
        path("admin/", include(admin_urls, namespace="admin")),
        path("mcp/", include(mcp_urls, namespace="mcp")),
        path(
            "",
            include(integrations_urls, namespace="integrations"),
        ),
        path(
            "",
            include(user_source_urls, namespace="user_sources"),
        ),
    ]
    + application_type_registry.api_urls
    + auth_provider_type_registry.api_urls
    + plugin_registry.api_urls
    + service_type_registry.api_urls
)
