from django.urls import include, path

from ..integrations.microsoft_teams.api import urls as microsoft_teams_urls
from .admin import urls as admin_urls
from .audit_log import urls as audit_log_urls
from .builder.custom_code import urls as custom_code_urls
from .data_sync import urls as data_sync_urls
from .field_permissions import urls as field_permissions_urls
from .role import urls as role_urls
from .secure_file_serve import urls as secure_file_serve_urls
from .teams import urls as teams_urls

app_name = "baserow_enterprise.api"

urlpatterns = [
    path("teams/", include(teams_urls, namespace="teams")),
    path(
        "integrations/microsoft-teams/",
        include(microsoft_teams_urls, namespace="microsoft_teams"),
    ),
    path("role/", include(role_urls, namespace="role")),
    path("admin/", include(admin_urls, namespace="admin")),
    path("audit-log/", include(audit_log_urls, namespace="audit_log")),
    path("files/", include(secure_file_serve_urls, namespace="files")),
    path("data-sync/", include(data_sync_urls, namespace="data_sync")),
    path(
        "field-permissions/",
        include(field_permissions_urls, namespace="field_permissions"),
    ),
    path(
        "custom_code/",
        include(custom_code_urls, namespace="custom_code"),
    ),
    path(
        "builder/preview/",
        include(
            (
                custom_code_urls.preview_urlpatterns,
                custom_code_urls.app_name,
            ),
            namespace="builder_preview_custom_code",
        ),
    ),
]
