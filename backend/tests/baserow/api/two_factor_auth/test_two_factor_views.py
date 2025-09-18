from django.urls import reverse
import pytest
from rest_framework.status import HTTP_200_OK


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
    assert response.status_code == HTTP_200_OK
    assert response_json == {}
