from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from baserow.api.exceptions import (
    ThrottledAPIException,
    api_exception_to_json_response,
)
from baserow.api.sessions import get_user_remote_ip_address_from_request
from baserow.throttling.handler import ConcurrentUserRequestsThrottle

from .blacklist import get_token_cooldown_time, is_ip_blacklisted
from .utils import get_auth_token


class ThrottleBlacklistMiddleware:
    """
    Fast-path rejection for recently throttled tokens and, optionally, IPs.

    When ``ConcurrentUserRequestsThrottle`` denies a request it writes the
    SHA-256 hash of the bearer token to Redis with a short TTL.  This
    middleware — placed *before* authentication — checks that blacklist on
    every request.  A hit returns 429 immediately, skipping JWT validation,
    DB/cache lookups, DRF view initialisation, permissions, and serializers.

    When ``BASEROW_THROTTLE_IP_ENABLED`` is ``True``, anonymous requests
    (no ``Authorization`` header) are also checked against an IP-based
    blacklist.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        if settings.BASEROW_THROTTLE_IP_ENABLED:
            self._check_anonymous = lambda request: is_ip_blacklisted(
                get_user_remote_ip_address_from_request(request)
            )
        else:
            self._check_anonymous = lambda request: None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if token := get_auth_token(request):
            cooldown = get_token_cooldown_time(token)
        else:
            cooldown = self._check_anonymous(request)

        if cooldown is not None:
            # Use the same response format returned by ConcurrentUserRequestsThrottle
            return api_exception_to_json_response(ThrottledAPIException(wait=cooldown))

        return self.get_response(request)


class ConcurrentUserRequestsMiddleware:
    """
    Counterpart of ``ConcurrentUserRequestsThrottle``.  Removes the request
    id from the Redis sorted set once the response has been generated, freeing
    the concurrency slot.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        finally:
            ConcurrentUserRequestsThrottle.on_request_processed(request)
