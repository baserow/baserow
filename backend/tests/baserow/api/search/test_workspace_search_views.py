"""
Generic API tests for workspace search functionality.

Tests workspace access, parameter validation, feature flags, and general API behavior.
"""

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_requires_authentication(api_client, data_fixture):
    workspace = data_fixture.create_workspace()

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id})
    response = api_client.get(url, {"query": "test"})

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_requires_workspace_membership(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()  # User is not a member

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id})
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_workspace_not_found(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    url = reverse("api:search:workspace_search", kwargs={"workspace_id": 99999})
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_missing_query_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_empty_query_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": ""}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_basic_success(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": "Test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert "results" in response_json
    assert "has_more" in response_json

    results = response_json["results"]
    assert len(results) == 1
    assert results[0]["id"] == database.id
    assert results[0]["title"] == "Test Database"


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_with_limit_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    for i in range(5):
        data_fixture.create_database_application(
            workspace=user_workspace.workspace, name=f"Database {i}"
        )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Database", "limit": 3}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json["results"]) <= 3


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_with_offset_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    databases = []
    for i in range(5):
        databases.append(
            data_fixture.create_database_application(
                workspace=user_workspace.workspace, name=f"Search DB {i:02d}"
            )
        )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response1 = api_client.get(
        url,
        {"query": "Search DB", "limit": 2, "offset": 0},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response2 = api_client.get(
        url,
        {"query": "Search DB", "limit": 2, "offset": 2},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response1.status_code == HTTP_200_OK
    assert response2.status_code == HTTP_200_OK

    results1 = response1.json()["results"]
    results2 = response2.json()["results"]

    assert len(results1) == 2
    assert len(results2) == 2

    assert results1[0]["id"] == databases[0].id
    assert results1[1]["id"] == databases[1].id
    assert results2[0]["id"] == databases[2].id
    assert results2[1]["id"] == databases[3].id


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_invalid_limit_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "test", "limit": -1}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    response = api_client.get(
        url, {"query": "test", "limit": 1000}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_invalid_offset_parameter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "test", "offset": -1}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_case_insensitive(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="CamelCase Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    for query in ["camelcase", "CAMELCASE", "CamelCase", "camelCASE"]:
        response = api_client.get(
            url, {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}"
        )

        assert response.status_code == HTTP_200_OK
        response_json = response.json()

        database_results = response_json["results"]
        assert len(database_results) == 1
        assert database_results[0]["id"] == database.id
        assert database_results[0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_partial_match(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Very Long Database Name"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    for query in ["Very", "Long", "Database", "Name", "Very Long", "Database Name"]:
        response = api_client.get(
            url, {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}"
        )

        assert response.status_code == HTTP_200_OK
        response_json = response.json()

        database_results = response_json["results"]
        assert len(database_results) == 1
        assert database_results[0]["id"] == database.id
        assert database_results[0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_no_results(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )

    response = api_client.get(
        url, {"query": "nonexistent search term"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json["results"]) == 0
    assert response_json["has_more"] is False


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_admin_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user, permissions="ADMIN")

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Admin Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Admin Test"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == database.id
    assert response_json["results"][0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_member_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user, permissions="MEMBER")

    database = data_fixture.create_database_application(
        workspace=user_workspace.workspace, name="Member Test Database"
    )

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(
        url, {"query": "Member Test"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == database.id
    assert response_json["results"][0]["title"] == database.name


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_workspace_search_trashed_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_workspace = data_fixture.create_user_workspace(user=user)

    from baserow.core.trash.handler import TrashHandler

    TrashHandler.trash(user, user_workspace.workspace, None, user_workspace.workspace)

    url = reverse(
        "api:search:workspace_search",
        kwargs={"workspace_id": user_workspace.workspace.id},
    )
    response = api_client.get(url, {"query": "test"}, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND
