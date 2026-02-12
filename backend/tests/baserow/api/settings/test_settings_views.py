from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from baserow.api.settings.registries import SettingsDataRegistry, SettingsDataType
from baserow.core.handler import CoreHandler
from baserow.core.models import Settings


@pytest.mark.django_db
def test_get_settings(api_client):
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "instance_id" not in response_json
    assert response_json["allow_new_signups"] is True

    settings = Settings.objects.first()
    settings.allow_new_signups = False
    settings.save()

    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "instance_id" not in response_json
    assert response_json["allow_new_signups"] is False
    assert response_json["email_verification"] == "no_verification"

    # None is not returned as a value for email_verification
    settings.email_verification = None
    settings.save()
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["email_verification"] == "no_verification"


@pytest.mark.django_db
def test_require_first_admin_user_is_false_after_admin_creation(
    api_client, data_fixture
):
    data_fixture.create_password_provider()
    response = api_client.get(reverse("api:settings:get"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_admin_signup_page"] is True

    # create the admin user
    response = api_client.post(
        reverse("api:user:index"),
        {
            "name": "admin",
            "email": "admin@baserow.io",
            "password": "admin1234",
            "language": "en",
            "authenticate": True,
        },
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    token = response_json["access_token"]

    response = api_client.get(
        reverse("api:settings:get"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["show_admin_signup_page"] is False


@pytest.mark.django_db
def test_get_instance_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    user_2, token_2 = data_fixture.create_user_and_token()

    response = api_client.get(reverse("api:settings:instance_id"))
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert CoreHandler().get_settings().allow_new_signups is True

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["instance_id"]) > 32

    settings = Settings.objects.first()
    settings.allow_new_signups = False
    settings.save()

    response = api_client.get(
        reverse("api:settings:instance_id"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["instance_id"] == settings.instance_id


@pytest.mark.django_db
def test_update_settings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    user_2, token_2 = data_fixture.create_user_and_token()

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert CoreHandler().get_settings().allow_new_signups is True

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["allow_new_signups"][0]["code"] == "invalid"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"instance_id": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().instance_id != "test"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["allow_new_signups"] is False
    assert "instance_id" not in response_json
    assert CoreHandler().get_settings().allow_new_signups is False

    response = api_client.patch(
        reverse("api:settings:update"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["allow_new_signups"] is False
    assert "instance_id" not in response_json
    assert CoreHandler().get_settings().allow_new_signups is False


@pytest.mark.django_db
def test_update_co_branding_logo(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )

    response = api_client.patch(
        reverse("api:settings:update"),
        {"co_branding_logo": {"name": file1.name}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["co_branding_logo"]["name"] == file1.name

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["co_branding_logo"]["name"] == file1.name


@pytest.mark.django_db
def test_update_show_baserow_help_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"show_baserow_help_request": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_baserow_help_request"] is False

    response = api_client.patch(
        reverse("api:settings:update"),
        {"allow_new_signups": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_baserow_help_request"] is False


@pytest.mark.django_db
def test_register_settings_data_type(api_client, data_fixture):
    registry = SettingsDataRegistry()

    class TmpSettingsDataType(SettingsDataType):
        type = "test_tmp"

        def get_settings_data(self, request) -> dict:
            return "hello"

    registry.register(TmpSettingsDataType())

    with patch("baserow.api.settings.views.settings_data_registry", new=registry):
        response = api_client.get(reverse("api:settings:get"))
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert len(response_json.keys()) > 1
        assert response_json["test_tmp"] == "hello"


@pytest.mark.parametrize("value", [None, "invalid"])
@pytest.mark.django_db
def test_update_email_verification_settings_invalid(api_client, data_fixture, value):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["email_verification"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
def test_update_email_verification_settings(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": "recommended"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().email_verification == "recommended"


@pytest.mark.django_db
def test_partial_update_does_not_overwrite_email_verification(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.patch(
        reverse("api:settings:update"),
        {"email_verification": "recommended"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert CoreHandler().get_settings().email_verification == "recommended"

    response = api_client.patch(
        reverse("api:settings:update"),
        {"track_workspace_usage": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json["track_workspace_usage"] is True

    settings = CoreHandler().get_settings()
    assert settings.email_verification == "recommended"
    assert response_json["email_verification"] == "recommended"
