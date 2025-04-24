import os
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import OperationalError, transaction
from django.test.utils import override_settings

import pytest
from itsdangerous.exc import BadSignature

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.models import (
    BooleanField,
    DateField,
    LongTextField,
    TextField,
)
from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.views.models import GridView, GridViewFieldOptions
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationNotInWorkspace,
    ApplicationTypeDoesNotExist,
    BaseURLHostnameNotAllowed,
    DuplicateApplicationMaxLocksExceededException,
    IsNotAdminError,
    LastAdminOfWorkspace,
    MaxNumberOfPendingWorkspaceInvitesReached,
    TemplateDoesNotExist,
    TemplateFileDoesNotExist,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationDoesNotExist,
    WorkspaceInvitationEmailMismatch,
    WorkspaceUserAlreadyExists,
    WorkspaceUserDoesNotExist,
    WorkspaceUserIsLastAdmin,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    Application,
    Settings,
    Template,
    TemplateCategory,
    Workspace,
    WorkspaceInvitation,
    WorkspaceUser,
)
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.registries import ImportExportConfig, plugin_registry
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.models import UserFile


@pytest.mark.django_db
def test_get_settings():
    settings = CoreHandler().get_settings()
    assert isinstance(settings, Settings)
    assert len(settings.instance_id) > 32
    assert settings.allow_new_signups is True


@pytest.mark.django_db
def test_update_settings(data_fixture):
    user_1 = data_fixture.create_user(is_staff=True)
    user_2 = data_fixture.create_user()

    with pytest.raises(IsNotAdminError):
        CoreHandler().update_settings(user_2, allow_new_signups=False)

    settings = CoreHandler().update_settings(
        user_1, allow_new_signups=False, instance_id="test"
    )
    assert settings.allow_new_signups is False
    assert settings.instance_id != "test"

    settings = Settings.objects.all().first()
    assert settings.instance_id != "test"
    assert settings.allow_new_signups is False


