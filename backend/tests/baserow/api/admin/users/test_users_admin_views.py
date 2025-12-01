import json
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    WORKSPACE_USER_PERMISSION_MEMBER,
)

User = get_user_model()
invalid_passwords = [
    "a",
    "ab",
    "ask",
    "oiue",
    "dsj43",
    "984kds",
    "dsfkjh4",
]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admin_cannot_see_admin_users_endpoint(api_client, data_fixture):
    non_staff_user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=False,
    )
    response = api_client.get(
        reverse("api:admin:users:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_see_admin_users_endpoint(api_client, data_fixture):
    staff_user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    workspace_user_is_admin_of = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_user_is_admin_of,
        user=staff_user,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    workspace_user_is_not_admin_of = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_user_is_not_admin_of,
        user=staff_user,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )
    response = api_client.get(
        reverse("api:admin:users:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "date_joined": "2021-04-01T01:00:00Z",
                "name": staff_user.first_name,
                "username": staff_user.email,
                "workspaces": unordered(
                    [
                        {
                            "id": workspace_user_is_admin_of.id,
                            "name": workspace_user_is_admin_of.name,
                            "permissions": WORKSPACE_USER_PERMISSION_ADMIN,
                        },
                        {
                            "id": workspace_user_is_not_admin_of.id,
                            "name": workspace_user_is_not_admin_of.name,
                            "permissions": WORKSPACE_USER_PERMISSION_MEMBER,
                        },
                    ]
                ),
                "id": staff_user.id,
                "is_staff": True,
                "is_active": True,
                "last_login": None,
            }
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_with_invalid_token_cannot_see_admin_users(api_client, data_fixture):
    data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    response = api_client.get(
        reverse("api:admin:users:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_INVALID_ACCESS_TOKEN"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_accessing_invalid_user_admin_page_returns_empty_list(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1
    assert response.json()["results"] == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_accessing_user_admin_with_invalid_page_size_returns_error(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&size=201",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_SIZE_LIMIT"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_search_users(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    searched_for_user = data_fixture.create_user(
        email="specific_user@test.nl",
        password="password",
        first_name="Test1",
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&search=specific_user",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "date_joined": "2021-04-01T01:00:00Z",
                "name": searched_for_user.first_name,
                "username": searched_for_user.email,
                "workspaces": [],
                "id": searched_for_user.id,
                "is_staff": False,
                "is_active": True,
                "last_login": None,
            }
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_sort_users(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    searched_for_user = data_fixture.create_user(
        email="specific_user@test.nl",
        password="password",
        first_name="Test1",
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&search=specific_user",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "date_joined": "2021-04-01T01:00:00Z",
                "name": searched_for_user.first_name,
                "username": searched_for_user.email,
                "workspaces": [],
                "id": searched_for_user.id,
                "is_staff": False,
                "is_active": True,
                "last_login": None,
            }
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_invalid_sort_field_provided(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=-invalid_field_name",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_ATTRIBUTE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_sort_direction_not_provided(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=username",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_DIRECTION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_invalid_sort_direction_provided(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=*username",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_DIRECTION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_invalid_sorts_mixed_with_valid_ones(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=+username,username,-invalid_field",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_DIRECTION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_blank_sorts_provided(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=,,",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_ATTRIBUTE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_returns_error_response_if_no_sorts_provided(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    url = reverse("api:admin:users:list")
    response = api_client.get(
        f"{url}?page=1&sorts=",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_SORT_ATTRIBUTE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admin_cannot_delete_user(api_client, data_fixture):
    _, non_admin_token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=False,
    )
    user_to_delete = data_fixture.create_user(
        email="specific_user@test.nl",
        password="password",
        first_name="Test1",
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user_to_delete.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {non_admin_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_delete_user(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    user_to_delete = data_fixture.create_user(
        email="specific_user@test.nl",
        password="password",
        first_name="Test1",
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user_to_delete.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:admin:users:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admin_cannot_patch_user(api_client, data_fixture):
    non_admin_user, non_admin_user_token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=False,
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": non_admin_user.id})
    response = api_client.patch(
        url,
        {"username": "some_other_email@test.nl"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {non_admin_user_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    non_admin_user.refresh_from_db()
    assert non_admin_user.email == "test@test.nl"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_create_user_without_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:list")
    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    user.refresh_from_db()
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["name"][0]["code"] == "required"
    assert response_json["detail"]["password"][0]["code"] == "required"
    assert response_json["detail"]["username"][0]["code"] == "required"
    assert User.objects.all().count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_create_user_that_already_exists(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    data_fixture.create_user(email="test2@test.nl")
    url = reverse("api:admin:users:list")
    response = api_client.post(
        url,
        {"username": "test2@test.nl", "password": "Test1234", "name": "Test1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    user.refresh_from_db()
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "USER_ADMIN_ALREADY_EXISTS"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_create_user(api_client, data_fixture):
    user = data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:list")
    with freeze_time("2020-01-02 12:00"):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            url,
            {
                "username": "test2@test.nl",
                "password": "Test1234",
                "name": "Test1",
                "is_staff": True,
                "is_active": True,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        user = User.objects.all().last()
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "date_joined": "2020-01-02T12:00:00Z",
            "name": "Test1",
            "username": "test2@test.nl",
            "workspaces": [],
            "id": user.id,
            "is_staff": True,
            "is_active": True,
            "last_login": None,
        }

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@test.nl", "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert "access_token" in response.json()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_patch_user(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user.id})
    old_password = user.password
    response = api_client.patch(
        url,
        {"username": "some_other_email@test.nl", "password": "new_password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    user.refresh_from_db()
    assert user.password != old_password
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "date_joined": "2021-04-01T01:00:00Z",
        "name": user.first_name,
        "username": "some_other_email@test.nl",
        "workspaces": [],
        "id": user.id,
        "is_staff": True,
        "is_active": True,
        "last_login": None,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_patch_user_without_providing_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user.id})
    old_password = user.password
    response = api_client.patch(
        url,
        {"username": "some_other_email@test.nl", "name": "Test2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    user.refresh_from_db()
    assert user.password == old_password
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "date_joined": "2021-04-01T01:00:00Z",
        "name": "Test2",
        "username": "some_other_email@test.nl",
        "workspaces": [],
        "id": user.id,
        "is_staff": True,
        "is_active": True,
        "last_login": None,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_update_to_existing_user(api_client, data_fixture):
    user_to_change = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user_to_change.id})
    response = api_client.patch(
        url,
        {"username": "test@test.nl"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "USER_ADMIN_ALREADY_EXISTS"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("invalid_password", invalid_passwords)
def test_invalid_password_returns_400(api_client, data_fixture, invalid_password):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    user_to_edit = data_fixture.create_user(
        email="second@test.nl",
        password="password",
        first_name="Test1",
        is_staff=False,
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user_to_edit.id})

    response = api_client.patch(
        url,
        {"username": user_to_edit.email, "password": invalid_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response.json()["detail"]["password"][0]["code"] == "password_validation_failed"
    )

    # just sending the password will throw the same error
    response = api_client.patch(
        url,
        {"password": invalid_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response.json()["detail"]["password"][0]["code"] == "password_validation_failed"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_error_returned_when_invalid_field_supplied_to_edit(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user.id})

    # We have to provide a str as otherwise the test api client will "helpfully" try
    # to serialize the dict using the endpoints serializer, which will fail before
    # actually running the endpoint.
    response = api_client.patch(
        url,
        json.dumps({"date_joined": "2021-04-01T01:00:00Z"}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_error_returned_when_updating_user_with_invalid_email(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user.id})

    # We have to provide a str as otherwise the test api client will "helpfully" try
    # to serialize the dict using the endpoints serializer, which will fail before
    # actually running the endpoint.
    response = api_client.patch(
        url,
        json.dumps({"username": "invalid email address"}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_error_returned_when_valid_and_invalid_fields_supplied_to_edit(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    url = reverse("api:admin:users:edit", kwargs={"user_id": user.id})

    # We have to provide a str as otherwise the test api client will "helpfully" try
    # to serialize the dict using the endpoints serializer, which will fail before
    # actually running the endpoint.
    response = api_client.patch(
        url,
        json.dumps({"is_active": False, "date_joined": "2021-04-01T01:00:00Z"}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_getting_view_users_only_runs_two_queries_instead_of_n(
    data_fixture, django_assert_num_queries, api_client
):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    fixed_num_of_queries_unrelated_to_number_of_rows = 6

    for i in range(10):
        data_fixture.create_user_workspace()

    with django_assert_num_queries(fixed_num_of_queries_unrelated_to_number_of_rows):
        response = api_client.get(
            reverse("api:admin:users:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 11

    # Make even more to ensure that more rows don't result in more queries.
    for i in range(10):
        data_fixture.create_user_workspace()

    with django_assert_num_queries(fixed_num_of_queries_unrelated_to_number_of_rows):
        response = api_client.get(
            reverse("api:admin:users:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 21


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_impersonate_not_existing_user(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["user"][0].startswith("Invalid pk")


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_impersonate_user_as_normal_user(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=False,
        is_superuser=False,
    )
    user_to_impersonate = data_fixture.create_user(
        email="specific_user@test.nl", password="password", first_name="Test1"
    )
    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": user_to_impersonate.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_impersonate_user(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    user_to_impersonate = data_fixture.create_user(
        email="specific_user@test.nl", password="password", first_name="Test1"
    )
    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": user_to_impersonate.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "access_token" in response_json
    assert "refresh_token" in response_json
    assert "password" not in response_json["user"]
    assert response_json["user"]["username"] == "specific_user@test.nl"
    assert response_json["user"]["first_name"] == "Test1"
    assert response_json["user"]["is_staff"] is False
    assert response_json["user"]["id"] == user_to_impersonate.id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_impersonate_staff_or_superuser(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    user_to_impersonate_superuser = data_fixture.create_user(
        email="specific_user@test.nl",
        password="password",
        first_name="Test1",
        is_superuser=True,
    )
    user_to_impersonate_staff = data_fixture.create_user(
        email="specific_user2@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
    )
    user_to_impersonate_superuser_staff = data_fixture.create_user(
        email="specific_user3@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        is_superuser=True,
    )
    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": user_to_impersonate_superuser.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["user"][0].startswith("Invalid pk")

    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": user_to_impersonate_staff.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["user"][0].startswith("Invalid pk")

    response = api_client.post(
        reverse("api:admin:users:impersonate"),
        {"user": user_to_impersonate_superuser_staff.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["user"][0].startswith("Invalid pk")
