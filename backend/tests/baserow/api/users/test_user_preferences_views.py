from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)


@pytest.mark.django_db
def test_update_user_preferences(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:user:preferences")

    response = api_client.patch(
        url,
        {"all_workspaces_sort_by": "name_desc"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "all_workspaces_sort_by": "name_desc",
        "all_workspaces_view_mode": "expanded",
    }

    response = api_client.patch(
        url,
        {"all_workspaces_view_mode": "compact"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "all_workspaces_sort_by": "name_desc",
        "all_workspaces_view_mode": "compact",
    }
    user.profile.refresh_from_db()
    assert user.profile.preferences == {
        "all_workspaces_sort_by": "name_desc",
        "all_workspaces_view_mode": "compact",
    }


@pytest.mark.django_db
def test_update_user_preferences_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    url = reverse("api:user:preferences")

    response = api_client.patch(
        url,
        {"all_workspaces_sort_by": "random"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "all_workspaces_sort_by" in response.json()["detail"]

    response = api_client.patch(
        url,
        {"unknown": "value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "unknown" in response.json()["detail"]["non_field_errors"][0]["error"]

    user.profile.refresh_from_db()
    assert user.profile.preferences == {}

    response = api_client.patch(
        url, {"all_workspaces_sort_by": "created"}, format="json"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_token_auth_exposes_user_preferences(api_client, data_fixture):
    user = data_fixture.create_user(email="test@localhost", password="password")
    user.profile.preferences = {"all_workspaces_view_mode": "compact"}
    user.profile.save()

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@localhost", "password": "password"},
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["user"]["preferences"] == {
        "all_workspaces_sort_by": "last_viewed",
        "all_workspaces_view_mode": "compact",
    }
