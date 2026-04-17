from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitation, WorkspaceUser
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_list_workspace_invitations(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace(user=user_1)
    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    with freeze_time("2020-01-02 12:00"):
        invitation_1 = data_fixture.create_workspace_invitation(
            workspace=workspace_1,
            invited_by=user_1,
            email="test3@test.nl",
            permissions="MEMBER",
        )
    invitation_2 = data_fixture.create_workspace_invitation(
        workspace=workspace_1,
        invited_by=user_1,
        email="test4@test.nl",
        permissions="ADMIN",
    )

    response = api_client.get(
        reverse("api:workspaces:invitations:list", kwargs={"workspace_id": 999999}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_2.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"
    assert (
        response.json()["detail"] == "You need workspace.list_invitations permissions."
    )

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == invitation_1.id
    assert response_json[0]["workspace"] == invitation_1.workspace_id
    assert response_json[0]["email"] == "test3@test.nl"
    assert response_json[0]["permissions"] == "MEMBER"
    assert response_json[0]["created_on"] == "2020-01-02T12:00:00Z"
    assert response_json[1]["id"] == invitation_2.id


@pytest.mark.django_db
def test_create_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace(user=user_1)
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_3, permissions="MEMBER"
    )

    response = api_client.post(
        reverse("api:workspaces:invitations:list", kwargs={"workspace_id": 99999}),
        {
            "email": "test@test.nl",
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": "test@test.nl",
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": user_3.email,
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GROUP_USER_ALREADY_EXISTS"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": "test@test.nl",
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": "test@test.nl",
            "permissions": "ADMIN",
            "base_url": "http://test.nl:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_HOSTNAME_IS_NOT_ALLOWED"

    # Custom messages are no longer supported: any `message` in the request body is
    # silently ignored and neither persisted nor returned.
    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": "test0@test.nl",
            "permissions": "ADMIN",
            "message": "Test",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    invitation = WorkspaceInvitation.objects.all().first()
    assert response_json["id"] == invitation.id
    assert response_json["workspace"] == invitation.workspace_id
    assert response_json["email"] == "test0@test.nl"
    assert response_json["permissions"] == "ADMIN"
    assert invitation.message == ""
    assert "message" not in response_json
    assert "created_on" in response_json

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace_1.id}
        ),
        {
            "email": "test2@test.nl",
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_get_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email="test0@test.nl",
        permissions="ADMIN",
    )

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item", kwargs={"workspace_invitation_id": 99999}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == invitation.id
    assert response_json["workspace"] == invitation.workspace_id
    assert response_json["email"] == invitation.email
    assert response_json["permissions"] == invitation.permissions
    assert "created_on" in response_json


@pytest.mark.django_db
def test_update_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email="test0@test.nl",
        permissions="ADMIN",
    )

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item", kwargs={"workspace_invitation_id": 99999}
        ),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == invitation.id
    assert response_json["workspace"] == invitation.workspace_id
    assert response_json["email"] == invitation.email
    assert response_json["permissions"] == "MEMBER"
    assert "created_on" in response_json

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        {
            "email": "should.be@ignored.nl",
            "permissions": "ADMIN",
            "base_url": "http://should.be.ignored:3000/invite",
        },
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == invitation.id
    assert response_json["workspace"] == invitation.workspace_id
    assert response_json["email"] == invitation.email
    assert response_json["permissions"] == "ADMIN"


@pytest.mark.django_db
def test_delete_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email="test0@test.nl",
        permissions="ADMIN",
    )

    response = api_client.delete(
        reverse(
            "api:workspaces:invitations:item", kwargs={"workspace_invitation_id": 99999}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.delete(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.delete(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert WorkspaceInvitation.objects.all().count() == 0


@pytest.mark.django_db
def test_accept_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace()
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email="test1@test.nl",
        permissions="ADMIN",
    )

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:accept",
            kwargs={"workspace_invitation_id": 99999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:accept",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GROUP_INVITATION_EMAIL_MISMATCH"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:accept",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "id" in response_json
    assert response_json["permissions"] == "ADMIN"
    assert response_json["name"] == workspace_1.name
    assert response_json["order"] == 1
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 1


@pytest.mark.django_db
def test_reject_workspace_invitation(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace()
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email="test1@test.nl",
        permissions="ADMIN",
    )

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:reject",
            kwargs={"workspace_invitation_id": 99999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:reject",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GROUP_INVITATION_EMAIL_MISMATCH"

    response = api_client.post(
        reverse(
            "api:workspaces:invitations:reject",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert WorkspaceInvitation.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 0


@pytest.mark.django_db
def test_get_workspace_invitation_by_token(api_client, data_fixture):
    data_fixture.create_user(email="test1@test.nl")
    # `message` is a deprecated column kept on the model; even when a legacy row
    # still has a value, the API must not expose it.
    invitation = data_fixture.create_workspace_invitation(
        email="test0@test.nl", permissions="ADMIN", message="Legacy message"
    )
    invitation_2 = data_fixture.create_workspace_invitation(
        email="test1@test.nl",
        permissions="ADMIN",
    )

    handler = CoreHandler()
    signer = handler.get_workspace_invitation_signer()

    response = api_client.get(
        reverse("api:workspaces:invitations:token", kwargs={"token": "INVALID"}),
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "BAD_TOKEN_SIGNATURE"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:token", kwargs={"token": signer.dumps(99999)}
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:token",
            kwargs={"token": signer.dumps(invitation.id)},
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == invitation.id
    assert response_json["invited_by"] == invitation.invited_by.first_name
    assert response_json["workspace"] == invitation.workspace.name
    assert response_json["email"] == invitation.email
    assert "message" not in response_json
    assert response_json["email_exists"] is False
    assert "created_on" in response_json

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:token",
            kwargs={"token": signer.dumps(invitation_2.id)},
        ),
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == invitation_2.id
    assert response_json["email_exists"] is True


@pytest.mark.django_db
def test_when_workspace_is_trashed_so_is_invitation(data_fixture, api_client):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    visible_workspace = data_fixture.create_workspace(user=user_1)
    trashed_workspace = data_fixture.create_workspace(user=user_1)
    visible_invitation = data_fixture.create_workspace_invitation(
        workspace=visible_workspace,
        invited_by=user_1,
        email="test4@test.nl",
        permissions="ADMIN",
    )
    trashed_invitation = data_fixture.create_workspace_invitation(
        workspace=trashed_workspace,
        invited_by=user_1,
        email="test4@test.nl",
        permissions="ADMIN",
    )
    # Put the trashed_workspace in the trash
    CoreHandler().delete_workspace_by_id(user_1, trashed_workspace.id)

    # The trashed workspace 404's when asking for invitations
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list",
            kwargs={"workspace_id": trashed_workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    # The untrashed workspace still works like normal
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list",
            kwargs={"workspace_id": visible_workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == visible_invitation.id

    # can't view the invitation for the trashed workspace
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": trashed_invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    TrashHandler.restore_item(user_1, "workspace", trashed_workspace.id)

    # after restoring the workspace is visible again
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list",
            kwargs={"workspace_id": trashed_workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == trashed_invitation.id

    # after restoring the invitation is visible again
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": trashed_invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == trashed_invitation.id
