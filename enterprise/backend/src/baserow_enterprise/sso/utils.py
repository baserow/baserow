from typing import Callable

from django.conf import settings

import requests

import advocate
from baserow_enterprise.features import SSO
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler


def get_sso_request_function() -> Callable:
    """
    Returns the request function that must be used for outgoing SSO requests to
    admin/builder configured identity provider URLs (the OpenID Connect well-known
    and JWKS endpoints). In production the advocate library is used so that these
    URLs can't be used to reach Baserow's internal network (SSRF protection). This
    can be disabled by setting the `BASEROW_SSO_ALLOW_PRIVATE_ADDRESS` Django setting
    to `True`.
    """

    if settings.BASEROW_SSO_ALLOW_PRIVATE_ADDRESS is True:
        return requests.request
    else:
        return advocate.request


def is_sso_feature_active():
    return LicenseHandler.instance_has_feature(SSO)


def check_sso_feature_is_active_or_raise():
    if not is_sso_feature_active():
        raise FeaturesNotAvailableError()
