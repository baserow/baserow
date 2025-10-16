import pyotp
from django.urls import reverse
import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.test_utils.helpers import AnyList, AnyStr

from urllib.parse import urlparse, parse_qs


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
def test_configure_totp_view_confirmation_failed(api_client, data_fixture):
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
