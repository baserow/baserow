from unittest.mock import patch

import pytest

from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.handler import TeamHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_synced_roles_for_all_tests_here(
    enable_enterprise, synced_roles
):
    pass


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_assignment_created(
    mock_broadcast_to_users, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    role_admin = Role.objects.get(uid="ADMIN")

    RoleAssignmentHandler().assign_role(user, workspace, role_admin, scope=database)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_assignment_updated(
    mock_broadcast_to_users, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    role_admin = Role.objects.get(uid="ADMIN")
    role_builder = Role.objects.get(uid="BUILDER")

    RoleAssignmentHandler().assign_role(user, workspace, role_admin, scope=database)
    mock_broadcast_to_users.delay.reset_mock()

    RoleAssignmentHandler().assign_role(user, workspace, role_builder, scope=database)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_assignment_deleted(
    mock_broadcast_to_users, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    role_admin = Role.objects.get(uid="ADMIN")

    RoleAssignmentHandler().assign_role(user, workspace, role_admin, scope=database)
    mock_broadcast_to_users.delay.reset_mock()

    RoleAssignmentHandler().remove_role(user, workspace, scope=database)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_workspace_level_permissions_updated(
    mock_broadcast_to_users, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(members=[user])
    role_viewer = Role.objects.get(uid="VIEWER")

    RoleAssignmentHandler().assign_role(user, workspace, role_viewer)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_team_trashed(
    mock_broadcast_to_users, data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    enterprise_data_fixture.create_subject(team, user)

    TeamHandler().delete_team(user, team)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_team_restored(
    mock_broadcast_to_users, data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    enterprise_data_fixture.create_subject(team, user)

    TeamHandler().delete_team(user, team)
    mock_broadcast_to_users.delay.reset_mock()

    TrashHandler.restore_item(user, "team", team.id)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0] == [user.id]
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow_enterprise.role.receivers.broadcast_to_users")
def test_permissions_updated_signal_role_many_users(
    mock_broadcast_to_users, data_fixture, enterprise_data_fixture
):
    user_amount = 20
    owner = data_fixture.create_user()
    users = [data_fixture.create_user() for i in range(user_amount)]
    user_ids = [user.id for user in users]
    workspace = data_fixture.create_workspace(user=owner, members=users)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    for user in users:
        enterprise_data_fixture.create_subject(team, user)

    TeamHandler().delete_team(owner, team)

    mock_broadcast_to_users.delay.assert_called_once()
    args = mock_broadcast_to_users.delay.call_args
    assert args[0][0].sort() == user_ids.sort()
    assert args[0][1] == {
        "type": "permissions_updated",
        "workspace_id": workspace.id,
    }
