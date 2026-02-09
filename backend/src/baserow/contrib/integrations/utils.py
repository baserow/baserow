from typing import Callable

from django.conf import settings

import requests

from baserow.core.ssrf import ssrf_safe_request


def get_http_request_function() -> Callable:
    """
    Return the appropriate request function based on production environment
    or settings.
    In production mode, SSRF protection is used so that the internal
    network can't be reached. This can be disabled by changing the Django
    setting INTEGRATIONS_ALLOW_PRIVATE_ADDRESS.
    """

    if settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS is True:
        return requests.request
    else:
        return ssrf_safe_request.request
