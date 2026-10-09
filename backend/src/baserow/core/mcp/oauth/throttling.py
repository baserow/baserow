from django.conf import settings
from django.http import JsonResponse

from baserow.api.exceptions import ThrottledAPIException
from baserow.core.utils import get_user_remote_ip_address_from_request
from baserow.throttling.handler import RateLimitThrottle


class MCPOAuthTokenRateThrottle(RateLimitThrottle):
    """
    Limits calls to the OAuth token endpoint per client IP. The endpoint takes no
    user credentials, so the IP is the only key an anonymous caller can't pick.
    """

    scope = "mcp_oauth_token"

    def get_rate_limits(self, request):
        return settings.BASEROW_MCP_OAUTH_TOKEN_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        return get_user_remote_ip_address_from_request(request)


class MCPOAuthRegistrationRateThrottle(MCPOAuthTokenRateThrottle):
    """Limits anonymous DCR registrations per client IP."""

    scope = "mcp_oauth_registration"

    def get_rate_limits(self, request):
        return settings.BASEROW_MCP_OAUTH_REGISTRATION_RATE_LIMITS


class MCPOAuthAuthorizeRateThrottle(MCPOAuthTokenRateThrottle):
    """
    Limits anonymous authorization requests per client IP. Each one can fetch a
    CIMD client's metadata document and store the client.
    """

    scope = "mcp_oauth_authorize"

    def get_rate_limits(self, request):
        return settings.BASEROW_MCP_OAUTH_AUTHORIZE_RATE_LIMITS


def rate_limited(throttle, request, view) -> JsonResponse | None:
    """
    The OAuth `slow_down` response when `throttle` refuses the request, else None.
    """

    try:
        throttle.allow_request(request, view)
    except ThrottledAPIException:
        response = JsonResponse(
            {"error": "slow_down", "error_description": "Too many requests."},
            status=429,
        )
        response["Retry-After"] = str(throttle.wait())
        return response
    return None
