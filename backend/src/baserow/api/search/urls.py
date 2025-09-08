from django.urls import path

from baserow.api.search.views import WorkspaceSearchView
from baserow.core.feature_flags import FF_WORKSPACE_SEARCH, feature_flag_is_enabled

app_name = "baserow.api.search"

urlpatterns = []

if feature_flag_is_enabled(FF_WORKSPACE_SEARCH):
    urlpatterns = [
        path(
            "workspace/<int:workspace_id>/",
            WorkspaceSearchView.as_view(),
            name="workspace_search",
        ),
    ]
