from django.conf import settings

from baserow.throttling.handler import RateLimitThrottle


class OAuthAccountStartRateThrottle(RateLimitThrottle):
    """
    Limits how often one user starts signing in to a provider, whichever. Each
    start keeps a pending sign-in in the cache until it's finished or expires.
    """

    scope = "oauth_account_start"

    def get_rate_limits(self, request):
        return settings.INTEGRATIONS_OAUTH_START_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        user = request.user
        return str(user.id) if user.is_authenticated else None
