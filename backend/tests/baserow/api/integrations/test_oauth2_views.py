from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import signing
from django.test import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_302_FOUND, HTTP_400_BAD_REQUEST

from baserow.contrib.integrations.oauth2.handler import STATE_SALT
from tests.baserow.contrib.integrations.external_api_test_utils import fake_response

FRONTEND = "http://localhost:3000"
SEND = "baserow.contrib.integrations.oauth2.integration_types.send_http_request"


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND)
def test_authorize_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_google_integration(user=user, refresh_token="")
    url = reverse(
        "api:integrations:oauth2_authorize", kwargs={"integration_id": integration.id}
    )

    response = api_client.post(
        url,
        {"return_url": f"{FRONTEND}/automation/1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    authorization_url = response.json()["authorization_url"]
    assert authorization_url.startswith("https://accounts.google.com/")
    assert "state=" in authorization_url

    response = api_client.post(
        url,
        {"return_url": "https://elsewhere.example/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_OAUTH2_INVALID_RETURN_URL"

    unconfigured = data_fixture.create_google_integration(user=user, client_id="")
    response = api_client.post(
        reverse(
            "api:integrations:oauth2_authorize",
            kwargs={"integration_id": unconfigured.id},
        ),
        {"return_url": f"{FRONTEND}/automation/1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED"

    slack = data_fixture.create_slack_bot_integration(user=user)
    response = api_client.post(
        reverse(
            "api:integrations:oauth2_authorize", kwargs={"integration_id": slack.id}
        ),
        {"return_url": f"{FRONTEND}/automation/1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_OAUTH2_NOT_SUPPORTED"

    _, other_token = data_fixture.create_user_and_token()
    response = api_client.post(
        url,
        {"return_url": f"{FRONTEND}/automation/1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND)
def test_callback_redirects_back_with_the_outcome(api_client, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(user=user, refresh_token="")
    url = reverse("api:integrations:oauth2_callback")
    state = signing.dumps(
        {
            "integration_id": integration.id,
            "user_id": user.id,
            "return_url": f"{FRONTEND}/automation/1?tab=integrations",
        },
        salt=STATE_SALT,
    )

    responses = [
        fake_response(200, {"access_token": "at", "refresh_token": "rt"}),
        fake_response(200, {"email": "me@example.com"}),
    ]
    with patch(SEND, side_effect=responses):
        response = api_client.get(url, {"code": "c", "state": state})
    assert response.status_code == HTTP_302_FOUND
    redirected = urlparse(response["Location"])
    assert redirected.path == "/automation/1"
    query = parse_qs(redirected.query)
    assert query["tab"] == ["integrations"]
    assert query["oauth2_status"] == ["success"]
    assert query["oauth2_integration"] == [str(integration.id)]
    integration.refresh_from_db()
    assert integration.account_email == "me@example.com"

    # Consent refused by the person: back to the page with the reason.
    response = api_client.get(
        url, {"error": "access_denied", "state": state, "error_description": "No"}
    )
    query = parse_qs(urlparse(response["Location"]).query)
    assert query["oauth2_status"] == ["error"]
    assert query["oauth2_error"] == ["No"]

    # A forged state cannot name a page, so the frontend root explains it.
    response = api_client.get(url, {"code": "c", "state": "forged"})
    assert response.status_code == HTTP_302_FOUND
    assert response["Location"].startswith(f"{FRONTEND}/?")
    assert "oauth2_status=error" in response["Location"]
