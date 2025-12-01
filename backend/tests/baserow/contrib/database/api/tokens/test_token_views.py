from unittest.mock import call, patch

from django.shortcuts import reverse

import pytest
from pytest_unordered import unordered
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.rows.operations import DeleteDatabaseRowOperationType
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.contrib.database.tokens.models import Token, TokenPermission
from baserow.contrib.database.tokens.operations import (
    ReadTokenOperationType,
    UpdateTokenOperationType,
)
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_list_tokens(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    token_1 = data_fixture.create_token(user=user, workspace=workspace_1)
    token_2 = data_fixture.create_token(user=user, workspace=workspace_1)
    token_3 = data_fixture.create_token(user=user, workspace=workspace_2)

    url = reverse("api:database:tokens:list")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:tokens:list")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3

    assert len(response_json[0]) == 5
    assert response_json[0]["id"] == token_1.id
    assert response_json[0]["name"] == token_1.name
    assert response_json[0]["key"] == token_1.key
    assert response_json[0]["workspace"] == token_1.workspace_id
    assert response_json[0]["permissions"] == {
        "create": False,
        "read": False,
        "update": False,
        "delete": False,
    }

    assert len(response_json[1]) == 5
    assert response_json[1]["id"] == token_2.id
    assert response_json[1]["name"] == token_2.name
    assert response_json[1]["key"] == token_2.key
    assert response_json[1]["workspace"] == token_2.workspace_id
    assert response_json[0]["permissions"] == {
        "create": False,
        "read": False,
        "update": False,
        "delete": False,
    }

    assert len(response_json[2]) == 5
    assert response_json[2]["id"] == token_3.id
    assert response_json[2]["name"] == token_3.name
    assert response_json[2]["key"] == token_3.key
    assert response_json[2]["workspace"] == token_3.workspace_id
    assert response_json[0]["permissions"] == {
        "create": False,
        "read": False,
        "update": False,
        "delete": False,
    }


@pytest.mark.django_db
def test_create_token(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    url = reverse("api:database:tokens:list")
    response = api_client.post(
        url,
        {"name": "Test 1", "workspace": workspace_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT random",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:tokens:list")
    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"]["name"][0]["code"] == "required"
    assert response_json["detail"]["workspace"][0]["code"] == "required"

    url = reverse("api:database:tokens:list")
    response = api_client.post(
        url,
        {"name": "Test", "workspace": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"]["workspace"][0]["code"] == "does_not_exist"

    url = reverse("api:database:tokens:list")
    response = api_client.post(
        url,
        {
            "name": "Test",
            "workspace": workspace_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    print(response_json)
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tokens:list")
    response = api_client.post(
        url,
        {"name": "Test", "workspace": workspace_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert Token.objects.all().count() == 1
    token = Token.objects.all().first()
    assert response_json["id"] == token.id
    assert response_json["name"] == token.name
    assert response_json["workspace"] == token.workspace_id == workspace_1.id
    assert response_json["key"] == token.key
    assert len(response_json["key"]) == 32
    assert response_json["permissions"] == {
        "create": True,
        "read": True,
        "update": True,
        "delete": True,
    }


@pytest.mark.django_db
def test_get_token(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    token_1 = data_fixture.create_token(user=user, workspace=workspace_1)
    token_2 = data_fixture.create_token(user=user, workspace=workspace_2)
    token_3 = data_fixture.create_token()

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_table(database=database_1, create_table=False)
    data_fixture.create_database_table(database=database_1, create_table=False)
    table_3 = data_fixture.create_database_table(
        database=database_2, create_table=False
    )

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:tokens:item", kwargs={"token_id": 99999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_3.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_2.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == token_1.id
    assert response_json["name"] == token_1.name
    assert response_json["workspace"] == token_1.workspace_id
    assert response_json["key"] == token_1.key
    assert len(response_json["key"]) == 32
    assert response_json["permissions"] == {
        "create": False,
        "read": False,
        "update": False,
        "delete": False,
    }

    TokenHandler().update_token_permissions(
        user,
        token_1,
        create=True,
        read=[database_2],
        update=[database_1, table_3],
        delete=False,
    )

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["permissions"]["create"] is True
    assert len(response_json["permissions"]["read"]) == 1
    assert response_json["permissions"]["read"][0] == ["database", database_2.id]
    assert len(response_json["permissions"]["update"]) == 2
    assert response_json["permissions"]["update"] == unordered(
        [["table", table_3.id], ["database", database_1.id]]
    )
    assert response_json["permissions"]["delete"] is False

    TokenHandler().update_token_permissions(
        user,
        token_1,
        create=[database_1, database_2],
        read=False,
        update=True,
        delete=[table_3],
    )

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["permissions"]["create"]) == 2
    assert response_json["permissions"]["create"] == unordered(
        [["database", database_1.id], ["database", database_2.id]]
    )
    assert response_json["permissions"]["read"] is False
    assert response_json["permissions"]["update"] is True
    assert len(response_json["permissions"]["delete"]) == 1
    assert response_json["permissions"]["delete"][0] == ["table", table_3.id]


@pytest.mark.django_db
def test_update_token(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    workspace_3 = data_fixture.create_workspace(user=user)
    token_1 = data_fixture.create_token(user=user, workspace=workspace_1)
    token_2 = data_fixture.create_token(user=user, workspace=workspace_2)
    token_3 = data_fixture.create_token()

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    database_3 = data_fixture.create_database_application(workspace=workspace_3)
    table_1 = data_fixture.create_database_table(
        database=database_1, create_table=False
    )
    data_fixture.create_database_table(database=database_1, create_table=False)
    table_3 = data_fixture.create_database_table(
        database=database_2, create_table=False
    )
    table_4 = data_fixture.create_database_table(
        database=database_3, create_table=False
    )

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT random"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:tokens:item", kwargs={"token_id": 99999})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_3.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_2.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_2.id})
    response = api_client.patch(
        url, {"name": ""}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"]["name"][0]["code"] == "blank"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_3.id})
    response = api_client.patch(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    token_1.refresh_from_db()
    assert response_json["id"] == token_1.id
    assert response_json["name"] == "New name" == token_1.name
    assert response_json["workspace"] == token_1.workspace_id
    assert response_json["key"] == token_1.key
    assert len(response_json["key"]) == 32
    assert response_json["permissions"] == {
        "create": False,
        "read": False,
        "update": False,
        "delete": False,
    }

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {
            "permissions": {
                "create": "something",
                "read": False,
                "update": False,
                "delete": False,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {
            "permissions": {
                "create": True,
                "read": [["something", 1]],
                "update": False,
                "delete": False,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {
            "permissions": {
                "create": True,
                "read": [1],
                "update": False,
                "delete": False,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {"permissions": {"create": True, "update": False, "delete": False}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url, {"permissions": {}}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {
            "permissions": {
                "create": True,
                "read": [["database", database_3.id]],
                "update": True,
                "delete": True,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DATABASE_DOES_NOT_BELONG_TO_GROUP"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url,
        {
            "permissions": {
                "create": True,
                "read": [["table", table_4.id]],
                "update": True,
                "delete": True,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    with patch(
        "baserow.core.handler.CoreHandler.check_permissions"
    ) as mock_check_permissions:
        response = api_client.patch(
            url,
            {
                "name": "New name 2",
                "permissions": {
                    "create": True,
                    "read": [["database", database_1.id]],
                    "update": False,
                    "delete": [["table", table_1.id], ["table", table_3.id]],
                },
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        expected_calls = [
            call(
                user,
                ReadTokenOperationType.type,
                workspace=token_1.workspace,
                context=token_1,
            ),
            call(
                user,
                UpdateTokenOperationType.type,
                workspace=token_1.workspace,
                context=token_1,
            ),
            call(
                user,
                DeleteDatabaseRowOperationType.type,
                workspace=token_1.workspace,
                context=table_1,
            ),
            call(
                user,
                DeleteDatabaseRowOperationType.type,
                workspace=token_1.workspace,
                context=table_3,
            ),
        ]
        assert mock_check_permissions.mock_calls == expected_calls

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    token_1.refresh_from_db()
    assert response_json["id"] == token_1.id
    assert response_json["name"] == "New name 2" == token_1.name
    assert response_json["workspace"] == token_1.workspace_id
    assert response_json["key"] == token_1.key
    assert len(response_json["key"]) == 32
    assert response_json["permissions"]["create"] is True
    assert len(response_json["permissions"]["read"]) == 1
    assert response_json["permissions"]["read"][0] == ["database", database_1.id]
    assert response_json["permissions"]["update"] is False
    assert len(response_json["permissions"]["delete"]) == 2
    assert response_json["permissions"]["delete"] == unordered(
        ["table", table_1.id], ["table", table_3.id]
    )

    assert TokenPermission.objects.all().count() == 4
    assert TokenPermission.objects.filter(
        token=token_1, type="create", database__isnull=True, table__isnull=True
    ).exists()
    assert TokenPermission.objects.filter(
        token=token_1, type="read", database_id=database_1.id, table__isnull=True
    ).exists()
    assert TokenPermission.objects.filter(
        token=token_1, type="delete", database__isnull=True, table_id=table_1.id
    ).exists()
    assert TokenPermission.objects.filter(
        token=token_1, type="delete", database__isnull=True, table_id=table_1.id
    ).exists()

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.patch(
        url, {"rotate_key": True}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["key"] != token_1.key
    token_1.refresh_from_db()
    assert response_json["key"] == token_1.key


@pytest.mark.django_db
def test_delete_token(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    token_1 = data_fixture.create_token(user=user, workspace=workspace_1)
    token_2 = data_fixture.create_token(user=user, workspace=workspace_2)
    token_3 = data_fixture.create_token()

    TokenHandler().update_token_permissions(
        user, token_1, create=True, read=True, update=True, delete=True
    )

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:database:tokens:item", kwargs={"token_id": 99999})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_3.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_2.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_3.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    assert Token.objects.all().count() == 3
    assert TokenPermission.objects.all().count() == 4

    url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    assert Token.objects.all().count() == 2
    assert TokenPermission.objects.all().count() == 0


@pytest.mark.django_db
def test_trashing_table_hides_restores_tokens(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    token_1 = data_fixture.create_token(user=user, workspace=workspace_1)

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    table_1 = data_fixture.create_database_table(database=database_1)
    table_2 = data_fixture.create_database_table(database=database_1)

    TokenHandler().update_token_permissions(
        user,
        token_1,
        create=[database_1, table_1, table_2, database_2],
        read=[database_1, table_1, table_2, database_2],
        update=[database_1, table_1, table_2, database_2],
        delete=[database_1, table_1, table_2, database_2],
    )

    def assert_all_permission_types_for_token_are(value):
        url = reverse("api:database:tokens:item", kwargs={"token_id": token_1.id})
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        # permissions must be the same, ignoring order
        permissions = response_json["permissions"]
        unordered_value = unordered(value)
        assert permissions["update"] == unordered_value
        assert permissions["create"] == unordered_value
        assert permissions["delete"] == unordered_value
        assert permissions["read"] == unordered_value

    assert_all_permission_types_for_token_are(
        [
            ["table", table_1.id],
            ["table", table_2.id],
            ["database", database_2.id],
            ["database", database_1.id],
        ]
    )

    TrashHandler.trash(user, workspace_1, database_1, table_1)

    assert_all_permission_types_for_token_are(
        [
            ["table", table_2.id],
            ["database", database_2.id],
            ["database", database_1.id],
        ]
    )

    TrashHandler.trash(user, workspace_1, database_1, database_1)

    assert_all_permission_types_for_token_are(
        [
            ["table", table_2.id],
            ["database", database_2.id],
        ]
    )

    TrashHandler.restore_item(user, "application", database_1.id)

    assert_all_permission_types_for_token_are(
        [
            ["table", table_2.id],
            ["database", database_2.id],
            ["database", database_1.id],
        ]
    )

    TrashHandler.restore_item(user, "table", table_1.id)

    assert_all_permission_types_for_token_are(
        [
            ["table", table_2.id],
            ["table", table_1.id],
            ["database", database_2.id],
            ["database", database_1.id],
        ]
    )


@pytest.mark.django_db
def test_check_token(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    url = reverse("api:database:tokens:check")
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_403_FORBIDDEN

    url = reverse("api:database:tokens:check")
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION="Token WRONG")
    assert response.status_code == HTTP_403_FORBIDDEN

    token = TokenHandler().create_token(user, workspace, "Good")
    url = reverse("api:database:tokens:check")
    response = api_client.get(
        url, format="json", HTTP_AUTHORIZATION=f"Token {token.key}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"token": "OK"}


@pytest.mark.django_db
def test_cannot_get_row_metadata_from_token(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    row = table.get_model().objects.create()

    def get_row_from_api_with_metadata():
        return api_client.get(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            )
            + "?include=metadata",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

    response = get_row_from_api_with_metadata()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_CANNOT_INCLUDE_ROW_METADATA",
        "detail": "The token cannot include row metadata.",
    }
