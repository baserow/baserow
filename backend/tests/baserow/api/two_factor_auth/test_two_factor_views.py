import pyotp
from django.urls import reverse
import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.test_utils.helpers import AnyList, AnyStr

from urllib.parse import urlparse, parse_qs


@pytest.mark.django_db
def test_configure_totp_view_not_authenticated(api_client):
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
def test_configure_totp_view_type_does_not_exist(api_client, data_fixture):
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
def test_configure_totp_view(api_client, data_fixture):
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
        "enabled": False,
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
        "enabled": True,
        "provisioning_qr_code": "",
        "provisioning_url": "",
        "type": "totp",
    }


@pytest.mark.django_db
def test_configure_totp_view_confirmation_failed_invalidcode(api_client, data_fixture):
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
        "enabled": False,
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
def test_configure_totp_view_failed_already_provisioned(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    totp_provider = data_fixture.configure_totp(user)

    url = reverse("api:two_factor_auth:configuration")
    response = api_client.post(
        url,
        {"type": "totp"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # TODO:
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {}


@pytest.mark.django_db
def test_configure_totp_view_replaces_previous_configuration(api_client, data_fixture):
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
        "enabled": False,
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
        "enabled": False,
        "provisioning_qr_code": AnyStr(),
        "provisioning_url": AnyStr(),
        "type": "totp",
    }

    assert response_json["provisioning_url"] != response_json2["provisioning_url"]
