from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.db import transaction

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.core.handler import CoreHandler
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    WORKSPACE_USER_PERMISSION_MEMBER,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.handler import UserHandler
from baserow.core.utils import generate_hash
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_groups")
@pytest.mark.websockets
def test_user_updated_name(
    mock_broadcast_to_workspaces, mock_broadcast_to_workspace, data_fixture
):
    user = data_fixture.create_user(first_name="Albert")
    workspace_user = CoreHandler().create_workspace(user=user, name="Test")
    workspace_user_2 = CoreHandler().create_workspace(user=user, name="Test 2")

    UserHandler().update_user(user, first_name="Jack")

    mock_broadcast_to_workspaces.delay.assert_called_once()
    args = mock_broadcast_to_workspaces.delay.call_args
    assert args[0][0] == [workspace_user.workspace.id, workspace_user_2.workspace.id]
    assert args[0][1]["type"] == "user_updated"
    assert args[0][1]["user"]["id"] == user.id
    assert args[0][1]["user"]["first_name"] == "Jack"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_groups")
@pytest.mark.websockets
def test_schedule_user_deletion(
    mock_broadcast_to_workspaces, mock_broadcast_to_workspace, data_fixture
):
    user = data_fixture.create_user(first_name="Albert", password="albert")
    workspace_user = CoreHandler().create_workspace(user=user, name="Test")
    workspace_user_2 = CoreHandler().create_workspace(user=user, name="Test 2")

    UserHandler().schedule_user_deletion(user)

    mock_broadcast_to_workspaces.delay.assert_called_once()
    args = mock_broadcast_to_workspaces.delay.call_args
    assert args[0][0] == [workspace_user.workspace.id, workspace_user_2.workspace.id]
    assert args[0][1]["type"] == "user_deleted"
    assert args[0][1]["user"]["id"] == user.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_groups")
@pytest.mark.websockets
def test_cancel_user_deletion(
    mock_broadcast_to_workspaces, mock_broadcast_to_workspace, data_fixture
):
    user = data_fixture.create_user(first_name="Albert", password="albert")
    user.profile.to_be_deleted = True
    user.save()
    workspace_user = CoreHandler().create_workspace(user=user, name="Test")
    workspace_user_2 = CoreHandler().create_workspace(user=user, name="Test 2")

    UserHandler().cancel_user_deletion(user)

    mock_broadcast_to_workspaces.delay.assert_called_once()
    args = mock_broadcast_to_workspaces.delay.call_args
    assert args[0][0] == [workspace_user.workspace.id, workspace_user_2.workspace.id]
    assert args[0][1]["type"] == "user_restored"
    assert args[0][1]["user"]["id"] == user.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_groups")
@pytest.mark.websockets
def test_user_permanently_deleted(
    mock_broadcast_to_workspaces, mock_broadcast_to_workspace, data_fixture
):
    user = data_fixture.create_user(first_name="Albert", password="albert")
    user.profile.to_be_deleted = True
    user.profile.save()
    user.last_login = datetime.now(tz=timezone.utc) - timedelta(weeks=100)
    user.save()
    workspace_user = CoreHandler().create_workspace(user=user, name="Test")
    workspace_user_2 = CoreHandler().create_workspace(user=user, name="Test 2")

    UserHandler().delete_expired_users_and_related_workspaces_if_last_admin(
        grace_delay=timedelta(days=1)
    )

    mock_broadcast_to_workspaces.delay.assert_called_once()
    args = mock_broadcast_to_workspaces.delay.call_args
    assert args[0][0] == [workspace_user.workspace.id, workspace_user_2.workspace.id]
    assert args[0][1]["type"] == "user_permanently_deleted"
    assert args[0][1]["user_id"] == user.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@pytest.mark.websockets
