from django.urls import re_path

from .views import (
    BatchRoleAssignmentsView,
    RoleAssignmentsView,
    ScopedInvitationsView,
    ScopedInvitationView,
)

app_name = "baserow_enterprise.api.role"

urlpatterns = [
    re_path(
        r"^(?P<workspace_id>[0-9]+)/$",
        RoleAssignmentsView.as_view(),
        name="list",
    ),
    re_path(
        r"^(?P<workspace_id>[0-9]+)/batch/$",
        BatchRoleAssignmentsView.as_view(),
        name="batch",
    ),
    re_path(
        r"^(?P<workspace_id>[0-9]+)/invitations/$",
        ScopedInvitationsView.as_view(),
        name="scoped_invitations",
    ),
    re_path(
        r"^invitations/(?P<scoped_invitation_id>[0-9]+)/$",
        ScopedInvitationView.as_view(),
        name="scoped_invitation",
    ),
]
