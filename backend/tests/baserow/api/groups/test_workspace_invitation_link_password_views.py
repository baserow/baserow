from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import WorkspaceInvitationLink, WorkspaceUser

User = get_user_model()

LINK_PASSWORD = "correct horse battery"


def _set_password(api_client, token, invitation_link, password):
    return api_client.patch(
        reverse(
            "api:workspaces:invitation_links:item",
            kwargs={"invitation_link_id": invitation_link.id},
        ),
        {"password": password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


def _auth(api_client, invitation_link, password):
    return api_client.post(
        reverse(
            "api:workspaces:invitation_links:auth",
            kwargs={"slug": invitation_link.slug},
        ),
        {"password": password},
        format="json",
    )


def _link_header(access_token):
    return {"HTTP_BASEROW_INVITATION_LINK_AUTHORIZATION": f"JWT {access_token}"}


@pytest.mark.django_db
def test_set_and_remove_invitation_link_password(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )

    response = _set_password(api_client, admin_token, invitation_link, "short")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = _set_password(api_client, admin_token, invitation_link, LINK_PASSWORD)
    assert response.status_code == HTTP_200_OK
    assert response.json()["has_password"] is True
    assert "password" not in response.json()
    invitation_link.refresh_from_db()
    # Only the hash is stored.
    assert invitation_link.password not in ("", LINK_PASSWORD)
    assert invitation_link.check_password(LINK_PASSWORD)

    # Renaming the link keeps its password.
    api_client.patch(
        reverse(
            "api:workspaces:invitation_links:item",
            kwargs={"invitation_link_id": invitation_link.id},
        ),
        {"name": "Renamed"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    invitation_link.refresh_from_db()
    assert invitation_link.has_password

    response = _set_password(api_client, admin_token, invitation_link, "")
    assert response.status_code == HTTP_200_OK
    assert response.json()["has_password"] is False
    invitation_link.refresh_from_db()
    assert invitation_link.password == ""


@pytest.mark.django_db
def test_members_cant_set_invitation_link_password(api_client, data_fixture):
    admin = data_fixture.create_user()
    member, member_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )

    response = _set_password(api_client, member_token, invitation_link, LINK_PASSWORD)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"
    invitation_link.refresh_from_db()
    assert not invitation_link.has_password


@pytest.mark.django_db
def test_invitation_link_auth(api_client, data_fixture):
    invitation_link = data_fixture.create_workspace_invitation_link()

    # A link without a password has nothing to unlock.
    assert _auth(api_client, invitation_link, "anything").status_code == (
        HTTP_401_UNAUTHORIZED
    )

    invitation_link.set_password(LINK_PASSWORD)
    invitation_link.save()

    assert _auth(api_client, invitation_link, "wrong password").status_code == (
        HTTP_401_UNAUTHORIZED
    )

    response = _auth(api_client, invitation_link, LINK_PASSWORD)
    assert response.status_code == HTTP_200_OK
    assert response.json()["access_token"]

    response = api_client.post(
        reverse(
            "api:workspaces:invitation_links:auth", kwargs={"slug": "doesnotexist"}
        ),
        {"password": LINK_PASSWORD},
        format="json",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_password_protected_invitation_link(api_client, data_fixture):
    admin = data_fixture.create_user(first_name="Admin")
    workspace = data_fixture.create_workspace(user=admin, name="Secret workspace")
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin
    )
    invitation_link.set_password(LINK_PASSWORD)
    invitation_link.save()
    url = reverse(
        "api:workspaces:invitation_links:slug", kwargs={"slug": invitation_link.slug}
    )

    # Nothing about the workspace is revealed before the password is entered.
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == (
        "ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED"
    )
    assert "Secret workspace" not in response.content.decode()

    response = api_client.get(url, **_link_header("not-a-token"))
    assert response.status_code == HTTP_401_UNAUTHORIZED

    access_token = _auth(api_client, invitation_link, LINK_PASSWORD).json()[
        "access_token"
    ]
    response = api_client.get(url, **_link_header(access_token))
    assert response.status_code == HTTP_200_OK
    assert response.json()["workspace"] == "Secret workspace"


@pytest.mark.django_db
def test_token_of_another_link_doesnt_unlock(api_client, data_fixture):
    first_link = data_fixture.create_workspace_invitation_link()
    second_link = data_fixture.create_workspace_invitation_link()
    for link in [first_link, second_link]:
        link.set_password(LINK_PASSWORD)
        link.save()

    access_token = _auth(api_client, first_link, LINK_PASSWORD).json()["access_token"]
    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:slug", kwargs={"slug": second_link.slug}
        ),
        **_link_header(access_token),
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_join_password_protected_invitation_link(api_client, data_fixture):
    admin, admin_token = data_fixture.create_user_and_token()
    user, user_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    _set_password(api_client, admin_token, invitation_link, LINK_PASSWORD)
    url = reverse(
        "api:workspaces:invitation_links:join", kwargs={"slug": invitation_link.slug}
    )

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {user_token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == (
        "ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED"
    )
    assert not WorkspaceUser.objects.filter(user=user).exists()

    access_token = _auth(api_client, invitation_link, LINK_PASSWORD).json()[
        "access_token"
    ]

    # Changing the password invalidates the tokens handed out before.
    _set_password(api_client, admin_token, invitation_link, "another password")
    response = api_client.post(
        url, HTTP_AUTHORIZATION=f"JWT {user_token}", **_link_header(access_token)
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    access_token = _auth(api_client, invitation_link, "another password").json()[
        "access_token"
    ]
    response = api_client.post(
        url, HTTP_AUTHORIZATION=f"JWT {user_token}", **_link_header(access_token)
    )
    assert response.status_code == HTTP_200_OK
    assert WorkspaceUser.objects.get(user=user).workspace_id == workspace.id


@pytest.mark.django_db
def test_sign_up_via_password_protected_invitation_link(api_client, data_fixture):
    data_fixture.create_password_provider()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    invitation_link = data_fixture.create_workspace_invitation_link(
        workspace=workspace, created_by=admin, permissions="MEMBER"
    )
    invitation_link.set_password(LINK_PASSWORD)
    invitation_link.save()
    # The link is the only way in, so the signup depends on the password.
    data_fixture.update_settings(
        allow_new_signups=False, allow_signups_via_workspace_invitations=True
    )
    body = {
        "name": "Newcomer",
        "email": "newcomer@test.nl",
        "password": "thisIsAValidPassword",
        "workspace_invitation_link_slug": invitation_link.slug,
    }

    response = api_client.post(reverse("api:user:index"), body, format="json")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == (
        "ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED"
    )
    assert not User.objects.filter(email="newcomer@test.nl").exists()

    access_token = _auth(api_client, invitation_link, LINK_PASSWORD).json()[
        "access_token"
    ]
    response = api_client.post(
        reverse("api:user:index"),
        {**body, "workspace_invitation_link_token": access_token},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    user = User.objects.get(email="newcomer@test.nl")
    assert WorkspaceUser.objects.get(user=user).workspace_id == workspace.id


@pytest.mark.django_db
def test_invitation_link_password_db_default(data_fixture):
    invitation_link = data_fixture.create_workspace_invitation_link()
    assert WorkspaceInvitationLink.objects.get(id=invitation_link.id).password == ""
    assert not invitation_link.has_password
