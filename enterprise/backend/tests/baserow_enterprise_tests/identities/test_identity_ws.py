from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.core.identities.service import IdentityService
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow.ws.tasks import broadcast_to_permitted_users
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import TeamSubject


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize("event", ["create", "update", "delete", "restore"])
def test_identity_events_only_reach_users_allowed_to_list_identities(
    data_fixture, enable_enterprise, synced_roles, event
):
    """Lifecycle events use real RBAC checks before reaching the user transport."""

    admin = data_fixture.create_user()
    admin.web_socket_id = "origin"
    members = [data_fixture.create_user() for _ in range(4)]
    workspace = data_fixture.create_workspace(user=admin, members=members)
    handler = RoleAssignmentHandler()
    for member, role_uid in zip(members, ["BUILDER", "EDITOR", "VIEWER", "NO_ACCESS"]):
        handler.assign_role(member, workspace, handler.get_role_by_uid(role_uid))

    service = IdentityService()
    identity = service.create_identity(admin, workspace, name="Private identity")
    if event == "restore":
        service.delete_identity(admin, identity)

    with (
        patch(
            "baserow.ws.signals.broadcast_to_permitted_users.delay",
            side_effect=broadcast_to_permitted_users,
        ),
        patch("baserow.ws.tasks.broadcast_to_users") as broadcast,
        patch("baserow.ws.signals.broadcast_to_group") as workspace_broadcast,
    ):
        if event == "create":
            identity = service.create_identity(
                admin, workspace, name="Private identity"
            )
        elif event == "update":
            service.update_identity(admin, identity, name="Updated private identity")
        elif event == "delete":
            service.delete_identity(admin, identity)
        else:
            TrashHandler.restore_item(admin, "identity", identity.profile.id)

    broadcast.assert_called_once()
    user_ids, payload = broadcast.call_args.args
    # Admins and Builders can list identities; Editors, Viewers and No access cannot.
    assert set(user_ids) == {admin.id, members[0].id}
    expected_type = {
        "create": "identity_created",
        "update": "identity_updated",
        "delete": "identity_deleted",
        "restore": "identity_created",
    }[event]
    assert payload["type"] == expected_type
    assert payload["workspace_id"] == workspace.id
    assert broadcast.call_args.kwargs["ignore_web_socket_id"] == (
        None if event == "restore" else "origin"
    )
    workspace_broadcast.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize(
    "change", ["add", "remove", "replace", "rename", "trash", "restore", "rollback"]
)
def test_team_changes_broadcast_current_identity_teams(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles, change
):
    """Team edits send committed, permission-filtered summaries, including to the caller."""
    admin = data_fixture.create_user()
    admin.web_socket_id = "origin"
    viewer = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[viewer])
    roles = RoleAssignmentHandler()
    roles.assign_role(viewer, workspace, roles.get_role_by_uid("VIEWER"))
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Team")
    identity = IdentityService().create_identity(
        admin, workspace, name="Writer", team_ids=[] if change == "add" else [team.id]
    )
    handler = TeamHandler()
    if change == "restore":
        handler.delete_team(admin, team)

    with (
        patch(
            "baserow.ws.signals.broadcast_to_permitted_users.delay",
            side_effect=broadcast_to_permitted_users,
        ),
        patch("baserow.ws.tasks.broadcast_to_users") as broadcast,
    ):
        with transaction.atomic():
            if change == "add":
                handler.create_subject(
                    admin, {"id": identity.id}, UserSubjectType.type, team
                )
            elif change in {"remove", "rollback"}:
                membership = TeamSubject.objects.get(team=team, subject_id=identity.id)
                handler.delete_subject(admin, membership)
            elif change in {"replace", "rename"}:
                subjects = (
                    []
                    if change == "replace"
                    else [
                        {
                            "subject_id": identity.id,
                            "subject_type": UserSubjectType.type,
                        }
                    ]
                )
                handler.update_team(admin, team, "Renamed", subjects=subjects)
            elif change == "trash":
                handler.delete_team(admin, team)
            else:
                TrashHandler.restore_item(admin, "team", team.id)
            broadcast.assert_not_called()
            if change == "rollback":
                transaction.set_rollback(True)
        if change == "rollback":
            broadcast.assert_not_called()
            return

    assert broadcast.call_count >= 1
    expected_teams = (
        []
        if change in {"remove", "replace", "trash"}
        else [{"id": team.id, "name": team.name}]
    )
    for call in broadcast.call_args_list:
        recipients, payload = call.args
        assert recipients == [admin.id]
        assert payload["type"] == "identity_updated"
        assert payload["identity"]["id"] == identity.id
        assert payload["identity"]["teams"] == expected_teams
        assert call.kwargs["ignore_web_socket_id"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
def test_human_team_changes_do_not_broadcast_an_identity(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Only identity memberships should trigger identity metadata broadcasts."""
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    team = enterprise_data_fixture.create_team(workspace=workspace)
    data_fixture.create_identity(workspace=workspace, name="Another identity")
    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as broadcast:
        TeamHandler().create_subject(admin, {"id": member.id}, "auth.User", team)
    broadcast.assert_not_called()
