from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import WorkspaceInvitation
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.role.actions import (
    DeleteScopedInvitationActionType,
    UpdateScopedInvitationActionType,
)
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, WorkspaceScopedInvitation

BASE_URL = "http://localhost:3000/invite"


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def setup_workspace(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, user=user)
    return user, token, workspace, database, table


def create_scoped_invitation(
    user, workspace, table, email="foo@bar.com", role="EDITOR"
):
    return RoleAssignmentHandler().create_scoped_invitation(
        user, workspace, email, Role.objects.get(uid=role), table, BASE_URL
    )


@pytest.mark.django_db
def test_create_scoped_invitation(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)

    response = api_client.post(
        reverse(
            "api:enterprise:role:scoped_invitations",
            kwargs={"workspace_id": workspace.id},
        ),
        {
            "email": "foo@bar.com",
            "role": "EDITOR",
            "scope_id": table.id,
            "scope_type": "database_table",
            "base_url": BASE_URL,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "id": AnyInt(),
        "invitation_id": AnyInt(),
        "email": "foo@bar.com",
        "role": "EDITOR",
        "scope_id": table.id,
        "scope_type": "database_table",
        "created_on": response_json["created_on"],
    }
    invitation = WorkspaceInvitation.objects.get(id=response_json["invitation_id"])
    assert invitation.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert WorkspaceScopedInvitation.objects.get(id=response_json["id"]).scope == table


@pytest.mark.django_db
def test_create_scoped_invitation_errors(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)
    member = data_fixture.create_user(email="member@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="VIEWER"
    )
    viewer, viewer_token = data_fixture.create_user_and_token(email="viewer@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=viewer, permissions="VIEWER"
    )
    _, outsider_token = data_fixture.create_user_and_token(email="outsider@bar.com")
    url = reverse(
        "api:enterprise:role:scoped_invitations", kwargs={"workspace_id": workspace.id}
    )
    body = {
        "email": "foo@bar.com",
        "role": "EDITOR",
        "scope_id": table.id,
        "scope_type": "database_table",
        "base_url": BASE_URL,
    }

    response = api_client.post(
        url,
        {**body, "email": "member@bar.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GROUP_USER_ALREADY_EXISTS"

    response = api_client.post(
        url,
        {**body, "role": "DOES_NOT_EXIST"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROLE_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {**body, "scope_id": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        url,
        {**body, "scope_id": 999999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPE_DOES_NOT_EXIST"

    # A member without the role operation on the table.
    response = api_client.post(
        url, body, format="json", HTTP_AUTHORIZATION=f"JWT {viewer_token}"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # A user outside the workspace.
    response = api_client.post(
        url, body, format="json", HTTP_AUTHORIZATION=f"JWT {outsider_token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    assert WorkspaceScopedInvitation.objects.count() == 0


@pytest.mark.django_db
def test_list_scoped_invitations(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)
    other_table = data_fixture.create_database_table(database=database, user=user)
    first = create_scoped_invitation(user, workspace, table)
    create_scoped_invitation(user, workspace, other_table, email="other@bar.com")

    response = api_client.get(
        reverse(
            "api:enterprise:role:scoped_invitations",
            kwargs={"workspace_id": workspace.id},
        ),
        {"scope_id": table.id, "scope_type": "database_table"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == first.id
    assert response_json[0]["email"] == "foo@bar.com"
    assert response_json[0]["role"] == "EDITOR"

    response = api_client.get(
        reverse(
            "api:enterprise:role:scoped_invitations",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


@pytest.mark.django_db
def test_list_scoped_invitations_query_count_is_constant(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)
    url = reverse(
        "api:enterprise:role:scoped_invitations", kwargs={"workspace_id": workspace.id}
    )
    params = {"scope_id": table.id, "scope_type": "database_table"}
    create_scoped_invitation(user, workspace, table, email="one@bar.com")

    with CaptureQueriesContext(connection) as with_one:
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert len(response.json()) == 1

    for i in range(4):
        create_scoped_invitation(user, workspace, table, email=f"more{i}@bar.com")

    with CaptureQueriesContext(connection) as with_five:
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert len(response.json()) == 5

    assert len(with_five.captured_queries) == len(with_one.captured_queries)


@pytest.mark.django_db
def test_update_scoped_invitation(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)
    scoped_invitation = create_scoped_invitation(user, workspace, table)

    response = api_client.patch(
        reverse(
            "api:enterprise:role:scoped_invitation",
            kwargs={"scoped_invitation_id": scoped_invitation.id},
        ),
        {"role": "VIEWER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["role"] == "VIEWER"
    scoped_invitation.refresh_from_db()
    assert scoped_invitation.role.uid == "VIEWER"

    # The change is written to the audit log like a workspace invitation change.
    entry = AuditLogEntry.objects.get(action_type=UpdateScopedInvitationActionType.type)
    assert entry.user_id == user.id
    assert entry.workspace_id == workspace.id
    assert entry.action_params == {
        "scoped_invitation_id": scoped_invitation.id,
        "invitation_id": scoped_invitation.invitation_id,
        "email": "foo@bar.com",
        "role_uid": "VIEWER",
        "original_role_uid": "EDITOR",
        "scope_type_name": "database_table",
        "scope_id": table.id,
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
    }
    assert entry.description == (
        f'Invitation ({scoped_invitation.invitation_id}) role for "foo@bar.com" on '
        f'"database_table" ({table.id}) in "{workspace.name}" ({workspace.id}) '
        "changed from EDITOR to VIEWER."
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:role:scoped_invitation",
            kwargs={"scoped_invitation_id": 999999},
        ),
        {"role": "VIEWER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPED_INVITATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_delete_scoped_invitation(api_client, data_fixture):
    user, token, workspace, database, table = setup_workspace(data_fixture)
    other_table = data_fixture.create_database_table(database=database, user=user)
    first = create_scoped_invitation(user, workspace, table)
    second = create_scoped_invitation(user, workspace, other_table, role="VIEWER")

    response = api_client.delete(
        reverse(
            "api:enterprise:role:scoped_invitation",
            kwargs={"scoped_invitation_id": first.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert list(WorkspaceScopedInvitation.objects.all()) == [second]
    assert WorkspaceInvitation.objects.filter(id=first.invitation_id).exists()

    # Revoking is written to the audit log like deleting a workspace invitation.
    entry = AuditLogEntry.objects.get(action_type=DeleteScopedInvitationActionType.type)
    assert entry.user_id == user.id
    assert entry.workspace_id == workspace.id
    assert entry.action_params == {
        "scoped_invitation_id": first.id,
        "invitation_id": first.invitation_id,
        "email": "foo@bar.com",
        "role_uid": "EDITOR",
        "scope_type_name": "database_table",
        "scope_id": table.id,
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
    }
    assert entry.description == (
        f'Invitation ({first.invitation_id}) role EDITOR for "foo@bar.com" on '
        f'"database_table" ({table.id}) in "{workspace.name}" ({workspace.id}) '
        "revoked."
    )
