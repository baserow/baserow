from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.exceptions import InvalidWorkspaceRole
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitation


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid", ["ADMIN", "MEMBER"])
def test_handler_accepts_basic_workspace_roles(data_fixture, role_uid):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    member = data_fixture.create_user()
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER"
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
@pytest.mark.parametrize("role_uid", ["SUPERUSER", "VIEWER", "", "admin"])
def test_handler_rejects_unknown_workspace_roles(data_fixture, role_uid):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    member = data_fixture.create_user()
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER"
    )
    invitation = data_fixture.create_workspace_invitation(
        invited_by=admin, workspace=workspace, permissions="MEMBER"
    )
    handler = CoreHandler()

    with pytest.raises(InvalidWorkspaceRole):
        handler.create_workspace_invitation(
            admin, workspace, "invited@test.nl", role_uid
        )
    assert not WorkspaceInvitation.objects.filter(email="invited@test.nl").exists()

    with pytest.raises(InvalidWorkspaceRole):
        handler.update_workspace_invitation(admin, invitation, role_uid)
    invitation.refresh_from_db()
    assert invitation.permissions == "MEMBER"

    with pytest.raises(InvalidWorkspaceRole):
        handler.update_workspace_user(admin, workspace_user, permissions=role_uid)
    workspace_user.refresh_from_db()
    assert workspace_user.permissions == "MEMBER"


@pytest.mark.django_db
def test_create_workspace_invitation_endpoint_validates_role(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    url = reverse(
        "api:workspaces:invitations:list", kwargs={"workspace_id": workspace.id}
    )

    response = api_client.post(
        url,
        {"email": "invited@test.nl", "permissions": "SUPERUSER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_WORKSPACE_ROLE"
    assert not WorkspaceInvitation.objects.exists()

    for role_uid in ["ADMIN", "MEMBER"]:
        response = api_client.post(
            url,
            {"email": f"{role_uid.lower()}@test.nl", "permissions": role_uid},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["permissions"] == role_uid


@pytest.mark.django_db
def test_update_workspace_invitation_endpoint_validates_role(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    invitation = data_fixture.create_workspace_invitation(
        invited_by=admin, workspace=workspace, permissions="MEMBER"
    )
    url = reverse(
        "api:workspaces:invitations:item",
        kwargs={"workspace_invitation_id": invitation.id},
    )

    response = api_client.patch(
        url,
        {"permissions": "SUPERUSER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_WORKSPACE_ROLE"
    invitation.refresh_from_db()
    assert invitation.permissions == "MEMBER"

    for role_uid in ["ADMIN", "MEMBER"]:
        response = api_client.patch(
            url,
            {"permissions": role_uid},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["permissions"] == role_uid


@pytest.mark.django_db
def test_update_workspace_user_endpoint_validates_role(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace, permissions="MEMBER"
    )
    url = reverse(
        "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
    )

    response = api_client.patch(
        url,
        {"permissions": "SUPERUSER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_WORKSPACE_ROLE"
    workspace_user.refresh_from_db()
    assert workspace_user.permissions == "MEMBER"

    for role_uid in ["ADMIN", "MEMBER"]:
        response = api_client.patch(
            url,
            {"permissions": role_uid},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["permissions"] == role_uid
