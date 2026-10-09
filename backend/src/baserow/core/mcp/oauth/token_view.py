from oauth2_provider.views import TokenView

from .throttling import MCPOAuthTokenRateThrottle, rate_limited


class MCPTokenView(TokenView):
    """The library's token endpoint, rate-limited per client IP."""

    def post(self, request, *args, **kwargs):
        limited = rate_limited(MCPOAuthTokenRateThrottle(), request, self)
        if limited is not None:
            return limited
        return super().post(request, *args, **kwargs)
