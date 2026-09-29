from django.conf import settings

from rest_framework.throttling import SimpleRateThrottle

from baserow.core.utils import get_user_remote_ip_address_from_request


class AbuseReportRateThrottle(SimpleRateThrottle):
    scope = "abuse_report"

    def get_rate(self):
        return settings.BASEROW_ABUSE_REPORT_THROTTLE_RATE or None

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": get_user_remote_ip_address_from_request(request),
        }
