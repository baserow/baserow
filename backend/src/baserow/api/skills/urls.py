from django.urls import path

from .views import WorkspaceSkillsView, WorkspaceSkillView

app_name = "baserow.api.skills"

urlpatterns = [
    path(
        "workspace/<int:workspace_id>/",
        WorkspaceSkillsView.as_view(),
        name="workspace",
    ),
    path("<int:skill_id>/", WorkspaceSkillView.as_view(), name="item"),
]
