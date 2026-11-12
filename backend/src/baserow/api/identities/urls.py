from django.urls import path

from baserow.api.identities.views import IdentityView, WorkspaceIdentitiesView

app_name = "baserow.api.identities"

urlpatterns = [
    path(
        "workspace/<int:workspace_id>/",
        WorkspaceIdentitiesView.as_view(),
        name="workspace",
    ),
    path("<int:identity_id>/", IdentityView.as_view(), name="item"),
]