@pytest.mark.django_db
def test_get_workspace(data_fixture):
    user_1 = data_fixture.create_user()
    data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user_1)

    handler = CoreHandler()

    with pytest.raises(WorkspaceDoesNotExist):
        handler.get_workspace(workspace_id=0)

    workspace_1_copy = handler.get_workspace(workspace_id=workspace_1.id)
    assert workspace_1_copy.id == workspace_1.id

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_workspace(
            workspace_id=workspace_1.id,
            base_queryset=Workspace.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db
def test_get_workspace_user(data_fixture):
    user_1 = data_fixture.create_user()
    data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace()
    workspace_user_1 = data_fixture.create_user_workspace(
        user=user_1, workspace=workspace_1
    )

    handler = CoreHandler()

    with pytest.raises(WorkspaceUserDoesNotExist):
        handler.get_workspace_user(workspace_user_id=0)

    workspace_user = handler.get_workspace_user(workspace_user_id=workspace_user_1.id)
    assert workspace_user.id == workspace_user_1.id
    assert workspace_user_1.workspace_id == workspace_1.id

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_workspace_user(
            workspace_user_id=workspace_user_1.id,
            base_queryset=WorkspaceUser.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_user_updated.send")
def test_update_workspace_user(send_mock, data_fixture):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        user=user_1, workspace=workspace_1, permissions="ADMIN"
    )
    workspace_user_2 = data_fixture.create_user_workspace(
        user=user_2, workspace=workspace_1, permissions="MEMBER"
    )

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_workspace_user(user=user_3, workspace_user=workspace_user_2)

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        handler.update_workspace_user(user=user_2, workspace_user=workspace_user_2)

    tmp = handler.update_workspace_user(
        user=user_1, workspace_user=workspace_user_2, permissions="ADMIN"
    )

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace_user"].id == workspace_user_2.id
    assert send_mock.call_args[1]["user"].id == user_1.id

    workspace_user_2.refresh_from_db()
    assert tmp.id == workspace_user_2.id
    assert tmp.permissions == "ADMIN"
    assert workspace_user_2.permissions == "ADMIN"


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_user_deleted.send")
def test_delete_workspace_user(send_mock, data_fixture):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        user=user_1, workspace=workspace_1, permissions="ADMIN"
    )
    workspace_user_2 = data_fixture.create_user_workspace(
        user=user_2, workspace=workspace_1, permissions="MEMBER"
    )

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_workspace_user(user=user_3, workspace_user=workspace_user_2)

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        handler.delete_workspace_user(user=user_2, workspace_user=workspace_user_2)

    workspace_user_id = workspace_user_2.id
    handler.delete_workspace_user(user=user_1, workspace_user=workspace_user_2)
    assert WorkspaceUser.objects.all().count() == 1

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace_user_id"] == workspace_user_id
    assert (
        send_mock.call_args[1]["workspace_user"].workspace_id
        == workspace_user_2.workspace_id
    )
    assert send_mock.call_args[1]["user"].id == user_1.id


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_created.send")
def test_create_workspace(send_mock, data_fixture):
    user = data_fixture.create_user()

    handler = CoreHandler()
    workspace_user = handler.create_workspace(user=user, name="Test workspace")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace"].id == workspace_user.workspace.id
    assert send_mock.call_args[1]["user"].id == user.id

    workspace = Workspace.objects.all().first()
    user_workspace = WorkspaceUser.objects.all().first()

    assert workspace.name == "Test workspace"
    assert user_workspace.user == user
    assert user_workspace.workspace == workspace
    assert user_workspace.order == 1
    assert user_workspace.permissions == WORKSPACE_USER_PERMISSION_ADMIN

    handler.create_workspace(user=user, name="Test workspace 2")

    assert Workspace.objects.all().count() == 2
    assert WorkspaceUser.objects.all().count() == 2


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_restored.send")
def test_restore_workspace(workspace_restored_mock, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(name="Test workspace", user=user)

    handler = CoreHandler()

    handler.delete_workspace_by_id(user, workspace.id)

    assert Workspace.objects.count() == 0

    TrashHandler.restore_item(user, "workspace", workspace.id)

    workspace_restored_mock.assert_called_once()
    assert workspace_restored_mock.call_args[1]["user"] is None
    assert (
        workspace_restored_mock.call_args[1]["workspace_user"].id
        == workspace.workspaceuser_set.get(user=user).id
    )

    workspace = Workspace.objects.all().first()
    user_workspace = WorkspaceUser.objects.all().first()

    assert workspace.name == "Test workspace"
    assert user_workspace.user == user
    assert user_workspace.workspace == workspace
    assert user_workspace.permissions == WORKSPACE_USER_PERMISSION_ADMIN


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_updated.send")
def test_update_workspace(send_mock, data_fixture):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user_1)

    handler = CoreHandler()

    workspace = handler.get_workspace_for_update(workspace.id)
    handler.update_workspace(user=user_1, workspace=workspace, name="New name")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace"].id == workspace.id
    assert send_mock.call_args[1]["user"].id == user_1.id

    workspace.refresh_from_db()

    assert workspace.name == "New name"

    with pytest.raises(UserNotInWorkspace):
        handler.update_workspace(user=user_2, workspace=workspace, name="New name")

    with pytest.raises(
        ValueError, match="The workspace is not an instance of Workspace."
    ):
        handler.update_workspace(user=user_2, workspace=object(), name="New name")


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_user_deleted.send")
def test_leave_workspace(send_mock, data_fixture):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    user_4 = data_fixture.create_user()
    user_5 = data_fixture.create_user(to_be_deleted=True)
    workspace_1 = data_fixture.create_workspace()
    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        user=user_1, workspace=workspace_1, permissions="ADMIN"
    )
    workspace_user_2 = data_fixture.create_user_workspace(
        user=user_2, workspace=workspace_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        user=user_3, workspace=workspace_1, permissions="USER"
    )
    # Add a pending deletion user
    data_fixture.create_user_workspace(
        user=user_5, workspace=workspace_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        user=user_3, workspace=workspace_2, permissions="USER"
    )
    data_fixture.create_user_workspace(
        user=user_4, workspace=workspace_2, permissions="USER"
    )

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.leave_workspace(user=user_4, workspace=workspace_1)

    handler.leave_workspace(user=user_2, workspace=workspace_1)
    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace_user_id"] == workspace_user_2.id
    assert (
        send_mock.call_args[1]["workspace_user"].workspace_id
        == workspace_user_2.workspace_id
    )
    assert send_mock.call_args[1]["user"].id == user_2.id

    with pytest.raises(WorkspaceUserIsLastAdmin):
        handler.leave_workspace(user=user_1, workspace=workspace_1)

    handler.leave_workspace(user=user_3, workspace=workspace_1)

    assert (
        WorkspaceUser.objects.filter(user=user_1, workspace=workspace_1).exists()
        is True
    )
    assert (
        WorkspaceUser.objects.filter(user=user_2, workspace=workspace_1).exists()
        is False
    )
    assert (
        WorkspaceUser.objects.filter(user=user_3, workspace=workspace_1).exists()
        is False
    )
    assert (
        WorkspaceUser.objects.filter(user=user_3, workspace=workspace_2).exists()
        is True
    )
    assert (
        WorkspaceUser.objects.filter(user=user_4, workspace=workspace_2).exists()
        is True
    )


