from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils.module_loading import import_string

import pytest
from rest_framework.status import HTTP_429_TOO_MANY_REQUESTS

from baserow.throttling.blacklist import (
    _token_key,
    blacklist_ip,
    blacklist_token,
    get_token_cooldown_time,
    is_ip_blacklisted,
)
from baserow.throttling.middleware import ThrottleBlacklistMiddleware


def test_blacklist_key_is_sha256_hex():
    key = _token_key("my-secret-token")
    assert key.startswith("throttle_bl:")
    # SHA-256 hex digest is 64 chars
    assert len(key) == len("throttle_bl:") + 64
    # Token itself must not appear in the key
    assert "my-secret-token" not in key


@override_settings(BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS=7)
def test_blacklist_and_check():
    assert not get_token_cooldown_time("token-abc")

    blacklist_token("token-abc")
    assert get_token_cooldown_time("token-abc") == 7

    assert not get_token_cooldown_time("token-xyz")


def test_blacklist_different_tokens_are_independent():
    blacklist_token("token-1")
    assert get_token_cooldown_time("token-1")
    assert not get_token_cooldown_time("token-2")


def test_blacklist_returns_remaining_ttl():
    with patch("baserow.throttling.blacklist.time.time", return_value=100):
        blacklist_token("token-remaining", ttl=7)

    with patch("baserow.throttling.blacklist.time.time", return_value=103.1):
        assert get_token_cooldown_time("token-remaining") == 4


def test_blacklist_token_noops_when_ttl_is_zero():
    blacklist_token("token-zero", ttl=0)

    assert get_token_cooldown_time("token-zero") is None


def test_blacklist_ip_noops_when_ttl_is_negative():
    blacklist_ip("192.168.1.9", ttl=-1)

    assert is_ip_blacklisted("192.168.1.9") is None


def test_throttle_handler_import_path_is_valid():
    from baserow.throttling.handler import ConcurrentUserRequestsThrottle

    imported = import_string(
        "baserow.throttling.handler.ConcurrentUserRequestsThrottle"
    )

    assert imported is ConcurrentUserRequestsThrottle


def _make_middleware(status_code=200):
    """Build the middleware with a dummy downstream response."""

    def ok_response(request):
        return HttpResponse(status=status_code)

    return ThrottleBlacklistMiddleware(ok_response)


def test_middleware_rejects_blacklisted_token():
    middleware = _make_middleware()
    blacklist_token("the-token")

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", HTTP_AUTHORIZATION="JWT the-token")

    response = middleware(request)

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert b"Request was throttled." in response.content


def test_middleware_allows_non_blacklisted_token():
    middleware = _make_middleware()

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", HTTP_AUTHORIZATION="JWT clean-token")

    response = middleware(request)
    assert response.status_code == 200


