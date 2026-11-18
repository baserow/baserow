from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.actions import JoinWorkspaceViaInvitationLinkActionType
from baserow.core.exceptions import (
    FeatureDisabledException,
    PermissionDenied,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkSignupsDisabled,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitationLink, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.handler import UserHandler
from baserow_enterprise.exceptions import ScopeNotExist
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.actions import (
    CreateTeamInvitationLinkActionType,
    DeleteTeamInvitationLinkActionType,
    UpdateTeamInvitationLinkActionType,
)
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import TeamSubject
from baserow_enterprise.teams.operations import CreateTeamSubjectOperationType
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def role(uid):
    return Role.objects.get(uid=uid)


def setup_workspace(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, user=admin)
    team = TeamHandler().create_team(
        admin, "Sales", workspace, default_role=role("EDITOR")
    )
    other_team = TeamHandler().create_team(
        admin, "Support", workspace, default_role=role("VIEWER")
    )
    return admin, workspace, table, team, other_team


def add_member(data_fixture, workspace, permissions):
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions=permissions
    )
    return member


def team_member_ids(team):
    return list(
        TeamSubject.objects.filter(team=team).values_list("subject_id", flat=True)
    )


def can_read_table(user, workspace, table):
    try:
        CoreHandler().check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table,
        )
    except PermissionDenied:
        return False
    return True


@pytest.mark.django_db
def test_create_team_invitation_link_has_no_role_of_its_own(data_fixture):
    admin, workspace, _, team, other_team = setup_workspace(data_fixture)

    invitation_link = TeamHandler().create_team_invitation_link(admin, team, "Fair")
    other_link = TeamHandler().create_team_invitation_link(admin, other_team)

    assert invitation_link.scope == team
    assert invitation_link.workspace == workspace
    assert invitation_link.created_by == admin
    assert invitation_link.name == "Fair"
    assert invitation_link.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert list(TeamHandler().list_team_invitation_links(admin, team)) == [
        invitation_link
    ]
    assert list(TeamHandler().list_team_invitation_links(admin, other_team)) == [
        other_link
    ]
    # Links to a team aren't workspace links nor links that give a role.
    assert list(CoreHandler().list_workspace_invitation_links(admin, workspace)) == []
    assert list(
        RoleAssignmentHandler().get_scoped_invitation_links(workspace, team)
    ) == [invitation_link]
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        TeamHandler().get_team_invitation_link(invitation_link.id, other_team)


@pytest.mark.django_db
def test_only_who_can_add_team_members_and_create_links_manages_team_links(
    data_fixture,
):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    builder = add_member(data_fixture, workspace, "BUILDER")
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)
    handler = TeamHandler()

    with pytest.raises(PermissionDenied):
        handler.create_team_invitation_link(builder, team)
    with pytest.raises(PermissionDenied):
        handler.list_team_invitation_links(builder, team)
    with pytest.raises(PermissionDenied):
        handler.update_team_invitation_link(builder, team, invitation_link, "New")
    with pytest.raises(PermissionDenied):
        handler.delete_team_invitation_link(builder, team, invitation_link)

    # Adding members to the team alone isn't enough, because a link also brings
    # newcomers into the workspace.
    def only_add_team_members(user, operation, **kwargs):
        if operation != CreateTeamSubjectOperationType.type:
            raise PermissionDenied()

    with patch.object(
        CoreHandler, "check_permissions", side_effect=only_add_team_members
    ):
        with pytest.raises(PermissionDenied):
            handler.create_team_invitation_link(builder, team)

    assert WorkspaceInvitationLink.objects.count() == 1


@pytest.mark.django_db
def test_team_links_require_feature_flag_signups_and_teams(data_fixture, settings):
    admin, _, _, team, _ = setup_workspace(data_fixture)

    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        TeamHandler().create_team_invitation_link(admin, team)
    with pytest.raises(FeatureDisabledException):
        TeamHandler().list_team_invitation_links(admin, team)

    settings.FEATURE_FLAGS = "*"
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )
    with pytest.raises(WorkspaceInvitationLinkSignupsDisabled):
        TeamHandler().create_team_invitation_link(admin, team)

    data_fixture.update_settings(allow_new_signups=True)
    with patch.object(
        LicenseHandler,
        "raise_if_user_doesnt_have_feature",
        side_effect=FeaturesNotAvailableError(),
    ):
        with pytest.raises(FeaturesNotAvailableError):
            TeamHandler().create_team_invitation_link(admin, team)

    assert WorkspaceInvitationLink.objects.count() == 0


