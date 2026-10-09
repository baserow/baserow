from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.throttling.types import RateLimit

LIMITS = (RateLimit(period_in_seconds=60, number_of_calls=2),)


def _token_request(client, ip):
    return client.post(
        "/oauth/token/",
        {"grant_type": "authorization_code", "code": "nope", "client_id": "x"},
        HTTP_X_FORWARDED_FOR=ip,
    )


@pytest.mark.django_db
@override_settings(BASEROW_MCP_OAUTH_TOKEN_RATE_LIMITS=LIMITS)
def test_token_endpoint_is_rate_limited_per_ip(client):
    with freeze_time("2026-01-01 12:00:00"):
        assert _token_request(client, "1.1.1.1").status_code != 429
        assert _token_request(client, "1.1.1.1").status_code != 429
        limited = _token_request(client, "1.1.1.1")
        other_ip = _token_request(client, "2.2.2.2")

    assert limited.status_code == 429
    assert limited.json()["error"] == "slow_down"
    assert int(limited["Retry-After"]) > 0
    assert other_ip.status_code != 429


def _authorize_request(client, ip):
    return client.get("/oauth/authorize/?client_id=x", HTTP_X_FORWARDED_FOR=ip)


@pytest.mark.django_db
@override_settings(BASEROW_MCP_OAUTH_AUTHORIZE_RATE_LIMITS=LIMITS)
def test_authorize_endpoint_is_rate_limited_per_ip(client):
    with freeze_time("2026-01-01 12:00:00"):
        assert _authorize_request(client, "1.1.1.1").status_code != 429
        assert _authorize_request(client, "1.1.1.1").status_code != 429
        limited = _authorize_request(client, "1.1.1.1")
        other_ip = _authorize_request(client, "2.2.2.2")

    assert limited.status_code == 429
    assert limited.json()["error"] == "slow_down"
    assert int(limited["Retry-After"]) > 0
    assert other_ip.status_code != 429