def test_workspace_created(mock_broadcast_to_workspace, data_fixture):
    user = data_fixture.create_user()
    workspace_user = CoreHandler().create_workspace(user=user, name="Test")

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace_user.workspace_id
    assert args[0][1]["type"] == "group_created"
    assert args[0][1]["workspace"]["id"] == workspace_user.workspace_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_workspace_restored(mock_broadcast_to_users, data_fixture):
    admin_user = data_fixture.create_user()
    member_user = data_fixture.create_user()
    # This user should not be sent the restore signal
    not_included_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user = data_fixture.create_user_workspace(
        user=admin_user,
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    member_workspace_user = data_fixture.create_user_workspace(
        user=member_user,
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )
    database = data_fixture.create_database_application(
        user=admin_user, workspace=workspace
    )
    TrashHandler.trash(admin_user, workspace, None, workspace)

    TrashHandler.restore_item(admin_user, "workspace", workspace.id)

    args = mock_broadcast_to_users.delay.call_args_list
    expected_database_json = {
        "id": database.id,
        "name": database.name,
        "created_on": database.created_on.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "order": 0,
        "type": "database",
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "generative_ai_models_enabled": {},
        },
        "tables": [],
    }
    assert len(args) == 2
    call_1 = args[1][0]
    call_2 = args[0][0]
    assert [call_1[0], call_2[0]] == unordered([[member_user.id], [admin_user.id]])
    permissions = unordered(["MEMBER", "ADMIN"])
    assert [
        call_1[1]["workspace"]["permissions"],
        call_2[1]["workspace"]["permissions"],
    ] == permissions

    assert call_1[1]["type"] == "group_restored"
    assert call_1[1]["workspace"]["id"] == member_workspace_user.workspace_id
    assert call_1[1]["applications"] == [expected_database_json]

    assert call_2[1]["type"] == "group_restored"
    assert call_2[1]["workspace"]["id"] == workspace_user.workspace_id
    assert call_2[1]["applications"] == [expected_database_json]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@pytest.mark.websockets
def test_workspace_updated(mock_broadcast_to_workspace, data_fixture):
    user = data_fixture.create_user()
    user.web_socket_id = "test"
    workspace = data_fixture.create_workspace(user=user)
    with transaction.atomic():
        workspace = CoreHandler().get_workspace_for_update(workspace.id)
        workspace = CoreHandler().update_workspace(
            user=user, workspace=workspace, name="Test"
        )

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "group_updated"
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace"]["id"] == workspace.id
    assert args[0][2] == "test"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_workspace_deleted(mock_broadcast_to_users, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    workspace_id = workspace.id
    with transaction.atomic():
        workspace = CoreHandler().get_workspace_for_update(workspace_id)
        CoreHandler().delete_workspace(user=user, workspace=workspace)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1]["type"] == "group_deleted"
    assert args[0][1]["workspace_id"] == workspace_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.receivers.broadcast_to_users")
