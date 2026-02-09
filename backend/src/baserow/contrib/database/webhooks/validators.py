from functools import partial
from http.client import _is_illegal_header_value, _is_legal_header_name
from typing import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from baserow.core.ssrf import (
    InvalidSSRFAddress,
    SSRFValidator,
    ssrf_safe_request,
    validate_url,
)

INVALID_URL_CODE = "invalid_url"


def get_webhook_request_function() -> Callable:
    """
    Return the appropriate request function based on production environment
    or settings.
    In production mode, SSRF protection is used so that the internal
    network can't be reached. This can be disabled by changing the Django
    setting BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS.
    """

    if settings.BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS is True:
        from requests import request

        return request
    else:
        validator = get_ssrf_validator()
        return partial(ssrf_safe_request.request, validator=validator)


def get_ssrf_validator() -> SSRFValidator:
    """
    Return an SSRFValidator with the user configurable white and black lists.
    """

    return SSRFValidator(
        ip_blacklist=settings.BASEROW_WEBHOOKS_IP_BLACKLIST,
        ip_whitelist=settings.BASEROW_WEBHOOKS_IP_WHITELIST,
        hostname_blacklist=settings.BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST,
    )


def url_validator(value):
    """
    This is a custom url validation, needed in order to make sure that users will not
    enter a url which could be in the network of where baserow is running. It uses
    Baserow's SSRF protection module for address validation.

    :param value: The URL that must be validated.
    :raises django.core.exceptions.ValidationError: When the provided URL is not valid.
    :return: The provided URL if valid.
    """

    if settings.BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS is True:
        return value

    # Make sure we a are valid URL with a schema before parsing otherwise the parser can
    # return incorrect hostnames etc. For example without this the URL
    # `www.google.com` will be parsed by urlparse to have a path of `www.google.com`
    # and an empty hostname.
    URLValidator(code=INVALID_URL_CODE)(value)

    try:
        url = urlparse(value)
        # Reading an invalid port can raise a ValueError exception
        port = url.port
    except ValueError as e:
        raise ValidationError("Invalid URL", code=INVALID_URL_CODE) from e

    # in case the user does not provide a port we assume 80 if it is a
    # http url or 443 otherwise.
    if port is None:
        if url.scheme == "http":
            port = 80
        else:
            port = 443

    validator = get_ssrf_validator()
    dns_timeout = getattr(settings, "BASEROW_WEBHOOKS_URL_CHECK_TIMEOUT_SECS", 10)

    try:
        validate_url(url.hostname, port, validator=validator, timeout=dns_timeout)
        return value
    except InvalidSSRFAddress as e:
        raise ValidationError("Invalid URL", code=INVALID_URL_CODE) from e


def header_name_validator(value):
    if not _is_legal_header_name(value.encode()):
        raise ValidationError("Invalid header name")


def header_value_validator(value):
    if _is_illegal_header_value(value.encode()):
        raise ValidationError("Invalid header value")
