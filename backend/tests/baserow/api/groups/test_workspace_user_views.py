from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_list_workspace_users(api_client, data_fixture):
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

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": 99999}),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0]["permissions"] == "ADMIN"
    assert response_json[0]["name"] == user_1.first_name
    assert response_json[0]["email"] == user_1.email
    assert "created_on" in response_json[0]
    assert response_json[1]["permissions"] == "MEMBER"
    assert response_json[1]["name"] == user_2.first_name
    assert response_json[1]["email"] == user_2.email
    assert "created_on" in response_json[1]


@pytest.mark.django_db
def test_list_workspace_users_2fa_enabled(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    data_fixture.configure_base_totp(user_1)
    data_fixture.configure_totp(user_2)

    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_3, permissions="MEMBER"
    )

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["two_factor_auth"]["type"] == "totp"
    assert response_json[1]["two_factor_auth"]["type"] == "totp"
    assert response_json[0]["two_factor_auth"]["is_enabled"] is False
    assert response_json[1]["two_factor_auth"]["is_enabled"] is True
    assert response_json[2]["two_factor_auth"] == {}


@pytest.mark.django_db
def test_update_workspace_user(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )

    response = api_client.patch(
        reverse("api:workspaces:users:item", kwargs={"workspace_user_id": 99999}),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_USER_DOES_NOT_EXIST"

    response = api_client.patch(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        {"permissions": "ADMIN"},
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.patch(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        {"permissions": "ADMIN"},
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.patch(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        {"permissions": "ADMIN"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["permissions"] == "ADMIN"


@pytest.mark.django_db
def test_delete_workspace_user(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace_1 = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_1, permissions="ADMIN"
    )
    workspace_user = data_fixture.create_user_workspace(
        workspace=workspace_1, user=user_2, permissions="MEMBER"
    )
    user_1_workspace_user = WorkspaceUser.objects.get(
        user_id=user_1.id, workspace_id=workspace_1.id
    )

    response = api_client.delete(
        reverse("api:workspaces:users:item", kwargs={"workspace_user_id": 99999}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_USER_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.delete(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    # It should not be possible to delete yourself. The leave endpoint must be used
    # for that.
    response = api_client.delete(
        reverse(
            "api:workspaces:users:item",
            kwargs={"workspace_user_id": user_1_workspace_user.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_YOURSELF_FROM_GROUP"

    response = api_client.delete(
        reverse(
            "api:workspaces:users:item", kwargs={"workspace_user_id": workspace_user.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert WorkspaceUser.objects.all().count() == 1


@pytest.mark.django_db
def test_if_workspace_trashed_then_workspace_user_is_trashed(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    trashed_workspace = data_fixture.create_workspace(user=user_1)
    CoreHandler().delete_workspace_by_id(user_1, trashed_workspace.id)

    response = api_client.get(
        reverse(
            "api:workspaces:users:list", kwargs={"workspace_id": trashed_workspace.id}
        ),
        {"permissions": "MEMBER"},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    TrashHandler.restore_item(user_1, "workspace", trashed_workspace.id)

    response = api_client.get(
        reverse(
            "api:workspaces:users:list", kwargs={"workspace_id": trashed_workspace.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json[0]["email"] == user_1.email


@pytest.mark.django_db
def test_get_workspace_user_search(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(username="a", email="b")
    user_2, token_2 = data_fixture.create_user_and_token(username="b", email="b")
    user_3, token_3 = data_fixture.create_user_and_token(username="ab", email="b")

    workspace = data_fixture.create_workspace()

    data_fixture.create_user_workspace(
        workspace=workspace, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user_2, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user_3, permissions="MEMBER"
    )

    search = "a"

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id}),
        data={"search": search},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0]["permissions"] == "ADMIN"
    assert response_json[0]["name"] == user_1.first_name
    assert response_json[0]["email"] == user_1.email
    assert "created_on" in response_json[0]
    assert response_json[1]["permissions"] == "MEMBER"
    assert response_json[1]["name"] == user_3.first_name
    assert response_json[1]["email"] == user_3.email
    assert "created_on" in response_json[1]


@pytest.mark.django_db
def test_get_workspace_user_sorts(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(username="a", email="b")
    user_2, token_2 = data_fixture.create_user_and_token(username="b", email="b")
    user_3, token_3 = data_fixture.create_user_and_token(username="c", email="b")

    workspace = data_fixture.create_workspace()

    data_fixture.create_user_workspace(
        workspace=workspace, user=user_1, permissions="ADMIN"
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user_2, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user_3, permissions="MEMBER"
    )

    sorts = "-name"

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id}),
        data={"sorts": sorts},
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["permissions"] == "MEMBER"
    assert response_json[0]["name"] == user_3.first_name
    assert response_json[0]["email"] == user_3.email
    assert "created_on" in response_json[0]
    assert response_json[1]["permissions"] == "MEMBER"
    assert response_json[1]["name"] == user_2.first_name
    assert response_json[1]["email"] == user_2.email
    assert "created_on" in response_json[1]
    assert response_json[2]["permissions"] == "ADMIN"
    assert response_json[2]["name"] == user_1.first_name
    assert response_json[2]["email"] == user_1.email
    assert "created_on" in response_json[2]
