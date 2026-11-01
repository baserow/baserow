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
    and JWKS endpoints). When the `BASEROW_SSO_ALLOW_PRIVATE_ADDRESS` Django setting
    is `False`, the advocate library is used so that these URLs can't be used to
    reach Baserow's internal network (SSRF protection). The setting defaults to
    `True` for backwards compatibility.
    """

    if settings.BASEROW_SSO_ALLOW_PRIVATE_ADDRESS is True:
        return requests.request
    else:
        return advocate.request


def enforce_sso_ssrf_protection(session: requests.Session) -> requests.Session:
    """
    Mounts advocate's validating adapter on the given session so that requests made
    through it can't reach Baserow's internal network (SSRF protection). This guards
    OAuth2 fetches whose URLs come from admin/builder configured providers or from
    their well-known documents, like the token and user info endpoints. Only active
    when the `BASEROW_SSO_ALLOW_PRIVATE_ADDRESS` Django setting is `False`; it
    defaults to `True` for backwards compatibility. Note that advocate does not
    support proxies, so `HTTP_PROXY`/`HTTPS_PROXY` are rejected while active.
    """

    if settings.BASEROW_SSO_ALLOW_PRIVATE_ADDRESS is not True:
        session.mount("http://", advocate.ValidatingHTTPAdapter())
        session.mount("https://", advocate.ValidatingHTTPAdapter())
    return session


def is_sso_feature_active():
    return LicenseHandler.instance_has_feature(SSO)


def check_sso_feature_is_active_or_raise():
    if not is_sso_feature_active():
        raise FeaturesNotAvailableError()
