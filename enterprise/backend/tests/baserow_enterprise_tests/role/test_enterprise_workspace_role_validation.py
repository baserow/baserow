from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.exceptions import InvalidWorkspaceRole
from baserow.core.handler import CoreHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid", ["ADMIN", "MEMBER", "BUILDER", "EDITOR", "VIEWER", "NO_ACCESS"]
)
def test_handler_accepts_enterprise_workspace_roles(data_fixture, role_uid):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace, permissions="MEMBER"
    )
    handler = CoreHandler()

    invitation = handler.create_workspace_invitation(
        admin, workspace, "invited@test.nl", role_uid
    )
    assert invitation.permissions == role_uid
    invitation = handler.update_workspace_invitation(admin, invitation, role_uid)
    assert invitation.permissions == role_uid
    workspace_user = handler.update_workspace_user(
        admin, workspace_user, permissions=role_uid
    )
    assert workspace_user.permissions == role_uid


@pytest.mark.django_db
def test_handler_rejects_unavailable_enterprise_workspace_roles(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    other_workspace = data_fixture.create_workspace()
    Role.objects.create(uid="OTHER_WORKSPACE_ROLE", workspace=other_workspace)
    hidden_role_uid = Role.objects.filter(hidden=True).first().uid
    handler = CoreHandler()

    for role_uid in ["SUPERUSER", "OTHER_WORKSPACE_ROLE", hidden_role_uid]:
        with pytest.raises(InvalidWorkspaceRole):
            handler.create_workspace_invitation(
                admin, workspace, "invited@test.nl", role_uid
            )


@pytest.mark.django_db
def test_handler_accepts_only_basic_roles_without_rbac(data_fixture, settings):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    handler = CoreHandler()
    settings.PERMISSION_MANAGERS = [
        manager for manager in settings.PERMISSION_MANAGERS if manager != "role"
    ]

    with pytest.raises(InvalidWorkspaceRole):
        handler.create_workspace_invitation(
            admin, workspace, "invited@test.nl", "VIEWER"
        )
    invitation = handler.create_workspace_invitation(
        admin, workspace, "invited@test.nl", "MEMBER"
    )
    assert invitation.permissions == "MEMBER"


@pytest.mark.django_db
def test_workspace_endpoints_accept_enterprise_roles(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace, permissions="MEMBER"
    )

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace.id}
        ),
        {"email": "invited@test.nl", "permissions": "VIEWER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    invitation_id = response.json()["id"]

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation_id},
        ),
        {"permissions": "EDITOR"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "EDITOR"

    url = reverse(
        "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
    )
    response = api_client.patch(
        url,
        {"permissions": "VIEWER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "VIEWER"

    response = api_client.patch(
        url,
        {"permissions": "SUPERUSER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_WORKSPACE_ROLE"
