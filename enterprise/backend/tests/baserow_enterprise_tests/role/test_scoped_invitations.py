from unittest.mock import patch

import pytest

from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.exceptions import PermissionDenied, WorkspaceUserAlreadyExists
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitation, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.handler import UserHandler
from baserow_enterprise.exceptions import ScopedInvitationDoesNotExist, ScopeNotExist
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import (
    Role,
    RoleAssignment,
    WorkspaceScopedInvitation,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError

BASE_URL = "http://localhost:3000/invite"


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def setup_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_a = data_fixture.create_database_table(database=database, user=user)
    table_b = data_fixture.create_database_table(database=database, user=user)
    return user, workspace, database, table_a, table_b


def role(uid):
    return Role.objects.get(uid=uid)


@pytest.mark.django_db
def test_create_scoped_invitation_creates_invitation_without_workspace_role(
    data_fixture,
):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)

    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        scoped_invitation = RoleAssignmentHandler().create_scoped_invitation(
            user, workspace, "Foo@Bar.com", role("EDITOR"), table_a, BASE_URL
        )

    invitation = scoped_invitation.invitation
    send_email.assert_called_once_with(invitation, BASE_URL)
    assert invitation.workspace == workspace
    assert invitation.email == "foo@bar.com"
    assert invitation.invited_by == user
    assert invitation.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert scoped_invitation.scope == table_a
    assert scoped_invitation.role.uid == "EDITOR"


@pytest.mark.django_db
def test_create_scoped_invitation_reuses_invitation_for_another_scope(
    data_fixture,
):
    user, workspace, _, table_a, table_b = setup_workspace(data_fixture)
    handler = RoleAssignmentHandler()

    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        first = handler.create_scoped_invitation(
            user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
        )
        second = handler.create_scoped_invitation(
            user, workspace, "foo@bar.com", role("VIEWER"), table_b, BASE_URL
        )

    assert first.invitation_id == second.invitation_id
    assert WorkspaceInvitation.objects.count() == 1
    assert WorkspaceScopedInvitation.objects.count() == 2
    assert first.invitation.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert send_email.call_count == 2

    # Inviting again to the same scope changes the role instead of adding a row,
    # and the invitation email is sent again.
    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        again = handler.create_scoped_invitation(
            user, workspace, "foo@bar.com", role("BUILDER"), table_a, BASE_URL
        )

    assert again.id == first.id
    assert again.role.uid == "BUILDER"
    assert WorkspaceScopedInvitation.objects.count() == 2
    send_email.assert_called_once()


@pytest.mark.django_db
def test_create_scoped_invitation_keeps_existing_workspace_role(data_fixture):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)
    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace,
        invited_by=user,
        email="foo@bar.com",
        permissions="EDITOR",
    )

    scoped_invitation = RoleAssignmentHandler().create_scoped_invitation(
        user, workspace, "foo@bar.com", role("VIEWER"), table_a, BASE_URL
    )

    assert scoped_invitation.invitation_id == invitation.id
    invitation.refresh_from_db()
    assert invitation.permissions == "EDITOR"


@pytest.mark.django_db
def test_create_scoped_invitation_checks_scope_and_permissions(data_fixture):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)
    viewer = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=viewer, permissions="VIEWER"
    )
    other_workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=other_workspace),
        user=user,
    )
    handler = RoleAssignmentHandler()

    with patch.object(CoreHandler, "send_workspace_invitation_email") as send_email:
        with pytest.raises(PermissionDenied):
            handler.create_scoped_invitation(
                viewer, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
            )

        with pytest.raises(ScopeNotExist):
            handler.create_scoped_invitation(
                user, workspace, "foo@bar.com", role("EDITOR"), workspace, BASE_URL
            )

        with pytest.raises(ScopeNotExist):
            handler.create_scoped_invitation(
                user, workspace, "foo@bar.com", role("EDITOR"), other_table, BASE_URL
            )

    assert WorkspaceInvitation.objects.count() == 0
    send_email.assert_not_called()


@pytest.mark.django_db
def test_create_scoped_invitation_requires_license(
    data_fixture, enterprise_data_fixture
):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)
    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        RoleAssignmentHandler().create_scoped_invitation(
            user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
        )


@pytest.mark.django_db
def test_create_scoped_invitation_for_existing_member_fails(data_fixture):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)
    member = data_fixture.create_user(email="member@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="VIEWER"
    )

    with pytest.raises(WorkspaceUserAlreadyExists):
        RoleAssignmentHandler().create_scoped_invitation(
            user, workspace, "member@bar.com", role("EDITOR"), table_a, BASE_URL
        )

    assert WorkspaceScopedInvitation.objects.count() == 0


