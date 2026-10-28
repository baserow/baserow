from django.conf import settings

from baserow.throttling.handler import RateLimitThrottle


class CoreHTTPTriggerRateThrottle(RateLimitThrottle):
    """
    Limits how often one HTTP trigger may be called.

    Keyed on the trigger's uid: the callers are anonymous, and every accepted
    call is stored in the workflow's history, so the budget belongs to the
    trigger rather than to whoever calls it.
    """

    scope = "core_http_trigger"

    def get_rate_limits(self, request):
        """
        :param request: The call being counted.
        :return: The configured limits. Empty switches the throttle off.
        """

        return settings.AUTOMATION_HTTP_TRIGGER_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        """
        :param request: The call being counted.
        :return: The uid of the called trigger.
        """

        return str(request.parser_context["kwargs"]["webhook_uid"])
