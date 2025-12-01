from urllib.parse import parse_qs, urlparse

from django.urls import reverse

import pyotp
import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel
from baserow.test_utils.helpers import AnyList, AnyStr


@pytest.mark.django_db
def test_configuration_2fa_view_not_authenticated(api_client):
    url = reverse("api:two_factor_auth:configuration")
    response = api_client.get(
        url,
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_configuration_2fa_view_not_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {"allowed": True}


@pytest.mark.django_db
def test_configuration_2fa_view_totp_not_enabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_base_totp(user)

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "backup_codes": [],
        "is_enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }


@pytest.mark.django_db
def test_configuration_2fa_view_totp_enabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "backup_codes": [],
        "is_enabled": True,
        "provisioning_qr_code": "",
        "provisioning_url": "",
        "type": "totp",
    }


@pytest.mark.django_db
def test_configuration_2fa_view_cannot_be_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user.password = ""
    user.save()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {"allowed": False}


@pytest.mark.django_db
def test_configure_2fa_view_not_authenticated(api_client):
    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_configure_2fa_view_type_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "wrongtype"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_configure_2fa_view_type_not_provided(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_configure_2fa_view_cannot_be_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user.password = ""
    user.save()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_CANNOT_BE_CONFIGURED"


@pytest.mark.django_db
def test_configure_totp_2fa_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "backup_codes": [],
        "is_enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }

    # generate correct TOTP code based on provisioning_url
    parsed_url = urlparse(response_json["provisioning_url"])
    params = parse_qs(parsed_url.query)
    secret = params.get("secret", [])[0]
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    # provide TOTP code to confirm configuration
    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp", "code": valid_code},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "backup_codes": AnyList(),
        "is_enabled": True,
        "provisioning_qr_code": "",
        "provisioning_url": "",
        "type": "totp",
    }


@pytest.mark.django_db
def test_configure_totp_2fa_view_confirmation_failed_invalidcode(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "backup_codes": [],
        "is_enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }

    # provide TOTP code to confirm configuration
    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp", "code": "1234567"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED"


@pytest.mark.django_db
def test_configure_totp_2fa_view_failed_already_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED"


@pytest.mark.django_db
def test_configure_totp_2fa_view_replaces_previous_configuration(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "backup_codes": [],
        "is_enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }

    # when the totp is not fully enabled yet
    # we want to replace the previous configuration
    # as the user is trying to configure totp again
    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json2 = response.json()
    assert response.status_code == HTTP_200_OK, response_json2
    assert response_json2 == {
        "backup_codes": [],
        "is_enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }

    assert response_json["provisioning_url"] != response_json2["provisioning_url"]
    assert TwoFactorAuthProviderModel.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_disable_2fa_view_not_authenticated(api_client):
    url = reverse("api:two_factor_auth:disable")
    response = api_client.post(
        url,
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_disable_2fa_view_wrong_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:disable")
    response = api_client.post(
        url,
        {"password": "123456"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_403_FORBIDDEN, response_json
    assert response_json["error"] == "ERROR_WRONG_PASSWORD"


@pytest.mark.django_db
def test_disable_2fa_view_missing_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:disable")
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_disable_2fa_view_not_configured(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:two_factor_auth:disable")
    response = api_client.post(
        url,
        {"password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED"


@pytest.mark.django_db
def test_disable_2fa_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)

    url = reverse("api:two_factor_auth:disable")
    response = api_client.post(
        url,
        {"password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_verify_totp_view_missing_email(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": user.email, "password": "password"},
        format="json",
    )
    response_json = response.json()
    two_fa_token = response_json["token"]

    url = reverse("api:two_factor_auth:verify")
    response = api_client.post(
        url,
        {
            "code": "1234567",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_verify_totp_code_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    provider = data_fixture.configure_totp(user)

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": user.email, "password": "password"},
        format="json",
    )
    response_json = response.json()
    two_fa_token = response_json["token"]

    totp = pyotp.TOTP(provider.secret)
    valid_code = totp.now()

    url = reverse("api:two_factor_auth:verify")
    response = api_client.post(
        url,
        {
            "type": "totp",
            "email": user.email,
            "code": valid_code,
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "access_token": AnyStr(),
        "active_licenses": {"instance_wide": {}, "per_workspace": {}},
        "permissions": AnyList(),
        "refresh_token": AnyStr(),
        "token": AnyStr(),
        "user": {
            "completed_guided_tours": [],
            "completed_onboarding": False,
            "email_notification_frequency": "instant",
            "email_verified": False,
            "first_name": user.first_name,
            "id": user.id,
            "is_staff": False,
            "language": "en",
            "username": user.email,
        },
        "user_notifications": {"unread_count": 0},
        "user_session": AnyStr(),
    }


@pytest.mark.django_db
def test_verify_totp_code_view_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": user.email, "password": "password"},
        format="json",
    )
    response_json = response.json()
    two_fa_token = response_json["token"]

    url = reverse("api:two_factor_auth:verify")
    response = api_client.post(
        url,
        {
            "type": "totp",
            "email": user.email,
            "code": "1234567",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED"


@pytest.mark.django_db
def test_verify_totp_backup_code_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    provider = data_fixture.configure_totp(user)
    backup_code = provider.backup_codes[0]

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": user.email, "password": "password"},
        format="json",
    )
    response_json = response.json()
    two_fa_token = response_json["token"]

    url = reverse("api:two_factor_auth:verify")
    response = api_client.post(
        url,
        {
            "type": "totp",
            "email": user.email,
            "backup_code": backup_code,
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "access_token": AnyStr(),
        "active_licenses": {"instance_wide": {}, "per_workspace": {}},
        "permissions": AnyList(),
        "refresh_token": AnyStr(),
        "token": AnyStr(),
        "user": {
            "completed_guided_tours": [],
            "completed_onboarding": False,
            "email_notification_frequency": "instant",
            "email_verified": False,
            "first_name": user.first_name,
            "id": user.id,
            "is_staff": False,
            "language": "en",
            "username": user.email,
        },
        "user_notifications": {"unread_count": 0},
        "user_session": AnyStr(),
    }


@pytest.mark.django_db
def test_verify_totp_backup_code_view_invalid(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.configure_totp(user)

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": user.email, "password": "password"},
        format="json",
    )
    response_json = response.json()
    two_fa_token = response_json["token"]

    url = reverse("api:two_factor_auth:verify")
    response = api_client.post(
        url,
        {
            "type": "totp",
            "email": user.email,
            "backup_code": "XXXXX-XXXXX",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["error"] == "ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED"
