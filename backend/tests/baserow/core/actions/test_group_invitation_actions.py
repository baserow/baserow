import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    AcceptWorkspaceInvitationActionType,
    CreateWorkspaceInvitationActionType,
    DeleteWorkspaceInvitationActionType,
    RejectWorkspaceInvitationActionType,
    UpdateWorkspaceInvitationActionType,
)
from baserow.core.models import WorkspaceInvitation


@pytest.mark.django_db
def test_create_workspace_invitation_action_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    invitation = action_type_registry.get(CreateWorkspaceInvitationActionType.type).do(
        user=user,
        workspace=workspace,
        email="user@test.com",
        permissions="ADMIN",
        base_url="http://localhost:3000/",
    )

    assert invitation.workspace == workspace
    assert invitation.email == "user@test.com"
    assert invitation.permissions == "ADMIN"
    assert invitation.invited_by == user


@pytest.mark.django_db
def test_update_workspace_invitation_action_type(data_fixture):
    user = data_fixture.create_user()
    invitation = data_fixture.create_workspace_invitation(invited_by=user)

    assert invitation.permissions == "ADMIN"
    action_type_registry.get(UpdateWorkspaceInvitationActionType.type).do(
        user, invitation, permissions="MEMBER"
    )
    assert invitation.permissions == "MEMBER"


@pytest.mark.django_db
def test_delete_workspace_invitation_action_type(data_fixture):
    user = data_fixture.create_user()
    invitation = data_fixture.create_workspace_invitation(invited_by=user)

    assert WorkspaceInvitation.objects.count() == 1
    action_type_registry.get(DeleteWorkspaceInvitationActionType.type).do(
        user, invitation
    )
    assert WorkspaceInvitation.objects.count() == 0


@pytest.mark.django_db
def test_accept_workspace_invitation_action_type(data_fixture):
    sender = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=sender)
    user = data_fixture.create_user()
    invitation = data_fixture.create_workspace_invitation(
        invited_by=sender, workspace=workspace, email=user.email
    )

    action_type_registry.get(AcceptWorkspaceInvitationActionType.type).do(
        user, invitation
    )
    assert workspace.users.filter(id=user.id).exists()


@pytest.mark.django_db
def test_reject_workspace_invitation_action_type(data_fixture):
    sender = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=sender)
    user = data_fixture.create_user()
    invitation = data_fixture.create_workspace_invitation(
        invited_by=sender, workspace=workspace, email=user.email
    )

    action_type_registry.get(RejectWorkspaceInvitationActionType.type).do(
        user, invitation
    )
    assert workspace.users.filter(id=user.id).exists() is False
