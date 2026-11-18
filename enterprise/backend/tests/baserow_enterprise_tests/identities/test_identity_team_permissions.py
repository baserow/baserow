from django.urls import reverse

import pytest

from baserow.core.identities.service import IdentityService
from baserow.core.models import Operation, User
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.models import TeamSubject
from baserow_enterprise.teams.operations import (
    CreateTeamSubjectOperationType,
    DeleteTeamSubjectOperationType,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,can_add,can_remove,allowed",
    [
        ("create", False, False, False),
        ("create", True, False, True),
        ("replace", False, False, False),
        ("replace", True, False, False),
        ("replace", False, True, False),
        ("replace", True, True, True),
        ("retain", False, False, True),
        ("omit", False, False, True),
    ],
)
def test_identity_team_changes_require_membership_permissions(
    data_fixture,
    enterprise_data_fixture,
    api_client,
    enable_enterprise,
    synced_roles,
    action,
    can_add,
    can_remove,
    allowed,
):
    """Identity permissions alone cannot grant team access; denied requests roll back."""

    admin = data_fixture.create_user()
    editor, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[editor])
    old_team = enterprise_data_fixture.create_team(workspace=workspace)
    new_team = enterprise_data_fixture.create_team(workspace=workspace)
    identity = IdentityService().create_identity(
        admin, workspace, name="Original", team_ids=[old_team.id]
    )
    old_membership = TeamSubject.objects.get(team=old_team, subject_id=identity.id)

    role = Role.objects.create(
        uid="identity_editor", name="Identity editor", workspace=workspace
    )
    operations = ["identity.create", "identity.update"]
    if can_add:
        operations.append(CreateTeamSubjectOperationType.type)
    if can_remove:
        operations.append(DeleteTeamSubjectOperationType.type)
    role.operations.set(Operation.objects.filter(name__in=operations))
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(editor, workspace, role)

    payload = {"name": "Changed"}
    if action != "omit":
        payload["team_ids"] = [old_team.id if action == "retain" else new_team.id]
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    if action == "create":
        url = reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
        response = api_client.post(url, payload, format="json", **headers)
    else:
        url = reverse("api:identities:item", kwargs={"identity_id": identity.id})
        response = api_client.patch(url, payload, format="json", **headers)

    assert response.status_code == (200 if allowed else 401)
    identity.refresh_from_db()
    if not allowed:
        assert identity.first_name == "Original"
        assert list(
            User.objects_and_identities.filter(
                profile__user_type="identity", workspaceuser__workspace=workspace
            )
        ) == [identity]
        assert list(TeamSubject.objects.filter(team__workspace=workspace)) == [
            old_membership
        ]
    elif action == "create":
        created = User.objects_and_identities.get(id=response.json()["id"])
        assert created.first_name == "Changed"
        assert TeamSubject.objects.get(team=new_team).subject_id == created.id
        assert TeamSubject.objects.filter(id=old_membership.id).exists()
    else:
        assert identity.first_name == "Changed"
        memberships = TeamSubject.objects.filter(subject_id=identity.id)
        assert list(memberships.values_list("team_id", flat=True)) == [
            new_team.id if action == "replace" else old_team.id
        ]