@patch("baserow.ws.signals.broadcast_to_users")
@patch("baserow.ws.signals.broadcast_to_group")
@pytest.mark.websockets
def test_workspace_user_added(
    mock_broadcast_to_workspace,
    mock_broadcast_to_users,
    mock_broadcast_to_users2,
    data_fixture,
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user_1 = data_fixture.create_user_workspace(
        user=user_1, workspace=workspace
    )
    workspace_invitation = data_fixture.create_workspace_invitation(
        email=user_2.email, permissions="MEMBER", workspace=workspace
    )

    workspace_user_2 = CoreHandler().accept_workspace_invitation(
        user_2, workspace_invitation
    )

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "group_user_added"
    assert args[0][1]["id"] == workspace_user_2.id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_2.user_id
    assert args[0][1]["workspace_user"]["permissions"] == "MEMBER"


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
@patch("baserow.ws.signals.broadcast_to_group")
@pytest.mark.websockets
def test_workspace_user_updated(
    mock_broadcast_to_workspace, mock_broadcast_to_users, data_fixture
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user_1 = data_fixture.create_user_workspace(
        user=user_1, workspace=workspace
    )
    data_fixture.create_user_workspace(user=user_2, workspace=workspace)
    CoreHandler().update_workspace_user(
        user=user_2, workspace_user=workspace_user_1, permissions="MEMBER"
    )

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "group_user_updated"
    assert args[0][1]["id"] == workspace_user_1.id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_1.user_id
    assert args[0][1]["workspace_user"]["permissions"] == "MEMBER"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_workspace_user_deleted(
    mock_broadcast_to_users, mock_broadcast_to_workspace, data_fixture
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user_1 = data_fixture.create_user_workspace(
        user=user_1, workspace=workspace
    )
    workspace_user_id = workspace_user_1.id
    data_fixture.create_user_workspace(user=user_2, workspace=workspace)
    CoreHandler().delete_workspace_user(user=user_2, workspace_user=workspace_user_1)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user_1.id]
    assert args[0][1]["type"] == "group_user_deleted"
    assert args[0][1]["id"] == workspace_user_id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_1.user_id

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "group_user_deleted"
    assert args[0][1]["id"] == workspace_user_id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_1.user_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_user_leaves_workspace(
    mock_broadcast_to_users, mock_broadcast_to_workspace, data_fixture
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user_1 = data_fixture.create_user_workspace(
        user=user_1, workspace=workspace
    )
    workspace_user_id = workspace_user_1.id
    data_fixture.create_user_workspace(user=user_2, workspace=workspace)
    CoreHandler().leave_workspace(user_1, workspace)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user_1.id]
    assert args[0][1]["type"] == "group_user_deleted"
    assert args[0][1]["id"] == workspace_user_id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_1.user_id

    mock_broadcast_to_workspace.delay.assert_called_once()
    args = mock_broadcast_to_workspace.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "group_user_deleted"
    assert args[0][1]["id"] == workspace_user_id
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["workspace_user"]["user_id"] == workspace_user_1.user_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_workspaces_reordered(mock_broadcast_to_users, data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    workspace_3 = data_fixture.create_workspace(user=user)

    CoreHandler().order_workspaces(
        user=user, workspace_ids=[workspace_1.id, workspace_2.id, workspace_3.id]
    )

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1]["type"] == "groups_reordered"
    workspace_ids = [
        workspace_1.id,
        workspace_2.id,
        workspace_3.id,
    ]
    assert args[0][1]["workspace_ids"] == workspace_ids


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_application_created")
@pytest.mark.websockets
def test_application_created(mock_broadcast_application_created, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    websocket_id = "test"
    user.web_socket_id = websocket_id
    database = CoreHandler().create_application(
        user=user, workspace=workspace, type_name="database", name="Database"
    )

    mock_broadcast_application_created.delay.assert_called_once()
    args = mock_broadcast_application_created.delay.call_args
    assert args[0][0] == database.id
    assert args[0][1] == websocket_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_permitted_users")
@pytest.mark.websockets
def test_application_updated(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    CoreHandler().update_application(user=user, application=database, name="Database")

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "application_updated"
    assert args[0][4]["application_id"] == database.id
    assert args[0][4]["application"]["id"] == database.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_permitted_users")
@pytest.mark.websockets
def test_application_deleted(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    database_id = database.id
    CoreHandler().delete_application(user=user, application=database)

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "application_deleted"
    assert args[0][4]["application_id"] == database_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_group")
@pytest.mark.websockets
def test_applications_reordered(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    CoreHandler().order_applications(
        user=user, workspace=workspace, order=[database.id]
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == database.workspace_id
    assert args[0][1]["type"] == "applications_reordered"
    assert args[0][1]["workspace_id"] == workspace.id
    assert args[0][1]["order"] == [generate_hash(database.id)]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_application_created")
@pytest.mark.websockets
def test_duplicate_application(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    with transaction.atomic():
        application_clone = CoreHandler().duplicate_application(
            user=user, application=database
        )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][0] == application_clone.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.force_disconnect_users")
@pytest.mark.websockets
def test_user_password_changed(mock_force_disconnect_user, data_fixture):
    user = data_fixture.create_user(password="password")

    with transaction.atomic():
        UserHandler().change_password(user, "password", "newpassword")

    mock_force_disconnect_user.delay.assert_called_once()
    args = mock_force_disconnect_user.delay.call_args
    assert args[0][0] == [user.id]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.signals.broadcast_to_users")
@pytest.mark.websockets
def test_job_started(mock_broadcast_to_users, data_fixture):
    data_fixture.register_temp_job_types()

    user = data_fixture.create_user()
    with freeze_time("2024-01-01 12:00:00"):
        JobHandler().create_and_start_job(user, "tmp_job_type_1")

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "job_started",
        "job": {
            "id": AnyInt(),
            "type": "tmp_job_type_1",
            "progress_percentage": 0,
            "state": "started",
            "human_readable_error": "",
            "test_field": 42,
            "created_on": "2024-01-01T12:00:00Z",
            "updated_on": "2024-01-01T12:00:00Z",
        },
    }
