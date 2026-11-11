import pytest
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.core.handler import CoreHandler


def update_application_url(dashboard):
    return reverse("api:applications:item", kwargs={"application_id": dashboard.id})


def sharing_url(dashboard_id):
    return reverse("api:dashboard:sharing", kwargs={"dashboard_id": dashboard_id})


def rotate_slug_url(dashboard_id):
    return reverse("api:dashboard:rotate_slug", kwargs={"dashboard_id": dashboard_id})


@pytest.mark.django_db
def test_update_dashboard_sharing_state(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["public"] is True
    assert response_json["slug"] == dashboard.slug
    assert response_json["public_has_password"] is False
    assert response_json["show_logo"] is True
    assert "public_password" not in response_json
    dashboard.refresh_from_db()
    assert dashboard.public is True


@pytest.mark.django_db
def test_update_dashboard_public_password_is_stored_hashed(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public": True, "public_password": "secret-password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["public_has_password"] is True
    assert "secret-password" not in response.content.decode()
    dashboard.refresh_from_db()
    assert dashboard.public_password != "secret-password"
    assert dashboard.check_public_password("secret-password")
    assert not dashboard.check_public_password("wrong-password")


@pytest.mark.django_db
def test_update_dashboard_public_password_too_short(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public_password": "short"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["public_password"][0]["code"] == "min_length"
    dashboard.refresh_from_db()
    assert dashboard.public_password == ""


@pytest.mark.django_db
def test_update_dashboard_blank_password_removes_the_protection(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    dashboard.set_password("secret-password")
    dashboard.save()

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public_password": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["public_has_password"] is False
    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.public_password == ""


@pytest.mark.django_db
def test_update_dashboard_public_flag_clears_the_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    dashboard.set_password("secret-password")
    dashboard.save()

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    dashboard.refresh_from_db()
    assert dashboard.public is False
    assert dashboard.public_password == ""


@pytest.mark.django_db
def test_update_dashboard_sharing_ignores_premium_and_read_only_fields(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    original_slug = dashboard.slug

    response = api_client.patch(
        sharing_url(dashboard.id),
        {
            "public": True,
            "show_logo": False,
            "slug": "custom-slug",
            "public_has_password": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.show_logo is True
    assert dashboard.slug == original_slug
    assert dashboard.public_password == ""


@pytest.mark.django_db
def test_update_dashboard_sharing_requires_a_sharing_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    # Only the premium endpoint changes `show_logo`, so nothing is left to update.
    response = api_client.patch(
        sharing_url(dashboard.id),
        {"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "non_field_errors" in response_json["detail"]
    dashboard.refresh_from_db()
    assert dashboard.show_logo is True


@pytest.mark.django_db
def test_update_dashboard_sharing_user_not_in_workspace(api_client, data_fixture):
    user = data_fixture.create_user()
    _, other_token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        sharing_url(dashboard.id),
        {"public": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    dashboard.refresh_from_db()
    assert dashboard.public is False


@pytest.mark.django_db
def test_update_dashboard_sharing_dashboard_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.patch(
        sharing_url(0),
        {"public": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_application_ignores_the_sharing_fields(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    original_slug = dashboard.slug

    # The generic endpoint only changes the name and the description, sharing has
    # its own endpoint and action so the audit log can describe the change.
    response = api_client.patch(
        update_application_url(dashboard),
        {
            "description": "Updated description",
            "public": True,
            "public_password": "secret-password",
            "show_logo": False,
            "slug": "custom-slug",
            "public_has_password": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["description"] == "Updated description"
    assert response_json["public"] is False
    dashboard.refresh_from_db()
    assert dashboard.description == "Updated description"
    assert dashboard.public is False
    assert dashboard.public_password == ""
    assert dashboard.show_logo is True
    assert dashboard.slug == original_slug


@pytest.mark.django_db
def test_rotate_dashboard_slug(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    original_slug = dashboard.slug

    response = api_client.post(
        rotate_slug_url(dashboard.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == dashboard.id
    assert response_json["type"] == "dashboard"
    assert response_json["public"] is True
    assert response_json["slug"] != original_slug
    dashboard.refresh_from_db()
    assert dashboard.slug == response_json["slug"]


@pytest.mark.django_db
def test_rotate_dashboard_slug_user_not_in_workspace(api_client, data_fixture):
    user = data_fixture.create_user()
    _, other_token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    original_slug = dashboard.slug

    response = api_client.post(
        rotate_slug_url(dashboard.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    dashboard.refresh_from_db()
    assert dashboard.slug == original_slug


@pytest.mark.django_db
def test_rotate_dashboard_slug_dashboard_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.post(
        rotate_slug_url(0),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_rotate_dashboard_slug_trashed_dashboard(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    CoreHandler().delete_application(user, dashboard)

    response = api_client.post(
        rotate_slug_url(dashboard.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"
