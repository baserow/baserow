from django.http import JsonResponse

from oauth2_provider.views import TokenView

from baserow.api.exceptions import ThrottledAPIException

from .throttling import MCPOAuthTokenRateThrottle


class MCPTokenView(TokenView):
    """The library's token endpoint, rate-limited per client IP."""

    def post(self, request, *args, **kwargs):
        throttle = MCPOAuthTokenRateThrottle()
        try:
            throttle.allow_request(request, self)
        except ThrottledAPIException:
            response = JsonResponse(
                {
                    "error": "slow_down",
                    "error_description": "Too many token requests.",
                },
                status=429,
            )
            response["Retry-After"] = str(throttle.wait())
            return response
        return super().post(request, *args, **kwargs)
