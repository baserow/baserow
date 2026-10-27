from unittest.mock import patch

import pytest

from baserow.core.exceptions import (
    FeatureDisabledException,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkSignupsDisabled,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitationLink, WorkspaceUser
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_create_workspace_invitation_link(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    outsider = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])

    with pytest.raises(UserNotInWorkspace):
        CoreHandler().create_workspace_invitation_link(outsider, workspace, "MEMBER")

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        CoreHandler().create_workspace_invitation_link(member, workspace, "MEMBER")

    assert WorkspaceInvitationLink.objects.count() == 0

    invitation_link = CoreHandler().create_workspace_invitation_link(
        admin, workspace, "MEMBER"
    )
    second_link = CoreHandler().create_workspace_invitation_link(
        admin, workspace, "ADMIN"
    )

    assert invitation_link.workspace_id == workspace.id
    assert invitation_link.created_by_id == admin.id
    assert invitation_link.permissions == "MEMBER"
    assert len(invitation_link.slug) >= 43
    assert invitation_link.slug != second_link.slug


@pytest.mark.django_db
def test_create_workspace_invitation_link_requires_feature_flag(data_fixture, settings):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    settings.FEATURE_FLAGS = []

    with pytest.raises(FeatureDisabledException):
        CoreHandler().create_workspace_invitation_link(admin, workspace, "MEMBER")

    assert WorkspaceInvitationLink.objects.count() == 0


@pytest.mark.django_db
def test_create_workspace_invitation_link_requires_signups(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)

    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )
    with pytest.raises(WorkspaceInvitationLinkSignupsDisabled):
        CoreHandler().create_workspace_invitation_link(admin, workspace, "MEMBER")
    assert WorkspaceInvitationLink.objects.count() == 0

    # Either setting is enough for people to sign up through the link.
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=True
    )
    CoreHandler().create_workspace_invitation_link(admin, workspace, "MEMBER")
    data_fixture.update_settings(
        allow_new_signups=True, allow_signups_via_workspace_invitations=False
    )
    CoreHandler().create_workspace_invitation_link(admin, workspace, "MEMBER")
    assert WorkspaceInvitationLink.objects.count() == 2


@pytest.mark.django_db
def test_list_workspace_invitation_links(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )
    data_fixture.create_workspace_invitation_link()

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        CoreHandler().list_workspace_invitation_links(member, workspace)

    invitation_links = CoreHandler().list_workspace_invitation_links(admin, workspace)
    assert [link.id for link in invitation_links] == [invitation_link.id]


@pytest.mark.django_db
def test_update_workspace_invitation_link(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        CoreHandler().update_workspace_invitation_link(member, invitation_link, "ADMIN")

    CoreHandler().update_workspace_invitation_link(admin, invitation_link, "ADMIN")

    invitation_link.refresh_from_db()
    assert invitation_link.permissions == "ADMIN"


@pytest.mark.django_db
def test_delete_workspace_invitation_link(data_fixture):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        CoreHandler().delete_workspace_invitation_link(member, invitation_link)

    CoreHandler().delete_workspace_invitation_link(admin, invitation_link)

    assert WorkspaceInvitationLink.objects.count() == 0
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link_by_slug(invitation_link.slug)


@pytest.mark.django_db
def test_get_workspace_invitation_link_by_slug(data_fixture, settings):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )

    assert (
        CoreHandler().get_workspace_invitation_link_by_slug(invitation_link.slug).id
        == invitation_link.id
    )

    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link_by_slug("unknown")

    TrashHandler.trash(admin, workspace, None, workspace)
    with pytest.raises(WorkspaceInvitationLinkDoesNotExist):
        CoreHandler().get_workspace_invitation_link_by_slug(invitation_link.slug)

    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        CoreHandler().get_workspace_invitation_link_by_slug(invitation_link.slug)


@pytest.mark.django_db
@patch("baserow.core.handler.workspace_user_joined_via_invitation_link.send")
def test_join_workspace_via_invitation_link(send_mock, data_fixture):
    admin = data_fixture.create_user()
    newcomer = data_fixture.create_user()
    second_newcomer = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )

    workspace_user = CoreHandler().join_workspace_via_invitation_link(
        newcomer, invitation_link
    )
    CoreHandler().join_workspace_via_invitation_link(second_newcomer, invitation_link)

    assert workspace_user.user_id == newcomer.id
    assert workspace_user.workspace_id == workspace.id
    assert workspace_user.permissions == "MEMBER"
    assert WorkspaceUser.objects.filter(workspace=workspace).count() == 3
    # The link can be used any number of times.
    assert WorkspaceInvitationLink.objects.filter(id=invitation_link.id).exists()

    assert send_mock.call_count == 2
    kwargs = send_mock.call_args.kwargs
    assert kwargs["invitation_link"] == invitation_link
    assert kwargs["user"] == second_newcomer
    assert kwargs["workspace_user"] == WorkspaceUser.objects.get(user=second_newcomer)


@pytest.mark.django_db
def test_join_workspace_via_invitation_link_keeps_existing_permissions(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )

    workspace_user = CoreHandler().join_workspace_via_invitation_link(
        admin, invitation_link
    )

    assert workspace_user.permissions == "ADMIN"
    assert WorkspaceUser.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_join_workspace_via_invitation_link_requires_feature_flag(
    data_fixture, settings
):
    newcomer = data_fixture.create_user()
    invitation_link = data_fixture.create_workspace_invitation_link()
    settings.FEATURE_FLAGS = []

    with pytest.raises(FeatureDisabledException):
        CoreHandler().join_workspace_via_invitation_link(newcomer, invitation_link)

    assert not WorkspaceUser.objects.filter(user=newcomer).exists()


@pytest.mark.django_db
def test_invitation_link_survives_deleting_its_creator(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )

    admin.delete()

    invitation_link.refresh_from_db()
    assert invitation_link.created_by is None
