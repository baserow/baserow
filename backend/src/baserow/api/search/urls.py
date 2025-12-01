from django.urls import path

from baserow.api.search.views import WorkspaceSearchView

app_name = "baserow.api.search"

urlpatterns = [
    path(
        "workspace/<int:workspace_id>/",
        WorkspaceSearchView.as_view(),
        name="workspace_search",
    ),
]