@pytest.mark.django_db
@patch("baserow.core.signals.workspace_deleted.send")
def test_delete_workspace(send_mock, data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_table(database=database)
    data_fixture.create_workspace(user=user)
    user_2 = data_fixture.create_user()
    workspace_3 = data_fixture.create_workspace(user=user_2)

    handler = CoreHandler()

    workspace_1 = handler.get_workspace_for_update(workspace_1.id)
    workspace_3 = handler.get_workspace_for_update(workspace_3.id)
    handler.delete_workspace(user, workspace_1)

    assert workspace_1.trashed

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace"].id == workspace_1.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert len(send_mock.call_args[1]["workspace_users"]) == 1
    assert send_mock.call_args[1]["workspace_users"][0].id == user.id

    assert Workspace.objects.count() == 2
    assert WorkspaceUser.objects.count() == 2
    assert Workspace.trash.count() == 1
    assert WorkspaceUser.trash.count() == 1

    with pytest.raises(UserNotInWorkspace):
        handler.delete_workspace(user, workspace_3)

    handler.delete_workspace(user_2, workspace_3)

    assert Workspace.objects.count() == 1
    assert WorkspaceUser.objects.count() == 1
    assert Workspace.trash.count() == 2
    assert WorkspaceUser.trash.count() == 2

    with pytest.raises(ValueError):
        handler.delete_workspace(user=user_2, workspace=object())


@pytest.mark.django_db
@patch("baserow.core.signals.workspaces_reordered.send")
def test_order_workspaces(send_mock, data_fixture):
    user = data_fixture.create_user()
    ug_1 = data_fixture.create_user_workspace(user=user, order=1)
    ug_2 = data_fixture.create_user_workspace(user=user, order=2)
    ug_3 = data_fixture.create_user_workspace(user=user, order=3)

    assert [1, 2, 3] == [ug_1.order, ug_2.order, ug_3.order]

    handler = CoreHandler()
    handler.order_workspaces(
        user, [ug_3.workspace.id, ug_2.workspace.id, ug_1.workspace.id]
    )

    send_mock.assert_called_once()

    ug_1.refresh_from_db()
    ug_2.refresh_from_db()
    ug_3.refresh_from_db()

    assert [1, 2, 3] == [ug_3.order, ug_2.order, ug_1.order]

    handler.order_workspaces(
        user, [ug_2.workspace.id, ug_1.workspace.id, ug_3.workspace.id]
    )

    ug_1.refresh_from_db()
    ug_2.refresh_from_db()
    ug_3.refresh_from_db()

    assert [1, 2, 3] == [ug_2.order, ug_1.order, ug_3.order]


@pytest.mark.django_db
def test_get_workspaces_order(data_fixture):
    user = data_fixture.create_user()
    ug_1 = data_fixture.create_user_workspace(user=user, order=1)
    ug_2 = data_fixture.create_user_workspace(user=user, order=2)
    ug_3 = data_fixture.create_user_workspace(user=user, order=3)

    handler = CoreHandler()
    assert [
        ug_1.workspace_id,
        ug_2.workspace_id,
        ug_3.workspace_id,
    ] == handler.get_workspaces_order(user)

    handler.order_workspaces(
        user, [ug_3.workspace.id, ug_2.workspace.id, ug_1.workspace.id]
    )
    assert [
        ug_3.workspace_id,
        ug_2.workspace_id,
        ug_1.workspace_id,
    ] == handler.get_workspaces_order(user)


@pytest.mark.django_db
def test_get_workspace_invitation_by_token(data_fixture):
    user = data_fixture.create_user()
    workspace_user = data_fixture.create_user_workspace(user=user)
    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace_user.workspace, email=user.email
    )

    handler = CoreHandler()
    signer = handler.get_workspace_invitation_signer()

    with pytest.raises(BadSignature):
        handler.get_workspace_invitation_by_token(token="INVALID")

    with pytest.raises(WorkspaceInvitationDoesNotExist):
        handler.get_workspace_invitation_by_token(token=signer.dumps(999999))

    invitation2 = handler.get_workspace_invitation_by_token(
        token=signer.dumps(invitation.id)
    )

    assert invitation.id == invitation2.id
    assert invitation.invited_by_id == invitation2.invited_by_id
    assert invitation.workspace_id == invitation2.workspace_id
    assert invitation.email == invitation2.email
    assert invitation.permissions == invitation2.permissions
    assert isinstance(invitation2, WorkspaceInvitation)

    with pytest.raises(AttributeError):
        handler.get_workspace_invitation_by_token(
            token=signer.dumps(invitation.id),
            base_queryset=WorkspaceInvitation.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db
def test_get_workspace_invitation(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    data_fixture.create_user()
    workspace_user = data_fixture.create_user_workspace(user=user)
    data_fixture.create_user_workspace(
        user=user_2, workspace=workspace_user.workspace, permissions="MEMBER"
    )
    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace_user.workspace, email=user.email
    )

    handler = CoreHandler()

    with pytest.raises(WorkspaceInvitationDoesNotExist):
        handler.get_workspace_invitation(workspace_invitation_id=999999)

    invitation2 = handler.get_workspace_invitation(
        workspace_invitation_id=invitation.id
    )

    assert invitation.id == invitation2.id
    assert invitation.invited_by_id == invitation2.invited_by_id
    assert invitation.workspace_id == invitation2.workspace_id
    assert invitation.email == invitation2.email
    assert invitation.permissions == invitation2.permissions
    assert isinstance(invitation2, WorkspaceInvitation)

    with pytest.raises(AttributeError):
        handler.get_field(
            invitation_id=invitation.id,
            base_queryset=WorkspaceInvitation.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db(transaction=True)
def test_send_workspace_invitation_email(data_fixture, mailoutbox):
    workspace_invitation = data_fixture.create_workspace_invitation()
    handler = CoreHandler()

    with pytest.raises(BaseURLHostnameNotAllowed):
        handler.send_workspace_invitation_email(
            invitation=workspace_invitation, base_url="http://test.nl/workspace-invite"
        )

    signer = handler.get_workspace_invitation_signer()
    handler.send_workspace_invitation_email(
        invitation=workspace_invitation,
        base_url="http://localhost:3000/workspace-invite",
    )

    assert len(mailoutbox) == 1
    email = mailoutbox[0]

    assert (
        email.subject == f"{workspace_invitation.invited_by.first_name} invited you "
        f"to {workspace_invitation.workspace.name} - Baserow"
    )
    assert email.from_email == "no-reply@localhost"
    assert workspace_invitation.email in email.to

    html_body = email.alternatives[0][0]
    search_url = "http://localhost:3000/workspace-invite/"
    start_url_index = html_body.index(search_url)

    assert start_url_index != -1

    end_url_index = html_body.index('"', start_url_index)
    token = html_body[start_url_index + len(search_url) : end_url_index]

    invitation_id = signer.loads(token)
    assert invitation_id == workspace_invitation.id


@pytest.mark.django_db(transaction=True)
def test_send_workspace_invitation_email_in_different_language(
    data_fixture, mailoutbox
):
    user = data_fixture.create_user(language="fr")
    workspace_invitation = data_fixture.create_workspace_invitation(invited_by=user)

    handler = CoreHandler()
    handler.send_workspace_invitation_email(
        invitation=workspace_invitation,
        base_url="http://localhost:3000/workspace-invite",
    )

    assert len(mailoutbox) == 1
    assert (
        mailoutbox[0].subject
        == f"{workspace_invitation.invited_by.first_name} vous a invité à "
        f"{workspace_invitation.workspace.name} - Baserow"
    )


@pytest.mark.django_db
@patch("baserow.core.handler.CoreHandler.send_workspace_invitation_email")
def test_create_workspace_invitation(mock_send_email, data_fixture):
    user_workspace = data_fixture.create_user_workspace()
    user = user_workspace.user
    workspace = user_workspace.workspace
    user_2 = data_fixture.create_user()
    user_workspace_3 = data_fixture.create_user_workspace(
        workspace=workspace, permissions="MEMBER"
    )
    user_3 = user_workspace_3.user

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.create_workspace_invitation(
            user=user_2,
            workspace=workspace,
            email="test@test.nl",
            permissions="ADMIN",
            message="Test",
            base_url="http://localhost:3000/invite",
        )

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        handler.create_workspace_invitation(
            user=user_3,
            workspace=workspace,
            email="test@test.nl",
            permissions="ADMIN",
            message="Test",
            base_url="http://localhost:3000/invite",
        )

    with pytest.raises(WorkspaceUserAlreadyExists):
        handler.create_workspace_invitation(
            user=user,
            workspace=workspace,
            email=user_3.email,
            permissions="ADMIN",
            message="Test",
            base_url="http://localhost:3000/invite",
        )

    invitation = handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test@test.nl",
        permissions="ADMIN",
        message="Test",
        base_url="http://localhost:3000/invite",
    )
    assert invitation.invited_by_id == user.id
    assert invitation.workspace_id == workspace.id
    assert invitation.email == "test@test.nl"
    assert invitation.permissions == "ADMIN"
    assert invitation.message == "Test"
    assert WorkspaceInvitation.objects.all().count() == 1

    mock_send_email.assert_called_once()
    assert mock_send_email.call_args[0][0].id == invitation.id
    assert mock_send_email.call_args[0][1] == "http://localhost:3000/invite"

    # Because there already is an invitation for this email and workspace, it must be
    # updated instead of having duplicates.
    invitation = handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test@test.nl",
        permissions="MEMBER",
        message="New message",
        base_url="http://localhost:3000/invite",
    )
    assert invitation.invited_by_id == user.id
    assert invitation.workspace_id == workspace.id
    assert invitation.email == "test@test.nl"
    assert invitation.permissions == "MEMBER"
    assert invitation.message == "New message"
    assert WorkspaceInvitation.objects.all().count() == 1

    invitation = handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test2@test.nl",
        permissions="ADMIN",
        message="",
        base_url="http://localhost:3000/invite",
    )
    assert invitation.invited_by_id == user.id
    assert invitation.workspace_id == workspace.id
    assert invitation.email == "test2@test.nl"
    assert invitation.permissions == "ADMIN"
    assert invitation.message == ""
    assert WorkspaceInvitation.objects.all().count() == 2

    invitation = handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test3@test.nl",
        permissions="ADMIN",
        base_url="http://localhost:3000/invite",
    )
    assert invitation.invited_by_id == user.id
    assert invitation.workspace_id == workspace.id
    assert invitation.email == "test3@test.nl"
    assert invitation.permissions == "ADMIN"
    assert invitation.message == ""
    assert WorkspaceInvitation.objects.all().count() == 3


