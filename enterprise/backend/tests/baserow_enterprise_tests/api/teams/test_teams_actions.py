from typing import cast

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.models import Team, TeamSubject
from baserow_enterprise.role.models import Role
from baserow_enterprise.scopes import TeamsActionScopeType
from baserow_enterprise.teams.actions import (
    CreateTeamActionType,
    CreateTeamSubjectActionType,
    DeleteTeamActionType,
    DeleteTeamSubjectActionType,
    UpdateTeamActionType,
)
from baserow_enterprise.teams.handler import TeamForUpdate, TeamHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def undo_and_redo(user, workspace, session_id):
    scopes = [TeamsActionScopeType.value(workspace.id)]
    return (
        ActionHandler.undo(user, scopes, session_id),
        ActionHandler.redo(user, scopes, session_id),
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_creating_team_cannot_be_undone(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)

    team = action_type_registry.get_by_type(CreateTeamActionType).do(
        user,
        "test",
        workspace,
        [{"subject_id": user.id, "subject_type": "auth.User"}],
    )

    assert undo_and_redo(user, workspace, session_id) == ([], [])
    assert Team.objects.filter(pk=team.id).exists()
    assert TeamSubject.objects.filter(team=team, subject_id=user.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_team_cannot_be_undone(data_fixture, enterprise_data_fixture):
    session_id = "session-id"
    role_viewer = Role.objects.get(uid="VIEWER")
    role_builder = Role.objects.get(uid="BUILDER")
    user = data_fixture.create_user(session_id=session_id)
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[member])
    team = action_type_registry.get_by_type(CreateTeamActionType).do(
        user, "original name", workspace, default_role=role_viewer
    )
    subjects = [
        {"subject_id": user.id, "subject_type": "auth.User"},
        {"subject_id": member.id, "subject_type": "auth.User"},
    ]

    action_type_registry.get_by_type(UpdateTeamActionType).do(
        user,
        cast(TeamForUpdate, team),
        "updated name",
        subjects,
        default_role=role_builder,
    )

    assert undo_and_redo(user, workspace, session_id) == ([], [])
    team = TeamHandler().get_team(user, team.pk)
    assert team.name == "updated name"
    assert team.default_role_uid == "BUILDER"
    assert set(
        TeamSubject.objects.filter(team=team).values_list("subject_id", flat=True)
    ) == {user.id, member.id}


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_team_update_recorded_before_it_was_non_undoable_does_nothing(
    data_fixture, enterprise_data_fixture
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="updated name", members=[user]
    )
    # Action rows written while team updates were still undoable stay around until
    # they are cleaned up.
    Action.objects.create(
        user=user,
        session=session_id,
        scope=TeamsActionScopeType.value(workspace.id),
        type=UpdateTeamActionType.type,
        params={
            "team_id": team.id,
            "original_name": "original name",
            "name": "updated name",
            "workspace_id": workspace.id,
            "subjects": [],
            "original_default_role_uid": None,
            "default_role_uid": None,
        },
    )

    [action] = ActionHandler.undo(
        user, [TeamsActionScopeType.value(workspace.id)], session_id
    )

    assert action.error is not None
    team.refresh_from_db()
    assert team.name == "updated name"
    assert TeamSubject.objects.filter(team=team, subject_id=user.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_deleting_team_cannot_be_undone(data_fixture, enterprise_data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    action_type_registry.get_by_type(DeleteTeamActionType).do(user, team)

    assert undo_and_redo(user, workspace, session_id) == ([], [])
    assert not Team.objects.filter(pk=team.pk).exists()


@pytest.mark.django_db
def test_deleted_team_can_be_restored_from_the_trash(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace, members=[user])

    action_type_registry.get_by_type(DeleteTeamActionType).do(user, team)
    assert not Team.objects.filter(pk=team.pk).exists()

    TrashHandler.restore_item(user, "team", team.id)

    assert Team.objects.filter(pk=team.pk).exists()
    assert TeamSubject.objects.filter(team=team, subject_id=user.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_creating_team_subject_cannot_be_undone(data_fixture, enterprise_data_fixture):
    session_id = "session-id"
    invitee = data_fixture.create_user()
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user, members=[invitee])
    team = enterprise_data_fixture.create_team(workspace=workspace)

    subject = action_type_registry.get_by_type(CreateTeamSubjectActionType).do(
        user, {"email": invitee.email}, "auth.User", team
    )

    assert undo_and_redo(user, workspace, session_id) == ([], [])
    assert TeamSubject.objects.filter(pk=subject.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_deleting_team_subject_cannot_be_undone(data_fixture, enterprise_data_fixture):
    session_id = "session-id"
    invitee = data_fixture.create_user()
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user, members=[invitee])
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = enterprise_data_fixture.create_subject(team=team, subject=invitee)
    subject_id = subject.id

    action_type_registry.get_by_type(DeleteTeamSubjectActionType).do(user, subject)

    assert undo_and_redo(user, workspace, session_id) == ([], [])
    assert not TeamSubject.objects.filter(pk=subject_id).exists()


@pytest.mark.django_db
def test_team_actions_are_audit_logged(data_fixture, enterprise_data_fixture):
    role_viewer = Role.objects.get(uid="VIEWER")
    user = data_fixture.create_user()
    invitee = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[invitee])
    subjects = [{"subject_id": user.id, "subject_type": "auth.User"}]

    team = action_type_registry.get_by_type(CreateTeamActionType).do(
        user, "Sales", workspace, subjects
    )
    action_type_registry.get_by_type(UpdateTeamActionType).do(
        user, cast(TeamForUpdate, team), "Marketing", subjects, role_viewer
    )
    subject = action_type_registry.get_by_type(CreateTeamSubjectActionType).do(
        user, {"id": invitee.id}, "auth.User", team
    )
    subject_id = subject.id
    action_type_registry.get_by_type(DeleteTeamSubjectActionType).do(user, subject)
    action_type_registry.get_by_type(DeleteTeamActionType).do(user, team)

    entries = {
        entry.action_type: entry
        for entry in AuditLogEntry.objects.filter(workspace_id=workspace.id)
    }
    assert set(entries) == {
        CreateTeamActionType.type,
        UpdateTeamActionType.type,
        CreateTeamSubjectActionType.type,
        DeleteTeamSubjectActionType.type,
        DeleteTeamActionType.type,
    }

    created = entries[CreateTeamActionType.type]
    assert created.action_params == {
        "name": "Sales",
        "team_id": team.id,
        "workspace_id": workspace.id,
        "subjects": subjects,
    }
    assert created.type == "Create team"
    assert created.description == f'Team "Sales" ({team.id}) created.'

    updated = entries[UpdateTeamActionType.type]
    assert updated.action_params == {
        "team_id": team.id,
        "original_name": "Sales",
        "name": "Marketing",
        "workspace_id": workspace.id,
        "subjects": subjects,
        "original_default_role_uid": None,
        "default_role_uid": "VIEWER",
    }
    assert updated.type == "Update team"
    assert updated.description == f'Team "Marketing" ({team.id}) updated.'

    subject_created = entries[CreateTeamSubjectActionType.type]
    assert subject_created.action_params == {
        "team_id": team.id,
        "team_name": "Marketing",
        "subject_id": subject_id,
        "subject_lookup": {"id": invitee.id},
        "subject_subject_type_natural_key": "auth.User",
    }
    assert subject_created.type == "Create team subject"
    assert subject_created.description == (
        f'Subject ({subject_id}) created in team "Marketing" ({team.id}) '
    )

    subject_deleted = entries[DeleteTeamSubjectActionType.type]
    assert subject_deleted.action_params == {
        "team_id": team.id,
        "team_name": "Marketing",
        "subject_id": subject_id,
        "subject_subject_id": invitee.id,
        "subject_subject_type_natural_key": "auth.User",
    }
    assert subject_deleted.type == "Delete team subject"

    deleted = entries[DeleteTeamActionType.type]
    assert deleted.action_params == {"team_id": team.id, "team_name": "Marketing"}
    assert deleted.type == "Delete team"
    assert deleted.description == f'Team "Marketing" ({team.id}) deleted.'
