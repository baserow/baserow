from django.urls import re_path

from .views import (
    TeamInvitationLinksView,
    TeamInvitationLinkView,
    TeamInvitationsView,
    TeamInvitationView,
    TeamSubjectsView,
    TeamSubjectView,
    TeamsView,
    TeamView,
)

app_name = "baserow_enterprise.api.teams"

urlpatterns = [
    re_path(r"(?P<team_id>[0-9]+)/$", TeamView.as_view(), name="item"),
    re_path(
        r"(?P<team_id>[0-9]+)/subjects/$",
        TeamSubjectsView.as_view(),
        name="subject-list",
    ),
    re_path(
        r"(?P<team_id>[0-9]+)/subjects/(?P<subject_id>[0-9]+)/$",
        TeamSubjectView.as_view(),
        name="subject-detail",
    ),
    re_path(
        r"(?P<team_id>[0-9]+)/invitations/$",
        TeamInvitationsView.as_view(),
        name="invitation-list",
    ),
    re_path(
        r"(?P<team_id>[0-9]+)/invitations/(?P<team_invitation_id>[0-9]+)/$",
        TeamInvitationView.as_view(),
        name="invitation-detail",
    ),
    re_path(
        r"(?P<team_id>[0-9]+)/invitation-links/$",
        TeamInvitationLinksView.as_view(),
        name="invitation-link-list",
    ),
    re_path(
        r"(?P<team_id>[0-9]+)/invitation-links/(?P<invitation_link_id>[0-9]+)/$",
        TeamInvitationLinkView.as_view(),
        name="invitation-link-detail",
    ),
    re_path(r"workspace/(?P<workspace_id>[0-9]+)/$", TeamsView.as_view(), name="list"),
]
