from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceInvitationLink, WorkspaceUser
from baserow.core.trash.handler import TrashHandler

User = get_user_model()


@pytest.mark.django_db
def test_list_workspace_invitation_links(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    member, member_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    other_workspace = data_fixture.create_workspace()
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    data_fixture.create_workspace_invitation_link(workspace=other_workspace)

    response = api_client.get(
        reverse("api:workspaces:invitation_links:list", kwargs={"workspace_id": 0}),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": other_workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {member_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == invitation_link.id
    assert response_json[0]["workspace"] == workspace.id
    assert response_json[0]["slug"] == invitation_link.slug
    assert response_json[0]["permissions"] == "MEMBER"
    assert "created_on" in response_json[0]


@pytest.mark.django_db
def test_create_workspace_invitation_link(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    member, member_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    url = reverse(
        "api:workspaces:invitation_links:list", kwargs={"workspace_id": workspace.id}
    )

    response = api_client.post(
        url,
        {"permissions": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {member_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.post(
        url,
        {"permissions": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    invitation_link = WorkspaceInvitationLink.objects.get(id=response_json["id"])
    assert response_json["workspace"] == workspace.id
    assert response_json["slug"] == invitation_link.slug
    assert response_json["permissions"] == "MEMBER"
    assert invitation_link.created_by_id == admin.id


@pytest.mark.django_db
def test_create_workspace_invitation_link_feature_disabled(
    api_client, data_fixture, settings
):
    admin, admin_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    settings.FEATURE_FLAGS = []

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": workspace.id},
        ),
        {"permissions": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert WorkspaceInvitationLink.objects.count() == 0


@pytest.mark.django_db
def test_create_workspace_invitation_link_signups_disabled(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:list",
            kwargs={"workspace_id": workspace.id},
        ),
        {"permissions": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED"
    )
    assert WorkspaceInvitationLink.objects.count() == 0


@pytest.mark.django_db
def test_update_workspace_invitation_link(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    member, member_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    url = reverse(
        "api:workspaces:invitation_links:item",
        kwargs={"invitation_link_id": invitation_link.id},
    )

    response = api_client.patch(
        reverse(
            "api:workspaces:invitation_links:item",
            kwargs={"invitation_link_id": 0},
        ),
        {"permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"

    response = api_client.patch(
        url,
        {"permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {member_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.patch(
        url,
        {"permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "ADMIN"
    invitation_link.refresh_from_db()
    assert invitation_link.permissions == "ADMIN"


@pytest.mark.django_db
def test_delete_workspace_invitation_link(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    member, member_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )
    url = reverse(
        "api:workspaces:invitation_links:item",
        kwargs={"invitation_link_id": invitation_link.id},
    )

    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {member_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {admin_token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert WorkspaceInvitationLink.objects.count() == 0

    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:slug",
            kwargs={"slug": invitation_link.slug},
        )
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_workspace_invitation_link(api_client, data_fixture, settings):
    admin = data_fixture.create_user(first_name="Bram")
    workspace = data_fixture.create_workspace(user=admin, name="Widelab")
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    url = reverse(
        "api:workspaces:invitation_links:slug", kwargs={"slug": invitation_link.slug}
    )

    response = api_client.get(
        reverse("api:workspaces:invitation_links:slug", kwargs={"slug": "unknown"})
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"

    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "slug": invitation_link.slug,
        "invited_by": "Bram",
        "workspace": "Widelab",
        "workspace_id": workspace.id,
    }

    TrashHandler.trash(admin, workspace, None, workspace)
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND

    settings.FEATURE_FLAGS = []
    response = api_client.get(url)
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.django_db
def test_join_workspace_via_invitation_link(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    newcomer, newcomer_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    url = reverse(
        "api:workspaces:invitation_links:join", kwargs={"slug": invitation_link.slug}
    )

    response = api_client.post(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:workspaces:invitation_links:join", kwargs={"slug": "unknown"}),
        HTTP_AUTHORIZATION=f"JWT {newcomer_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {newcomer_token}")
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == workspace.id
    assert response_json["permissions"] == "MEMBER"
    assert WorkspaceUser.objects.get(user=newcomer).workspace_id == workspace.id

    # An existing member keeps their current role.
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {admin_token}")
    assert response.status_code == HTTP_200_OK
    assert response.json()["permissions"] == "ADMIN"
    assert WorkspaceUser.objects.filter(workspace=workspace).count() == 2


@pytest.mark.django_db
def test_join_workspace_via_invitation_link_feature_disabled(
    api_client, data_fixture, settings
):
    newcomer, newcomer_token = data_fixture.create_user_and_token()
    invitation_link = data_fixture.create_workspace_invitation_link()
    settings.FEATURE_FLAGS = []

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:join",
            kwargs={"slug": invitation_link.slug},
        ),
        HTTP_AUTHORIZATION=f"JWT {newcomer_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert not WorkspaceUser.objects.filter(user=newcomer).exists()


@pytest.mark.django_db
def test_sign_up_via_invitation_link(api_client, data_fixture):
    data_fixture.create_password_provider()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=True
    )

    for email in ["first@test.nl", "second@test.nl"]:
        response = api_client.post(
            reverse("api:user:index"),
            {
                "name": "Newcomer",
                "email": email,
                "password": "thisIsAValidPassword",
                "workspace_invitation_link_slug": invitation_link.slug,
            },
            format="json",
        )
        assert response.status_code == HTTP_200_OK

        user = User.objects.get(email=email)
        assert WorkspaceUser.objects.get(user=user).workspace_id == workspace.id
        assert WorkspaceUser.objects.get(user=user).permissions == "MEMBER"
        assert user.profile.completed_onboarding is True
        # Unlike an email invitation, a link doesn't prove the email address.
        assert user.profile.email_verified is False

    # No personal workspace is created for people who sign up through a link.
    assert Workspace.objects.count() == 1


@pytest.mark.django_db
def test_sign_up_via_invitation_link_respects_signup_settings(api_client, data_fixture):
    data_fixture.create_password_provider()
    invitation_link = data_fixture.create_workspace_invitation_link()
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=False
    )

    response = api_client.post(
        reverse("api:user:index"),
        {
            "name": "Newcomer",
            "email": "newcomer@test.nl",
            "password": "thisIsAValidPassword",
            "workspace_invitation_link_slug": invitation_link.slug,
        },
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DISABLED_SIGNUP"
    assert not User.objects.filter(email="newcomer@test.nl").exists()


@pytest.mark.django_db
def test_sign_up_via_invitation_link_invalid(api_client, data_fixture):
    data_fixture.create_password_provider()
    invitation = data_fixture.create_workspace_invitation(email="newcomer@test.nl")
    invitation_link = data_fixture.create_workspace_invitation_link()

    response = api_client.post(
        reverse("api:user:index"),
        {
            "name": "Newcomer",
            "email": "newcomer@test.nl",
            "password": "thisIsAValidPassword",
            "workspace_invitation_link_slug": "unknown",
        },
        format="json",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:user:index"),
        {
            "name": "Newcomer",
            "email": "newcomer@test.nl",
            "password": "thisIsAValidPassword",
            "workspace_invitation_link_slug": invitation_link.slug,
            "workspace_invitation_token": (
                CoreHandler().get_workspace_invitation_signer().dumps(invitation.id)
            ),
        },
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert not User.objects.filter(email="newcomer@test.nl").exists()