def test_middleware_ignores_non_jwt_requests():
    middleware = _make_middleware()

    factory = RequestFactory()
    request = factory.get("/api/workspaces/")

    response = middleware(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_zero_db_queries_on_blacklist_hit(data_fixture):
    """The whole point: a blacklisted token triggers zero DB queries."""

    middleware = _make_middleware()
    blacklist_token("db-test-token")

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", HTTP_AUTHORIZATION="JWT db-test-token")

    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        response = middleware(request)

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert len(ctx.captured_queries) == 0


@pytest.mark.django_db
@override_settings(
    BASEROW_CONCURRENT_USER_REQUESTS_THROTTLE_TIMEOUT=30,
    BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS=7,
)
def test_throttle_populates_blacklist_on_deny(data_fixture):
    """When the throttle denies a request, the token is blacklisted."""

    from rest_framework.test import APIRequestFactory

    from baserow.api.exceptions import ThrottledAPIException
    from baserow.throttling.handler import ConcurrentUserRequestsThrottle

    user = data_fixture.create_user()
    token_str = f"fake-token-{user.id}"

    # Build a realistic DRF request (matching existing throttle test pattern)
    factory = APIRequestFactory()
    request = factory.get("/api/workspaces/", HTTP_AUTHORIZATION=f"JWT {token_str}")
    request.user = user

    class DummyDjangoRequest:
        def __init__(self):
            self.path = "/api/workspaces/"
            self.user = user
            self.META = {"HTTP_AUTHORIZATION": f"JWT {token_str}"}

    request._request = DummyDjangoRequest()

    ConcurrentUserRequestsThrottle.timer = lambda s: 1000
    ConcurrentUserRequestsThrottle.rate = 1

    throttle = ConcurrentUserRequestsThrottle()

    # First request is allowed
    assert throttle.allow_request(request, None)
    assert not get_token_cooldown_time(token_str)

    # Second concurrent request is denied → raises and blacklists the token
    # with the fixed cooldown (BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS).
    throttle2 = ConcurrentUserRequestsThrottle()
    with pytest.raises(ThrottledAPIException) as exc_info:
        throttle2.allow_request(request, None)

    assert exc_info.value.wait == 7
    assert throttle2.wait() == 7
    assert get_token_cooldown_time(token_str) == 7

    ConcurrentUserRequestsThrottle.on_request_processed(request._request)


# --- IP blacklist tests ---


@override_settings(BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS=9)
def test_ip_blacklist_and_check():
    assert not is_ip_blacklisted("192.168.1.1")

    blacklist_ip("192.168.1.1")
    assert is_ip_blacklisted("192.168.1.1") == 9
    assert not is_ip_blacklisted("192.168.1.2")


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_rejects_blacklisted_ip_for_anonymous_request():
    middleware = _make_middleware()
    blacklist_ip("10.0.0.1")

    factory = RequestFactory()
    # REMOTE_ADDR is how Django exposes the client IP
    request = factory.get("/api/workspaces/", REMOTE_ADDR="10.0.0.1")

    response = middleware(request)
    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert b"Request was throttled." in response.content


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_allows_non_blacklisted_ip():
    middleware = _make_middleware()
    blacklist_ip("10.0.0.1")

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", REMOTE_ADDR="10.0.0.2")

    response = middleware(request)
    assert response.status_code == 200


@override_settings(BASEROW_THROTTLE_IP_ENABLED=False)
def test_middleware_skips_ip_check_when_disabled():
    middleware = _make_middleware()
    blacklist_ip("10.0.0.1")

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", REMOTE_ADDR="10.0.0.1")

    response = middleware(request)
    assert response.status_code == 200


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_ip_check_does_not_apply_to_jwt_requests():
    """JWT requests use the token blacklist, not the IP blacklist."""

    middleware = _make_middleware()
    blacklist_ip("10.0.0.1")

    factory = RequestFactory()
    request = factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_AUTHORIZATION="JWT some-clean-token",
    )

    # IP is blacklisted but this is a JWT request — should pass
    response = middleware(request)
    assert response.status_code == 200


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_uses_x_forwarded_for_header():
    middleware = _make_middleware()
    blacklist_ip("203.0.113.50")

    factory = RequestFactory()
    request = factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",  # proxy IP
        HTTP_X_FORWARDED_FOR="203.0.113.50, 70.41.3.18",
    )

    response = middleware(request)
    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_does_not_blacklist_anonymous_ip_after_non_429_response():
    middleware = _make_middleware(status_code=200)

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", REMOTE_ADDR="198.51.100.11")

    response = middleware(request)

    assert response.status_code == 200
    assert not is_ip_blacklisted("198.51.100.11")


@override_settings(BASEROW_THROTTLE_IP_ENABLED=True)
def test_middleware_does_not_blacklist_ip_for_jwt_429_response():
    middleware = _make_middleware(status_code=HTTP_429_TOO_MANY_REQUESTS)

    factory = RequestFactory()
    request = factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="198.51.100.12",
        HTTP_AUTHORIZATION="JWT some-clean-token",
    )

    response = middleware(request)

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert not is_ip_blacklisted("198.51.100.12")


@override_settings(BASEROW_THROTTLE_IP_ENABLED=False)
def test_middleware_does_not_blacklist_anonymous_ip_when_disabled():
    middleware = _make_middleware(status_code=HTTP_429_TOO_MANY_REQUESTS)

    factory = RequestFactory()
    request = factory.get("/api/workspaces/", REMOTE_ADDR="198.51.100.13")

    response = middleware(request)

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert not is_ip_blacklisted("198.51.100.13")