@pytest.mark.django_db
def test_newcomer_joins_through_team_link_and_gets_the_team_role(data_fixture):
    admin, workspace, table, team, other_team = setup_workspace(data_fixture)
    newcomer = data_fixture.create_user()
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)

    workspace_user = CoreHandler().join_workspace_via_invitation_link(
        newcomer, invitation_link
    )

    assert workspace_user.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert team_member_ids(team) == [newcomer.id]
    assert team_member_ids(other_team) == []
    assert can_read_table(newcomer, workspace, table)


@pytest.mark.django_db
def test_signing_up_through_a_team_link(data_fixture):
    admin, workspace, table, team, _ = setup_workspace(data_fixture)
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)

    user = UserHandler().create_user(
        "Newcomer",
        "newcomer@example.com",
        "password",
        workspace_invitation_link_slug=invitation_link.slug,
    )

    assert (
        WorkspaceUser.objects.get(user=user, workspace=workspace).permissions
        == NO_ROLE_LOW_PRIORITY_ROLE_UID
    )
    assert team_member_ids(team) == [user.id]
    assert can_read_table(user, workspace, table)


@pytest.mark.django_db
def test_member_outside_the_team_joins_it_and_keeps_their_role(data_fixture):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, "VIEWER")
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)
    handler = CoreHandler()

    assert handler.invitation_link_adds_member(member, invitation_link)
    assert (
        handler.get_permissions_raised_by_invitation_link(member, invitation_link)
        is None
    )

    workspace_user = handler.join_workspace_via_invitation_link(member, invitation_link)

    assert workspace_user.permissions == "VIEWER"
    assert team_member_ids(team) == [member.id]
    assert not handler.invitation_link_adds_member(member, invitation_link)


@pytest.mark.django_db
def test_team_member_joining_again_changes_nothing(data_fixture):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    TeamHandler().create_subject(admin, {"id": member.id}, "auth.User", team)
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)

    assert not CoreHandler().invitation_link_adds_member(member, invitation_link)

    CoreHandler().join_workspace_via_invitation_link(member, invitation_link)
    CoreHandler().join_workspace_via_invitation_link(member, invitation_link)

    assert team_member_ids(team) == [member.id]


@pytest.mark.django_db
def test_team_link_cannot_be_used_once_team_is_trashed_or_teams_are_lost(
    data_fixture,
):
    admin, workspace, _, team, other_team = setup_workspace(data_fixture)
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)
    other_link = TeamHandler().create_team_invitation_link(admin, other_team)
    handler = CoreHandler()

    assert handler.get_workspace_invitation_link_by_slug(invitation_link.slug)

    with patch.object(LicenseHandler, "workspace_has_feature", return_value=False):
        with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
            handler.get_workspace_invitation_link_by_slug(invitation_link.slug)

    TrashHandler.trash(admin, workspace, None, team)
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        handler.get_workspace_invitation_link_by_slug(invitation_link.slug)

    TrashHandler.restore_item(admin, "team", team.id)
    assert handler.get_workspace_invitation_link_by_slug(invitation_link.slug)

    TrashHandler.trash(admin, workspace, None, team)
    TrashHandler.permanently_delete(team)
    assert not WorkspaceInvitationLink.objects.filter(id=invitation_link.id).exists()
    assert WorkspaceInvitationLink.objects.filter(id=other_link.id).exists()


@pytest.mark.django_db
def test_people_who_joined_stay_in_the_team_when_the_link_is_deleted(data_fixture):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    newcomer = data_fixture.create_user()
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)
    CoreHandler().join_workspace_via_invitation_link(newcomer, invitation_link)

    TeamHandler().update_team_invitation_link(admin, team, invitation_link, "Fair")
    assert WorkspaceInvitationLink.objects.get(id=invitation_link.id).name == "Fair"

    TeamHandler().delete_team_invitation_link(admin, team, invitation_link)

    assert not WorkspaceInvitationLink.objects.filter(id=invitation_link.id).exists()
    assert team_member_ids(team) == [newcomer.id]


@pytest.mark.django_db
@patch("baserow.core.action.signals.action_done.send")
def test_team_link_actions_are_recorded(action_done_mock, data_fixture):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, "EDITOR")
    newcomer = data_fixture.create_user()

    invitation_link = CreateTeamInvitationLinkActionType.do(admin, team, "Fair")
    UpdateTeamInvitationLinkActionType.do(admin, team, invitation_link, "Partners")
    JoinWorkspaceViaInvitationLinkActionType.do(newcomer, invitation_link)
    JoinWorkspaceViaInvitationLinkActionType.do(member, invitation_link)
    # Already in the team, so nothing changes and nothing is recorded.
    JoinWorkspaceViaInvitationLinkActionType.do(member, invitation_link)
    invitation_link_id = invitation_link.id
    DeleteTeamInvitationLinkActionType.do(admin, team, invitation_link)

    calls = [call.kwargs for call in action_done_mock.call_args_list]
    assert [call["action_type"] for call in calls] == [
        CreateTeamInvitationLinkActionType,
        UpdateTeamInvitationLinkActionType,
        JoinWorkspaceViaInvitationLinkActionType,
        JoinWorkspaceViaInvitationLinkActionType,
        DeleteTeamInvitationLinkActionType,
    ]
    assert [calls[2]["user"], calls[3]["user"]] == [newcomer, member]
    assert UpdateTeamInvitationLinkActionType.get_long_description(
        calls[1]["action_params"]
    ) == (
        f'Invitation link ({invitation_link_id}) renamed from "Fair" to "Partners" '
        f'in team "Sales" ({team.id}) '
    )
    assert calls[2]["action_params"]["scope_type_name"] == "team"
    assert calls[2]["action_params"]["scope_id"] == team.id


