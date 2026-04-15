from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from rest_framework import status

from baserow.throttling.blacklist import is_ip_blacklisted, is_token_blacklisted


class ThrottleBlacklistMiddleware:
    """
    Fast-path rejection for recently throttled tokens and, optionally, IPs.

    When ``ConcurrentUserRequestsThrottle`` denies a request it writes the
    SHA-256 hash of the bearer token to Redis with a short TTL.  This
    middleware — placed *before* authentication — checks that blacklist on
    every request.  A hit returns 429 immediately, skipping JWT validation,
    DB/cache lookups, DRF view initialisation, permissions, and serializers.

    When ``BASEROW_THROTTLE_IP_BLACKLIST_ENABLED`` is ``True``, anonymous
    requests (no ``Authorization`` header) are also checked against an
    IP-based blacklist.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        if settings.BASEROW_THROTTLE_IP_BLACKLIST_ENABLED:
            from baserow.api.sessions import get_user_remote_ip_address_from_request

            self._get_ip = get_user_remote_ip_address_from_request
            self._check_anonymous = self._check_ip
        else:
            self._check_anonymous = self._noop

    def __call__(self, request: HttpRequest) -> HttpResponse:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("JWT "):
            ttl = is_token_blacklisted(auth_header[4:])
            if ttl is not None:
                return self._throttled_response(ttl)
        elif self._check_anonymous(request):
            return self._throttled_response()
        return self.get_response(request)

    def _check_ip(self, request: HttpRequest) -> bool:
        ip = self._get_ip(request)
        return bool(ip and is_ip_blacklisted(ip))

    @staticmethod
    def _noop(request: HttpRequest) -> bool:
        return False

    @staticmethod
    def _throttled_response(retry_after: int | None = None) -> JsonResponse:
        response = JsonResponse(
            {
                "error": "ERROR_THROTTLED",
                "detail": "Request was throttled. Try again later.",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        if retry_after is not None:
            response["Retry-After"] = retry_after
        return response


class ConcurrentUserRequestsMiddleware:
    """
    Counterpart of ``ConcurrentUserRequestsThrottle``.  Removes the request
    id from the Redis sorted set once the response has been generated, freeing
    the concurrency slot.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        from baserow.throttling.handler import ConcurrentUserRequestsThrottle

        response = self.get_response(request)
        ConcurrentUserRequestsThrottle.on_request_processed(request)
        return response
