from django.urls import include, path

from .dashboard import urls as dashboard_urls
from .templates import urls as templates_urls
from .users import urls as users_urls
from .workspaces import urls as workspaces_urls

app_name = "baserow.api.admin"

urlpatterns = [
    path("dashboard/", include(dashboard_urls, namespace="dashboard")),
    path("templates/", include(templates_urls, namespace="templates")),
    path("users/", include(users_urls, namespace="users")),
    path("workspaces/", include(workspaces_urls, namespace="workspaces")),
]