@pytest.mark.django_db
@patch("baserow.core.handler.CoreHandler.send_workspace_invitation_email")
@override_settings(BASEROW_MAX_PENDING_WORKSPACE_INVITES=1)
def test_create_workspace_invitation_max_pending(mock_send_email, data_fixture):
    user_workspace = data_fixture.create_user_workspace()
    user = user_workspace.user
    workspace = user_workspace.workspace

    handler = CoreHandler()

    handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test@test.nl",
        permissions="ADMIN",
        message="Test",
        base_url="http://localhost:3000/invite",
    )

    with pytest.raises(MaxNumberOfPendingWorkspaceInvitesReached):
        handler.create_workspace_invitation(
            user=user,
            workspace=workspace,
            email="test2@test.nl",
            permissions="ADMIN",
            message="Test",
            base_url="http://localhost:3000/invite",
        )

    # This email address already exists, so it should just update the invite without
    # failing.
    handler.create_workspace_invitation(
        user=user,
        workspace=workspace,
        email="test@test.nl",
        permissions="MEMBER",
        message="Test",
        base_url="http://localhost:3000/invite",
    )


@pytest.mark.django_db
def test_update_workspace_invitation(data_fixture):
    workspace_invitation = data_fixture.create_workspace_invitation()
    user = workspace_invitation.invited_by
    user_2 = data_fixture.create_user()
    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_workspace_invitation(
            user=user_2, invitation=workspace_invitation, permissions="ADMIN"
        )

    invitation = handler.update_workspace_invitation(
        user=user, invitation=workspace_invitation, permissions="MEMBER"
    )

    assert invitation.permissions == "MEMBER"
    invitation = WorkspaceInvitation.objects.all().first()
    assert invitation.permissions == "MEMBER"


