from django.urls import re_path

from .views import (
    JoinWorkspaceInvitationLinkView,
    PublicWorkspaceInvitationLinkView,
    WorkspaceInvitationLinksView,
    WorkspaceInvitationLinkView,
)

app_name = "baserow.api.workspaces.invitation_links"


urlpatterns = [
    re_path(
        r"workspace/(?P<workspace_id>[0-9]+)/$",
        WorkspaceInvitationLinksView.as_view(),
        name="list",
    ),
    re_path(
        r"slug/(?P<slug>[-\w]+)/$",
        PublicWorkspaceInvitationLinkView.as_view(),
        name="slug",
    ),
    re_path(
        r"slug/(?P<slug>[-\w]+)/join/$",
        JoinWorkspaceInvitationLinkView.as_view(),
        name="join",
    ),
    re_path(
        r"(?P<invitation_link_id>[0-9]+)/$",
        WorkspaceInvitationLinkView.as_view(),
        name="item",
    ),
]
