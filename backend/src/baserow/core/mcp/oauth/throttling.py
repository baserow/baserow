from django.conf import settings

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