@pytest.mark.django_db
def test_delete_workspace_invitation(data_fixture):
    workspace_invitation = data_fixture.create_workspace_invitation()
    user = workspace_invitation.invited_by
    user_2 = data_fixture.create_user()
    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_workspace_invitation(
            user=user_2,
            invitation=workspace_invitation,
        )

    handler.delete_workspace_invitation(
        user=user,
        invitation=workspace_invitation,
    )
    assert WorkspaceInvitation.objects.all().count() == 0


@pytest.mark.django_db
def test_reject_workspace_invitation(data_fixture):
    workspace_invitation = data_fixture.create_workspace_invitation(
        email="test@test.nl"
    )
    user_1 = data_fixture.create_user(email="test@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")

    handler = CoreHandler()

    with pytest.raises(WorkspaceInvitationEmailMismatch):
        handler.reject_workspace_invitation(
            user=user_2, invitation=workspace_invitation
        )

    assert WorkspaceInvitation.objects.all().count() == 1

    handler.reject_workspace_invitation(user=user_1, invitation=workspace_invitation)
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 1


@pytest.mark.django_db
def test_accept_workspace_invitation(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace_2 = data_fixture.create_workspace()
    workspace_invitation = data_fixture.create_workspace_invitation(
        email="test@test.nl", permissions="MEMBER", workspace=workspace
    )
    user_1 = data_fixture.create_user(email="test@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")

    handler = CoreHandler()

    with pytest.raises(WorkspaceInvitationEmailMismatch):
        handler.accept_workspace_invitation(
            user=user_2, invitation=workspace_invitation
        )

    assert WorkspaceInvitation.objects.all().count() == 1

    workspace_user = handler.accept_workspace_invitation(
        user=user_1, invitation=workspace_invitation
    )
    assert workspace_user.workspace_id == workspace.id
    assert workspace_user.permissions == "MEMBER"
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 1

    workspace_invitation = data_fixture.create_workspace_invitation(
        email="test@test.nl", permissions="ADMIN", workspace=workspace
    )
    workspace_user = handler.accept_workspace_invitation(
        user=user_1, invitation=workspace_invitation
    )
    assert workspace_user.workspace_id == workspace.id
    assert workspace_user.permissions == "ADMIN"
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 1

    workspace_invitation = data_fixture.create_workspace_invitation(
        email="test@test.nl", permissions="MEMBER", workspace=workspace_2
    )
    workspace_user = handler.accept_workspace_invitation(
        user=user_1, invitation=workspace_invitation
    )
    assert workspace_user.workspace_id == workspace_2.id
    assert workspace_user.permissions == "MEMBER"
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 2


@pytest.mark.django_db
def test_get_application(data_fixture):
    user_1 = data_fixture.create_user()
    data_fixture.create_user()
    application_1 = data_fixture.create_database_application(user=user_1)

    handler = CoreHandler()

    with pytest.raises(ApplicationDoesNotExist):
        handler.get_application(application_id=0)

    application_1_copy = handler.get_application(application_id=application_1.id)
    assert application_1_copy.id == application_1.id
    assert isinstance(application_1_copy, Application)

    database_1_copy = handler.get_application(
        application_id=application_1.id, base_queryset=Database.objects
    )
    assert database_1_copy.id == application_1.id
    assert isinstance(database_1_copy, Database)


@pytest.mark.django_db
@patch("baserow.core.signals.application_created.send")
def test_create_database_application(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    handler = CoreHandler()
    handler.create_application(
        user=user, workspace=workspace, type_name="database", name="Test database"
    )

    assert Application.objects.all().count() == 1
    assert Database.objects.all().count() == 1

    database = Database.objects.all().first()
    assert database.name == "Test database"
    assert database.order == 1
    assert database.workspace == workspace

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["application"].id == database.id
    assert send_mock.call_args[1]["user"].id == user.id

    with pytest.raises(UserNotInWorkspace):
        handler.create_application(
            user=user_2, workspace=workspace, type_name="database", name=""
        )

    with pytest.raises(ApplicationTypeDoesNotExist):
        handler.create_application(
            user=user, workspace=workspace, type_name="UNKNOWN", name=""
        )


@pytest.mark.django_db
@patch("baserow.core.signals.application_updated.send")
def test_update_database_application(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_application(
            user=user_2,
            application=database,
            name="Test database",
        )

    handler.update_application(user=user, application=database, name="Test 1")

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["application"].id == database.id
    assert send_mock.call_args[1]["user"].id == user.id

    database.refresh_from_db()

    assert database.name == "Test 1"


@pytest.mark.django_db
@patch("baserow.core.signals.applications_reordered.send")
def test_order_applications(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace, order=2
    )
    application_3 = data_fixture.create_database_application(
        workspace=workspace, order=3
    )

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.order_applications(user=user_2, workspace=workspace, order=[])

    with pytest.raises(ApplicationNotInWorkspace):
        handler.order_applications(user=user, workspace=workspace, order=[0])

    handler.order_applications(
        user=user,
        workspace=workspace,
        order=[application_3.id, application_2.id, application_1.id],
    )
    application_1.refresh_from_db()
    application_2.refresh_from_db()
    application_3.refresh_from_db()
    assert application_1.order == 3
    assert application_2.order == 2
    assert application_3.order == 1

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace"].id == workspace.id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["order"] == [
        application_3.id,
        application_2.id,
        application_1.id,
    ]

    handler.order_applications(
        user=user,
        workspace=workspace,
        order=[application_1.id, application_3.id, application_2.id],
    )
    application_1.refresh_from_db()
    application_2.refresh_from_db()
    application_3.refresh_from_db()
    assert application_1.order == 1
    assert application_2.order == 3
    assert application_3.order == 2

    handler.order_applications(user=user, workspace=workspace, order=[application_1.id])
    application_1.refresh_from_db()
    application_2.refresh_from_db()
    application_3.refresh_from_db()
    assert application_1.order == 1
    assert application_2.order == 3
    assert application_3.order == 2

    application_4 = data_fixture.create_database_application(
        workspace=workspace, order=4
    )
    application_5 = data_fixture.create_database_application(
        workspace=workspace, order=5
    )
    application_6 = data_fixture.create_database_application(
        workspace=workspace, order=6
    )

    handler.order_applications(
        user=user,
        workspace=workspace,
        order=[
            application_1.id,
            application_2.id,
            application_3.id,
            application_4.id,
            application_5.id,
            application_6.id,
        ],
    )

    assert list(Application.objects.order_by("order").values_list("id", flat=True)) == [
        application_1.id,
        application_2.id,
        application_3.id,
        application_4.id,
        application_5.id,
        application_6.id,
    ]

    tests = [
        (
            [
                application_2.id,
                application_4.id,
                application_3.id,
                application_5.id,
            ],
            [
                application_1.id,
                application_2.id,
                application_4.id,
                application_3.id,
                application_5.id,
                application_6.id,
            ],
        ),
        (
            [
                application_6.id,
                application_5.id,
                application_4.id,
            ],
            [
                application_1.id,
                application_2.id,
                application_3.id,
                application_6.id,
                application_5.id,
                application_4.id,
            ],
        ),
        (
            [
                application_3.id,
                application_2.id,
                application_1.id,
            ],
            [
                application_3.id,
                application_2.id,
                application_1.id,
                application_4.id,
                application_5.id,
                application_6.id,
            ],
        ),
        (
            [
                application_3.id,
                application_6.id,
                application_2.id,
                application_5.id,
                application_1.id,
            ],
            [
                application_3.id,
                application_4.id,
                application_6.id,
                application_2.id,
                application_5.id,
                application_1.id,
            ],
        ),
    ]

    for index, (input, result) in enumerate(tests):
        # Reset order
        handler.order_applications(
            user=user,
            workspace=workspace,
            order=[
                application_1.id,
                application_2.id,
                application_3.id,
                application_4.id,
                application_5.id,
                application_6.id,
            ],
        )

        handler.order_applications(
            user=user,
            workspace=workspace,
            order=input,
        )

        assert (
            list(Application.objects.order_by("order").values_list("id", flat=True))
            == result
        ), f"Test {index + 1} is not ordered as expected"


@pytest.mark.django_db
@patch("baserow.core.signals.application_deleted.send")
def test_delete_database_application(send_mock, data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)

    handler = CoreHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_application(user=user_2, application=database)

    with pytest.raises(ValueError):
        handler.delete_application(user=user_2, application=object())

    handler.delete_application(user=user, application=database)

    database.refresh_from_db()
    assert database.trashed

    assert Database.objects.all().count() == 0
    assert Database.trash.all().count() == 1

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["application_id"] == database.id
    assert send_mock.call_args[1]["application"].id == database.id
    assert send_mock.call_args[1]["user"].id == user.id


@pytest.mark.django_db
def test_get_template(data_fixture):
    data_fixture.create_user()
    template_1 = data_fixture.create_template()

    handler = CoreHandler()

    with pytest.raises(TemplateDoesNotExist):
        handler.get_template(template_id=0)

    template_1_copy = handler.get_template(template_id=template_1.id)
    assert template_1_copy.id == template_1.id

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_template(
            template_id=template_1.id,
            base_queryset=Template.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db(transaction=True)
def test_export_import_workspace_application(data_fixture):
    workspace = data_fixture.create_workspace()
    imported_workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)

    handler = CoreHandler()
    config = ImportExportConfig(include_permission_data=False)
    exported_applications = handler.export_workspace_applications(
        workspace, BytesIO(), config
    )
    imported_applications, id_mapping = handler.import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )

    assert len(imported_applications) == 1
    imported_database = imported_applications[0]
    assert imported_database.id != database.id
    assert imported_database.name == database.name
    assert imported_database.order == database.order + 1
    assert imported_database.table_set.all().count() == 1
    assert database.id in id_mapping["applications"]
    assert id_mapping["applications"][database.id] == imported_database.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to pytest's additional args to run this test,
# you can do this in intellij by editing the run config for this test and adding
# --run-once-per-day-in-ci to the additional args.
def test_sync_and_install_all_templates(data_fixture, tmpdir):
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = CoreHandler()
    handler.sync_templates(storage=storage)

    assert Template.objects.count() == len(
        list(Path(settings.APPLICATION_TEMPLATES_DIR).glob("*.json"))
    )

    workspace_user = data_fixture.create_user_workspace()
    for template in Template.objects.all():
        with transaction.atomic():
            handler.install_template(
                workspace_user.user, workspace_user.workspace, template, storage=storage
            )


@pytest.mark.django_db(transaction=True)
def test_sync_and_install_single_template(data_fixture, tmpdir):
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = CoreHandler()

    with transaction.atomic():
        handler.sync_templates(storage=storage, pattern="new-hire-onboarding")

    workspace_user = data_fixture.create_user_workspace()
    template = Template.objects.get()
    with transaction.atomic():
        handler.install_template(
            workspace_user.user, workspace_user.workspace, template, storage=storage
        )


@pytest.mark.django_db
def test_sync_templates(data_fixture, tmpdir):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    workspace_1 = data_fixture.create_workspace()
    workspace_2 = data_fixture.create_workspace()
    workspace_3 = data_fixture.create_workspace()

    category_1 = data_fixture.create_template_category(name="No templates")
    category_2 = data_fixture.create_template_category(name="Has template")
    template = data_fixture.create_template(
        slug="is-going-to-be-deleted", workspace=workspace_1, category=category_2
    )
    template_2 = data_fixture.create_template(
        slug="example-template",
        workspace=workspace_2,
        category=category_2,
        export_hash="IS_NOT_GOING_MATCH",
    )
    template_3 = data_fixture.create_template(
        slug="example-template-2",
        workspace=workspace_3,
        category=category_2,
        export_hash="f086c9b4b0dfea6956d0bb32af210277bb645ff3faebc5fb37a9eae85c433f2d",
    )

    handler = CoreHandler()
    handler.sync_templates(storage=storage)

    workspaces = Workspace.objects.all().order_by("id")
    assert len(workspaces) == 3
    assert workspaces[0].id == workspace_3.id
    assert workspaces[1].id not in [workspace_1.id, workspace_2.id]
    assert workspaces[2].id not in [workspace_1.id, workspace_2.id]

    assert not TemplateCategory.objects.filter(id=category_1.id).exists()
    assert not TemplateCategory.objects.filter(id=category_2.id).exists()
    categories = TemplateCategory.objects.all()
    assert len(categories) == 1
    assert categories[0].name == "Test category 1"

    assert not Template.objects.filter(id=template.id).exists()
    assert Template.objects.filter(id=template_2.id).exists()
    assert Template.objects.filter(id=template_3.id).exists()

    refreshed_template_2 = Template.objects.get(id=template_2.id)
    assert refreshed_template_2.name == "Example template"
    assert refreshed_template_2.icon == "file"
    assert (
        refreshed_template_2.export_hash
        == "7d86876e8fa061bb0deec179ce2a1b24a220f5cd4eb6ddacbdccf036160c7bf3"
    )
    assert refreshed_template_2.keywords == "Example,Template,For,Search"
    assert refreshed_template_2.categories.all().first().id == categories[0].id
    assert template_2.workspace_id != refreshed_template_2.workspace_id
    assert refreshed_template_2.workspace.name == "Example template"
    assert refreshed_template_2.workspace.application_set.count() == 1

    refreshed_template_3 = Template.objects.get(id=template_3.id)
    assert template_3.workspace_id == refreshed_template_3.workspace_id
    # We expect the workspace count to be zero because the export hash matches and
    # nothing was updated.
    assert refreshed_template_3.workspace.application_set.count() == 0

    # Because the `example-template.json` has a file field that contains the hello
    # world file, we expect it to exist after syncing the templates.
    assert UserFile.objects.all().count() == 1
    user_file = UserFile.objects.all().first()
    assert user_file.original_name == "hello.txt"
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello World"

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db
def test_sync_templates_mapped_open_application_id(data_fixture, tmpdir):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    handler = CoreHandler()
    handler.sync_templates(storage=storage)

    template_1 = Template.objects.get(slug="example-template")
    template_2 = Template.objects.get(slug="example-template-2")

    application = template_2.workspace.application_set.all().first()

    assert template_1.open_application is None
    assert template_2.open_application == application.id

    handler.sync_templates(storage=storage)

    assert template_1.open_application is None
    assert template_2.open_application == application.id

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db
@patch("baserow.core.signals.application_created.send")
def test_install_template(send_mock, tmpdir, data_fixture):
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    handler = CoreHandler()
    handler.sync_templates(storage=storage)

    template_2 = data_fixture.create_template(slug="does-not-exist")

    with pytest.raises(TemplateFileDoesNotExist):
        handler.install_template(user, workspace, template_2, storage=storage)

    template = Template.objects.get(slug="example-template")

    with pytest.raises(UserNotInWorkspace):
        handler.install_template(user, workspace_2, template, storage=storage)

    applications, id_mapping = handler.install_template(
        user, workspace, template, storage=storage
    )
    assert len(applications) == 1
    assert applications[0].workspace_id == workspace.id
    assert applications[0].name == "Event marketing"

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["application"].id == applications[0].id
    assert send_mock.call_args[1]["user"].id == user.id

    # Because the `example-template.json` has a file field that contains the hello
    # world file, we expect it to exist after syncing the templates.
    assert UserFile.objects.all().count() == 1
    user_file = UserFile.objects.all().first()
    assert user_file.original_name == "hello.txt"
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello World"

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db
@patch("baserow.core.signals.application_created.send")
def test_restore_application(application_created_mock, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(name="Test workspace", user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)

    handler = CoreHandler()

    handler.delete_application(user, application=database)

    assert Application.objects.count() == 0

    TrashHandler.restore_item(user, "application", database.id)

    application_created_mock.assert_called_once()
    assert application_created_mock.call_args[1]["application"].id == database.id
    assert application_created_mock.call_args[1]["user"] is None

    restored_app = Application.objects.all().first()

    assert restored_app.name == database.name
    assert restored_app.id == database.id


@pytest.mark.django_db
def test_raise_if_user_is_last_admin_of_workspace(data_fixture):
    workspace_user = data_fixture.create_user_workspace()
    user2 = data_fixture.create_user()

    with pytest.raises(LastAdminOfWorkspace):
        CoreHandler.raise_if_user_is_last_admin_of_workspace(workspace_user)

    CoreHandler().add_user_to_workspace(workspace_user.workspace, user2, "ADMIN")

    try:
        CoreHandler.raise_if_user_is_last_admin_of_workspace(workspace_user)
    except LastAdminOfWorkspace:
        pytest.fail("Unexpected last admin error...")


@pytest.mark.django_db
def test_check_permission_for_multiple_actors(data_fixture):
    user = data_fixture.create_user()
    user_of_another_workspace = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    assert CoreHandler().check_permission_for_multiple_actors(
        [user, user_of_another_workspace],
        ReadWorkspaceOperationType.type,
        workspace,
        context=workspace,
    ) == [user]


@pytest.mark.django_db
def test_duplicate_application_export_serialized_raises_operationalerror(
    data_fixture,
    bypass_check_permissions,
    application_type_serialized_raising_operationalerror,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = CoreHandler().create_application(
        user=user,
        workspace=workspace,
        type_name=DatabaseApplicationType.type,
        name="Database",
    )

    with application_type_serialized_raising_operationalerror(
        raise_transaction_exception=True
    ):
        with pytest.raises(DuplicateApplicationMaxLocksExceededException) as exc:
            CoreHandler().duplicate_application(user, database)

    with application_type_serialized_raising_operationalerror(
        raise_transaction_exception=False
    ):
        with pytest.raises(OperationalError) as exc:
            CoreHandler().duplicate_application(user, database)


@pytest.mark.django_db
def test_get_user_email_mapping(data_fixture):
    workspace = data_fixture.create_workspace()
    user_in_workspace = data_fixture.create_user()
    user2_in_workspace = data_fixture.create_user()
    user_outside_workspace = data_fixture.create_user()
    data_fixture.create_user_workspace(user=user_in_workspace, workspace=workspace)
    data_fixture.create_user_workspace(user=user2_in_workspace, workspace=workspace)

    mapping = CoreHandler.get_user_email_mapping(workspace.id, only_emails=[])

    assert mapping == {
        f"{user_in_workspace.email}": user_in_workspace,
        f"{user2_in_workspace.email}": user2_in_workspace,
    }

    mapping = CoreHandler.get_user_email_mapping(
        workspace.id, only_emails=[user_in_workspace.email]
    )

    assert mapping == {
        f"{user_in_workspace.email}": user_in_workspace,
    }


@pytest.mark.django_db
def test_create_initial_workspace(data_fixture):
    plugin_mock = MagicMock()
    with patch.dict(plugin_registry.registry, {"mock": plugin_mock}):
        user = data_fixture.create_user(first_name="Test1")
        workspace_user = CoreHandler().create_initial_workspace(user)

        assert Workspace.objects.all().count() == 1
        workspace = Workspace.objects.all().first()
        assert workspace.users.filter(id=user.id).count() == 1
        assert workspace.name == "Test1's workspace"
        assert workspace.id == workspace_user.workspace_id

        assert Database.objects.all().count() == 1
        assert Table.objects.all().count() == 2
        assert GridView.objects.all().count() == 2
        assert TextField.objects.all().count() == 3
        assert LongTextField.objects.all().count() == 1
        assert BooleanField.objects.all().count() == 2
        assert DateField.objects.all().count() == 1
        assert GridViewFieldOptions.objects.all().count() == 3

        tables = Table.objects.all().order_by("id")

        model_1 = tables[0].get_model()
        model_1_results = model_1.objects.all()
        assert len(model_1_results) == 5
        assert model_1_results[0].order == Decimal("1.00000000000000000000")
        assert model_1_results[1].order == Decimal("2.00000000000000000000")
        assert model_1_results[2].order == Decimal("3.00000000000000000000")
        assert model_1_results[3].order == Decimal("4.00000000000000000000")
        assert model_1_results[4].order == Decimal("5.00000000000000000000")

        model_2 = tables[1].get_model()
        model_2_results = model_2.objects.all()
        assert len(model_2_results) == 4
        assert model_2_results[0].order == Decimal("1.00000000000000000000")
        assert model_2_results[1].order == Decimal("2.00000000000000000000")
        assert model_2_results[2].order == Decimal("3.00000000000000000000")
        assert model_2_results[3].order == Decimal("4.00000000000000000000")

        plugin_mock.create_initial_workspace.assert_called_with(user, workspace)