@pytest.mark.django_db
def test_accepting_invitation_assigns_scoped_roles(data_fixture):
    user, workspace, database, table_a, table_b = setup_workspace(data_fixture)
    table_c = data_fixture.create_database_table(database=database, user=user)
    handler = RoleAssignmentHandler()
    scoped_invitation = handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("VIEWER"), table_b, BASE_URL
    )
    invitee = data_fixture.create_user(email="foo@bar.com")

    CoreHandler().accept_workspace_invitation(invitee, scoped_invitation.invitation)

    workspace_user = WorkspaceUser.objects.get(workspace=workspace, user=invitee)
    assert workspace_user.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assignments = {
        ra.scope_id: ra.role.uid
        for ra in RoleAssignment.objects.filter(workspace=workspace)
    }
    assert assignments == {table_a.id: "EDITOR", table_b.id: "VIEWER"}
    # The invitation and its scopes are gone once accepted.
    assert WorkspaceInvitation.objects.count() == 0
    assert WorkspaceScopedInvitation.objects.count() == 0

    def can_read(table):
        return CoreHandler().check_permissions(
            invitee,
            ReadDatabaseTableOperationType.type,
            workspace=workspace,
            context=table,
            raise_permission_exceptions=False,
        )

    assert can_read(table_a) is True
    assert can_read(table_b) is True
    assert can_read(table_c) is False


@pytest.mark.django_db
def test_accepting_invitation_skips_trashed_scope(data_fixture):
    user, workspace, database, table_a, table_b = setup_workspace(data_fixture)
    handler = RoleAssignmentHandler()
    scoped_invitation = handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("VIEWER"), table_b, BASE_URL
    )
    TrashHandler.trash(user, workspace, database, table_b)
    invitee = data_fixture.create_user(email="foo@bar.com")

    CoreHandler().accept_workspace_invitation(invitee, scoped_invitation.invitation)

    assert WorkspaceUser.objects.filter(workspace=workspace, user=invitee).exists()
    assignments = list(RoleAssignment.objects.filter(workspace=workspace))
    assert len(assignments) == 1
    assert assignments[0].scope_id == table_a.id


@pytest.mark.django_db
def test_signup_with_invitation_token_assigns_scoped_roles(data_fixture):
    user, workspace, _, table_a, _ = setup_workspace(data_fixture)
    scoped_invitation = RoleAssignmentHandler().create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    token = (
        CoreHandler()
        .get_workspace_invitation_signer()
        .dumps(scoped_invitation.invitation_id)
    )

    invitee = UserHandler().create_user(
        "Foo", "foo@bar.com", "password", workspace_invitation_token=token
    )

    assignment = RoleAssignment.objects.get(workspace=workspace)
    assert assignment.subject == invitee
    assert assignment.scope == table_a
    assert assignment.role.uid == "EDITOR"
    assert (
        WorkspaceUser.objects.get(workspace=workspace, user=invitee).permissions
        == NO_ROLE_LOW_PRIORITY_ROLE_UID
    )


@pytest.mark.django_db
def test_update_and_delete_scoped_invitation(data_fixture):
    user, workspace, _, table_a, table_b = setup_workspace(data_fixture)
    viewer = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=viewer, permissions="VIEWER"
    )
    handler = RoleAssignmentHandler()
    first = handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    second = handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("VIEWER"), table_b, BASE_URL
    )

    with pytest.raises(PermissionDenied):
        handler.update_scoped_invitation(viewer, first, role("BUILDER"))

    updated = handler.update_scoped_invitation(user, first, role("BUILDER"))
    assert updated.role.uid == "BUILDER"
    assert handler.get_scoped_invitation(first.id).role.uid == "BUILDER"

    with pytest.raises(PermissionDenied):
        handler.delete_scoped_invitation(viewer, first)

    handler.delete_scoped_invitation(user, first)

    # Only the scope is revoked, the invitation and its other scope remain.
    assert WorkspaceInvitation.objects.filter(id=first.invitation_id).exists()
    assert list(handler.get_scoped_invitations(workspace, table_b)) == [second]
    assert not handler.get_scoped_invitations(workspace, table_a).exists()
    with pytest.raises(ScopedInvitationDoesNotExist):
        handler.get_scoped_invitation(first.id)


@pytest.mark.django_db
def test_scoped_invitation_of_trashed_scope_cannot_be_managed(data_fixture):
    user, workspace, database, table_a, _ = setup_workspace(data_fixture)
    handler = RoleAssignmentHandler()
    scoped_invitation = handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    TrashHandler.trash(user, workspace, database, table_a)

    with pytest.raises(ScopeNotExist):
        handler.update_scoped_invitation(user, scoped_invitation, role("VIEWER"))

    with pytest.raises(ScopeNotExist):
        handler.delete_scoped_invitation(user, scoped_invitation)


@pytest.mark.django_db
def test_deleting_scope_deletes_its_scoped_invitations(data_fixture):
    user, workspace, _, table_a, table_b = setup_workspace(data_fixture)
    handler = RoleAssignmentHandler()
    handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("EDITOR"), table_a, BASE_URL
    )
    handler.create_scoped_invitation(
        user, workspace, "foo@bar.com", role("VIEWER"), table_b, BASE_URL
    )

    table_a.delete()

    remaining = list(WorkspaceScopedInvitation.objects.all())
    assert len(remaining) == 1
    assert remaining[0].scope_id == table_b.id
    assert WorkspaceInvitation.objects.count() == 1