@pytest.mark.django_db
def test_manage_team_links_through_the_api(api_client, data_fixture):
    admin, workspace, _, team, other_team = setup_workspace(data_fixture)
    token = data_fixture.generate_token(admin)
    list_url = reverse(
        "api:enterprise:teams:invitation-link-list", kwargs={"team_id": team.id}
    )

    response = api_client.post(
        list_url,
        {"name": "Fair", "permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    invitation_link = WorkspaceInvitationLink.objects.get(id=data["id"])
    assert data == {
        "id": invitation_link.id,
        "workspace": workspace.id,
        "team_id": team.id,
        "name": "Fair",
        "slug": invitation_link.slug,
        "created_on": data["created_on"],
    }
    # A link to a team never stores the role that may be sent along.
    assert invitation_link.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID

    response = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert [link["id"] for link in response.json()] == [invitation_link.id]

    detail_url = reverse(
        "api:enterprise:teams:invitation-link-detail",
        kwargs={"team_id": team.id, "invitation_link_id": invitation_link.id},
    )
    response = api_client.patch(
        detail_url,
        {"name": "Partners"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "Partners"

    response = api_client.patch(
        detail_url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    # The link can't be reached through another team.
    response = api_client.delete(
        reverse(
            "api:enterprise:teams:invitation-link-detail",
            kwargs={
                "team_id": other_team.id,
                "invitation_link_id": invitation_link.id,
            },
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"

    response = api_client.delete(detail_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not WorkspaceInvitationLink.objects.filter(id=invitation_link.id).exists()


@pytest.mark.django_db
def test_team_links_api_refuses_others_and_unknown_teams(
    api_client, data_fixture, settings
):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    builder = add_member(data_fixture, workspace, "BUILDER")
    outsider = data_fixture.create_user()
    list_url = reverse(
        "api:enterprise:teams:invitation-link-list", kwargs={"team_id": team.id}
    )

    response = api_client.get(list_url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        list_url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(builder)}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.get(
        list_url, HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(outsider)}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:enterprise:teams:invitation-link-list", kwargs={"team_id": 0}),
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(admin)}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEAM_DOES_NOT_EXIST"

    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )
    response = api_client.post(
        list_url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(admin)}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED"
    )

    settings.FEATURE_FLAGS = []
    response = api_client.get(
        list_url, HTTP_AUTHORIZATION=f"JWT {data_fixture.generate_token(admin)}"
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.django_db
def test_role_link_endpoints_refuse_team_links(data_fixture):
    admin, _, _, team, _ = setup_workspace(data_fixture)
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)

    with pytest.raises(ScopeNotExist):
        RoleAssignmentHandler().update_scoped_invitation_link(
            admin, invitation_link, name="New"
        )
    with pytest.raises(ScopeNotExist):
        RoleAssignmentHandler().delete_scoped_invitation_link(admin, invitation_link)


@pytest.mark.django_db
def test_open_and_join_team_link_through_the_api(api_client, data_fixture):
    admin, workspace, _, team, _ = setup_workspace(data_fixture)
    member = add_member(data_fixture, workspace, "VIEWER")
    invitation_link = TeamHandler().create_team_invitation_link(admin, team)
    token = data_fixture.generate_token(member)
    slug_url = reverse(
        "api:workspaces:invitation_links:slug", kwargs={"slug": invitation_link.slug}
    )

    response = api_client.get(slug_url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["scope_type"] == "team"
    assert response.json()["scope_id"] == team.id
    assert response.json()["scope_name"] == "Sales"
    assert response.json()["role_upgrade"] is None
    assert response.json()["adds_member"] is False

    response = api_client.get(slug_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json()["role_upgrade"] is None
    assert response.json()["adds_member"] is True

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:join",
            kwargs={"slug": invitation_link.slug},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "VIEWER"
    assert team_member_ids(team) == [member.id]

    response = api_client.get(slug_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.json()["adds_member"] is False
