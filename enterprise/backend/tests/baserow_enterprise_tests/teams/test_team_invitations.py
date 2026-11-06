from unittest.mock import patch

import pytest

from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.exceptions import PermissionDenied, WorkspaceUserAlreadyExists
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitation, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.handler import UserHandler
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.exceptions import TeamInvitationDoesNotExist
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import TeamSubject, WorkspaceTeamInvitation
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def setup_workspace(data_fixture, enterprise_data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team_a = TeamHandler().create_team(
        user, "Sales", workspace, default_role=Role.objects.get(uid="VIEWER")
    )
    team_b = enterprise_data_fixture.create_team(workspace=workspace)
    return user, workspace, team_a, team_b


def team_member_ids(team):
    return list(
        TeamSubject.objects.filter(team=team).values_list("subject_id", flat=True)
    )


@pytest.mark.django_db
def test_create_team_invitation_creates_invitation_without_workspace_role(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)

    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        team_invitation = TeamHandler().create_team_invitation(
            user, team_a, "Foo@Bar.com"
        )

    invitation = team_invitation.invitation
    send_email.assert_called_once_with(invitation)
    assert invitation.workspace == workspace
    assert invitation.email == "foo@bar.com"
    assert invitation.invited_by == user
    assert invitation.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert team_invitation.team == team_a


@pytest.mark.django_db
def test_create_team_invitation_reuses_invitation_for_another_team(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, team_b = setup_workspace(
        data_fixture, enterprise_data_fixture
    )
    handler = TeamHandler()

    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        first = handler.create_team_invitation(user, team_a, "foo@bar.com")
        second = handler.create_team_invitation(user, team_b, "foo@bar.com")
        # Inviting again to the same team sends the email again, without adding
        # another row.
        again = handler.create_team_invitation(user, team_a, "foo@bar.com")

    assert first.invitation_id == second.invitation_id
    assert again.id == first.id
    assert WorkspaceInvitation.objects.count() == 1
    assert WorkspaceTeamInvitation.objects.count() == 2
    assert send_email.call_count == 3


@pytest.mark.django_db
def test_create_team_invitation_keeps_existing_workspace_role(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace,
        invited_by=user,
        email="foo@bar.com",
        permissions="EDITOR",
    )

    team_invitation = TeamHandler().create_team_invitation(user, team_a, "foo@bar.com")

    assert team_invitation.invitation_id == invitation.id
    invitation.refresh_from_db()
    assert invitation.permissions == "EDITOR"


@pytest.mark.django_db
def test_create_team_invitation_checks_permissions(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    builder = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=builder, permissions="BUILDER"
    )

    with pytest.raises(PermissionDenied):
        TeamHandler().create_team_invitation(builder, team_a, "foo@bar.com")

    assert WorkspaceInvitation.objects.count() == 0


@pytest.mark.django_db
def test_create_team_invitation_requires_license(data_fixture, enterprise_data_fixture):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        TeamHandler().create_team_invitation(user, team_a, "foo@bar.com")


@pytest.mark.django_db
def test_create_team_invitation_for_existing_member_fails(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    member = data_fixture.create_user(email="member@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="VIEWER"
    )

    with pytest.raises(WorkspaceUserAlreadyExists):
        TeamHandler().create_team_invitation(user, team_a, "member@bar.com")

    assert WorkspaceTeamInvitation.objects.count() == 0


@pytest.mark.django_db
def test_accepting_invitation_adds_invitee_to_teams_with_the_team_role(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, team_b = setup_workspace(
        data_fixture, enterprise_data_fixture
    )
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=workspace),
        user=user,
    )
    handler = TeamHandler()
    team_invitation = handler.create_team_invitation(user, team_a, "foo@bar.com")
    handler.create_team_invitation(user, team_b, "foo@bar.com")
    invitee = data_fixture.create_user(email="foo@bar.com", email_verified=True)

    CoreHandler().accept_workspace_invitation(invitee, team_invitation.invitation)

    workspace_user = WorkspaceUser.objects.get(workspace=workspace, user=invitee)
    assert workspace_user.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert team_member_ids(team_a) == [invitee.id]
    assert team_member_ids(team_b) == [invitee.id]
    # The invitation and its teams are gone once accepted.
    assert WorkspaceInvitation.objects.count() == 0
    assert WorkspaceTeamInvitation.objects.count() == 0

    # The invitee has no workspace role of their own, so the role of the team
    # applies.
    assert (
        CoreHandler().check_permissions(
            invitee,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table,
            raise_permission_exceptions=False,
        )
        is True
    )


@pytest.mark.django_db
def test_accepting_invitation_skips_trashed_team_and_existing_membership(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, team_b = setup_workspace(
        data_fixture, enterprise_data_fixture
    )
    team_c = enterprise_data_fixture.create_team(workspace=workspace)
    handler = TeamHandler()
    team_invitation = handler.create_team_invitation(user, team_a, "foo@bar.com")
    handler.create_team_invitation(user, team_b, "foo@bar.com")
    handler.create_team_invitation(user, team_c, "foo@bar.com")
    TrashHandler.trash(user, workspace, None, team_b)
    invitee = data_fixture.create_user(email="foo@bar.com", email_verified=True)
    enterprise_data_fixture.create_subject(team=team_c, subject=invitee)

    CoreHandler().accept_workspace_invitation(invitee, team_invitation.invitation)

    assert WorkspaceUser.objects.filter(workspace=workspace, user=invitee).exists()
    assert team_member_ids(team_a) == [invitee.id]
    assert TeamSubject.objects_and_trash.filter(team=team_b).count() == 0
    assert team_member_ids(team_c) == [invitee.id]


@pytest.mark.django_db
def test_accepting_invitation_without_teams_feature_still_joins_workspace(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    team_invitation = TeamHandler().create_team_invitation(user, team_a, "foo@bar.com")
    enterprise_data_fixture.delete_all_licenses()
    invitee = data_fixture.create_user(email="foo@bar.com", email_verified=True)

    CoreHandler().accept_workspace_invitation(invitee, team_invitation.invitation)

    assert WorkspaceUser.objects.filter(workspace=workspace, user=invitee).exists()
    assert team_member_ids(team_a) == []


@pytest.mark.django_db
def test_signup_with_invitation_token_adds_invitee_to_team(
    data_fixture, enterprise_data_fixture
):
    user, workspace, team_a, _ = setup_workspace(data_fixture, enterprise_data_fixture)
    team_invitation = TeamHandler().create_team_invitation(user, team_a, "foo@bar.com")
    token = (
        CoreHandler()
        .get_workspace_invitation_signer()
        .dumps(team_invitation.invitation_id)
    )

    invitee = UserHandler().create_user(
        "Foo", "foo@bar.com", "password", workspace_invitation_token=token
    )

    assert team_member_ids(team_a) == [invitee.id]
    assert (
        WorkspaceUser.objects.get(workspace=workspace, user=invitee).permissions
        == NO_ROLE_LOW_PRIORITY_ROLE_UID
    )
    assert RoleAssignmentHandler().get_current_role_assignment(
        team_a, workspace
    ).role.uid == ("VIEWER")


@pytest.mark.django_db
def test_list_and_delete_team_invitations(data_fixture, enterprise_data_fixture):
    user, workspace, team_a, team_b = setup_workspace(
        data_fixture, enterprise_data_fixture
    )
    builder = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=builder, permissions="BUILDER"
    )
    handler = TeamHandler()
    first = handler.create_team_invitation(user, team_a, "foo@bar.com")
    second = handler.create_team_invitation(user, team_b, "foo@bar.com")
    other = handler.create_team_invitation(user, team_a, "other@bar.com")

    assert list(handler.list_team_invitations(user, team_a)) == [first, other]
    # The invitations hold email addresses, which only who can list the
    # invitations of the workspace may see.
    with pytest.raises(PermissionDenied):
        handler.list_team_invitations(builder, team_a)

    with pytest.raises(TeamInvitationDoesNotExist):
        handler.get_team_invitation(second.id, team_a)
    assert handler.get_team_invitation(first.id, team_a) == first

    with pytest.raises(PermissionDenied):
        handler.delete_team_invitation(builder, first)

    handler.delete_team_invitation(user, first)

    # Only the team is revoked, the invitation and its other team remain.
    assert WorkspaceInvitation.objects.filter(id=first.invitation_id).exists()
    assert list(handler.list_team_invitations(user, team_a)) == [other]
    assert list(handler.list_team_invitations(user, team_b)) == [second]


@pytest.mark.django_db
def test_deleting_team_deletes_its_invitations(data_fixture, enterprise_data_fixture):
    user, workspace, team_a, team_b = setup_workspace(
        data_fixture, enterprise_data_fixture
    )
    handler = TeamHandler()
    first = handler.create_team_invitation(user, team_a, "foo@bar.com")
    handler.create_team_invitation(user, team_b, "foo@bar.com")

    team_b.delete()

    assert list(WorkspaceTeamInvitation.objects.all()) == [first]
    assert WorkspaceInvitation.objects.filter(id=first.invitation_id).exists()
