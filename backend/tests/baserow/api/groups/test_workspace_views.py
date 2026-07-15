from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceUser
from baserow.test_utils.helpers import is_dict_subset


@pytest.mark.django_db
def test_list_workspaces(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    user_workspace_2 = data_fixture.create_user_workspace(
        user=user, order=2, permissions="ADMIN"
    )
    user_workspace_1 = data_fixture.create_user_workspace(
        user=user, order=1, permissions="MEMBER"
    )
    data_fixture.create_workspace()

    response = api_client.get(
        reverse("api:workspaces:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == user_workspace_1.workspace.id
    assert response_json[0]["order"] == 1
    assert response_json[0]["name"] == user_workspace_1.workspace.name
    assert response_json[0]["permissions"] == "MEMBER"
    assert response_json[1]["id"] == user_workspace_2.workspace.id
    assert response_json[1]["order"] == 2
    assert response_json[1]["name"] == user_workspace_2.workspace.name
    assert response_json[1]["permissions"] == "ADMIN"
    assert response_json[0]["unread_notifications_count"] == 0


@pytest.mark.django_db
def test_list_workspaces_with_users(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    user_workspace_1 = data_fixture.create_user_workspace(
        user=user, order=1, permissions="MEMBER"
    )
    user_workspace_1_2 = data_fixture.create_user_workspace(
        order=1, permissions="ADMIN", workspace=user_workspace_1.workspace
    )
    user_workspace_1_3 = data_fixture.create_user_workspace(
        order=1, permissions="MEMBER", workspace=user_workspace_1.workspace
    )

    user_workspace_2 = data_fixture.create_user_workspace(
        user=user, order=2, permissions="ADMIN"
    )
    user_workspace_2_2 = data_fixture.create_user_workspace(
        order=2, permissions="MEMBER", workspace=user_workspace_2.workspace
    )

    response = api_client.get(
        reverse("api:workspaces:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    expected_result = [
        {
            "id": user_workspace_1.workspace.id,
            "name": user_workspace_1.workspace.name,
            "order": 1,
            "permissions": "MEMBER",
            "users": [
                {
                    "email": user_workspace_1.user.email,
                    "workspace": user_workspace_1.workspace.id,
                    "id": user_workspace_1.id,
                    "name": user_workspace_1.user.first_name,
                    "permissions": "MEMBER",
                    "to_be_deleted": False,
                    "user_id": user_workspace_1.user.id,
                },
                {
                    "email": user_workspace_1_2.user.email,
                    "workspace": user_workspace_1_2.workspace.id,
                    "id": user_workspace_1_2.id,
                    "name": user_workspace_1_2.user.first_name,
                    "permissions": "ADMIN",
                    "to_be_deleted": False,
                    "user_id": user_workspace_1_2.user.id,
                },
                {
                    "email": user_workspace_1_3.user.email,
                    "workspace": user_workspace_1_3.workspace.id,
                    "id": user_workspace_1_3.id,
                    "name": user_workspace_1_3.user.first_name,
                    "permissions": "MEMBER",
                    "to_be_deleted": False,
                    "user_id": user_workspace_1_3.user.id,
                },
            ],
        },
        {
            "id": user_workspace_2.workspace.id,
            "name": user_workspace_2.workspace.name,
            "order": 2,
            "permissions": "ADMIN",
            "users": [
                {
                    "email": user_workspace_2.user.email,
                    "workspace": user_workspace_2.workspace.id,
                    "id": user_workspace_2.id,
                    "name": user_workspace_2.user.first_name,
                    "permissions": "ADMIN",
                    "to_be_deleted": False,
                    "user_id": user_workspace_2.user.id,
                },
                {
                    "email": user_workspace_2_2.user.email,
                    "workspace": user_workspace_2_2.workspace.id,
                    "id": user_workspace_2_2.id,
                    "name": user_workspace_2_2.user.first_name,
                    "permissions": "MEMBER",
                    "to_be_deleted": False,
                    "user_id": user_workspace_2_2.user.id,
                },
            ],
        },
    ]

    assert is_dict_subset(expected_result, response_json)


@pytest.mark.django_db
def test_create_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    json_response = response.json()
    workspace_user = WorkspaceUser.objects.filter(user=user.id).first()
    assert workspace_user.order == 1
    assert workspace_user.order == json_response["order"]
    assert workspace_user.workspace.id == json_response["id"]
    assert workspace_user.workspace.name == "Test 1"
    assert workspace_user.user == user

    response = api_client.post(
        reverse("api:workspaces:list"),
        {"not_a_name": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_workspace_name_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, name="Old name")

    invalid_names = [
        "SOMETHING! Your account has been blocked: something-helps.com",
        "Verify again: x.gd/bot",
        "www.evil.com",
        "https://evil.com",
        "bad\nname",
    ]
    for invalid_name in invalid_names:
        response = api_client.post(
            reverse("api:workspaces:list"),
            {"name": invalid_name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST, invalid_name
        assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert response_json["detail"]["name"][0]["code"] == "invalid_name"

        url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
        response = api_client.patch(
            url,
            {"name": invalid_name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST, invalid_name
        assert response_json["detail"]["name"][0]["code"] == "invalid_name"

    workspace.refresh_from_db()
    assert workspace.name == "Old name"

    # Dotted names without a high risk TLD or path must still be allowed.
    valid_names = ["Dept. Marketing", "rocket.ia", "team.exenra"]
    for valid_name in valid_names:
        url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
        response = api_client.patch(
            url,
            {"name": valid_name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK, valid_name
        workspace.refresh_from_db()
        assert workspace.name == valid_name


@pytest.mark.django_db
def test_update_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, name="Old name")
    data_fixture.create_user_workspace(
        user=user_2, workspace=workspace, permissions="MEMBER"
    )
    workspace_2 = data_fixture.create_workspace()

    url = reverse("api:workspaces:item", kwargs={"workspace_id": 99999})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace_2.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token_2}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    json_response = response.json()

    workspace.refresh_from_db()

    assert workspace.name == "New name"
    assert json_response["id"] == workspace.id
    assert json_response["name"] == "New name"


@pytest.mark.django_db
def test_leave_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(name="Old name")
    data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        user=user_2, workspace=workspace, permissions="ADMIN"
    )
    workspace_2 = data_fixture.create_workspace()

    url = reverse("api:workspaces:leave", kwargs={"workspace_id": 99999})
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:workspaces:leave", kwargs={"workspace_id": workspace_2.id})
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:workspaces:leave", kwargs={"workspace_id": workspace.id})
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token_2}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GROUP_USER_IS_LAST_ADMIN"

    url = reverse("api:workspaces:leave", kwargs={"workspace_id": workspace.id})
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 204
    assert WorkspaceUser.objects.all().count() == 1
    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()
    assert WorkspaceUser.objects.filter(user=user_2, workspace=workspace).exists()


@pytest.mark.django_db
def test_delete_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, name="Old name")
    data_fixture.create_user_workspace(
        user=user_2, workspace=workspace, permissions="MEMBER"
    )
    workspace_2 = data_fixture.create_workspace()

    url = reverse("api:workspaces:item", kwargs={"workspace_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace_2.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token_2}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    url = reverse("api:workspaces:item", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 204
    assert Workspace.objects.all().count() == 1


@pytest.mark.django_db
def test_reorder_workspaces(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_user_1 = data_fixture.create_user_workspace(user=user)
    workspace_user_2 = data_fixture.create_user_workspace(user=user)
    workspace_user_3 = data_fixture.create_user_workspace(user=user)

    url = reverse("api:workspaces:order")
    response = api_client.post(
        url,
        {
            "workspaces": [
                workspace_user_2.workspace.id,
                workspace_user_1.workspace.id,
                workspace_user_3.workspace.id,
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204

    workspace_user_1.refresh_from_db()
    workspace_user_2.refresh_from_db()
    workspace_user_3.refresh_from_db()

    assert [1, 2, 3] == [
        workspace_user_2.order,
        workspace_user_1.order,
        workspace_user_3.order,
    ]


@pytest.mark.django_db
def test_trashed_workspace_not_returned_by_views(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    trashed_workspace = data_fixture.create_workspace(user=user)
    visible_workspace = data_fixture.create_workspace(user=user)

    CoreHandler().delete_workspace_by_id(user, trashed_workspace.id)

    response = api_client.get(
        reverse("api:workspaces:list"), **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == visible_workspace.id


@pytest.mark.django_db
def test_only_admin_can_list_generative_ai_settings(api_client, data_fixture):
    data_fixture.register_fake_generate_ai_type()
    user, token = data_fixture.create_user_and_token(email="test@test.nl")
    member_user, member_token = data_fixture.create_user_and_token(
        email="test2@test.nl",
    )

    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member_user, permissions="MEMBER"
    )

    response = api_client.get(
        reverse(
            "api:workspaces:generative_ai_settings",
            kwargs={"workspace_id": workspace.id},
        ),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {}

    response = api_client.get(
        reverse(
            "api:workspaces:generative_ai_settings",
            kwargs={"workspace_id": workspace.id},
        ),
        **{"HTTP_AUTHORIZATION": f"JWT {member_token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_workspace_settings_override_global_generative_ai_settings(
    api_client, data_fixture
):
    data_fixture.register_fake_generate_ai_type()
    user, token = data_fixture.create_user_and_token(email="test@test.nl")
    member_user, member_token = data_fixture.create_user_and_token(
        email="test2@test.nl",
    )

    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member_user, permissions="MEMBER"
    )

    # the default value
    response = api_client.get(
        reverse("api:workspaces:list"), **{"HTTP_AUTHORIZATION": f"JWT {member_token}"}
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[0]["generative_ai_models_enabled"] == {
        "test_generative_ai": ["test_1"],
        "test_generative_ai_prompt_error": ["test_1"],
        "test_generative_ai_with_files": ["test_1"],
    }

    response = api_client.patch(
        reverse(
            "api:workspaces:generative_ai_settings",
            kwargs={"workspace_id": workspace.id},
        ),
        {"test_generative_ai": {"models": ["cannot_change_it"]}},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {member_token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.patch(
        reverse(
            "api:workspaces:generative_ai_settings",
            kwargs={"workspace_id": workspace.id},
        ),
        {"test_generative_ai": {"models": ["wp_model_setting"]}},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "id": workspace.id,
        "name": workspace.name,
        "generative_ai_models_enabled": {
            "test_generative_ai": ["wp_model_setting"],  # it was "test_1"
            "test_generative_ai_prompt_error": ["test_1"],
            "test_generative_ai_with_files": ["test_1"],
        },
    }

    response = api_client.get(
        reverse("api:workspaces:list"), **{"HTTP_AUTHORIZATION": f"JWT {member_token}"}
    )

    # The global settings is overridden by the workspace settings
    assert response.status_code == HTTP_200_OK
    settings = response.json()[0]["generative_ai_models_enabled"]
    assert settings["test_generative_ai"] == ["wp_model_setting"]  # it was "test_1"


@pytest.mark.django_db
def test_create_initial_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(first_name="Test1")

    response = api_client.post(
        reverse("api:workspaces:create_initial_workspace"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    json_response = response.json()
    workspace_user = WorkspaceUser.objects.filter(user=user.id).first()
    assert workspace_user.order == 1
    assert workspace_user.order == json_response["order"]
    assert workspace_user.workspace.id == json_response["id"]
    assert workspace_user.workspace.name == "Test1's workspace"
    assert workspace_user.user == user


@pytest.mark.django_db
def test_list_workspaces_two_factor_auth_no_n_plus_one(api_client, data_fixture):
    def build_workspace_and_get_token(member_count):
        owner, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=owner)
        for _ in range(member_count - 1):
            member = data_fixture.create_user()
            data_fixture.create_user_workspace(
                workspace=workspace, user=member, permissions="MEMBER"
            )
            # exercise the prefetched reverse relation with real providers
            data_fixture.configure_base_totp(member)
        return token

    token_few = build_workspace_and_get_token(member_count=2)
    token_many = build_workspace_and_get_token(member_count=6)

    url = reverse("api:workspaces:list")

    api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token_few}"})
    api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token_many}"})

    with CaptureQueriesContext(connection) as few_queries:
        response_few = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token_few}"})
    with CaptureQueriesContext(connection) as many_queries:
        response_many = api_client.get(
            url, **{"HTTP_AUTHORIZATION": f"JWT {token_many}"}
        )

    assert response_few.status_code == HTTP_200_OK
    assert response_many.status_code == HTTP_200_OK
    assert len(response_few.json()[0]["users"]) == 2
    assert len(response_many.json()[0]["users"]) == 6

    assert len(many_queries.captured_queries) == len(few_queries.captured_queries), (
        f"N+1 on two_factor_auth: {len(few_queries.captured_queries)} queries for "
        f"2 members vs {len(many_queries.captured_queries)} for 6 members"
    )
