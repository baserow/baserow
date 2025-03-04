from contextlib import ContextDecorator
from enum import Enum
from functools import wraps
from typing import Callable, Dict, Optional, Type
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.http import HttpResponse
from django.shortcuts import redirect

from requests.models import PreparedRequest

from baserow.core.user.utils import generate_session_tokens_for_user, sign_user_session


# please keep this in sync with baserow_enterprise/locales/en.json
class SsoErrorCode(Enum):
    FEATURE_NOT_ACTIVE = "errorSsoFeatureNotActive"
    INVALID_SAML_REQUEST = "errorInvalidSamlRequest"
    INVALID_SAML_RESPONSE = "errorInvalidSamlResponse"
    USER_DEACTIVATED = "errorUserDeactivated"
    PROVIDER_DOES_NOT_EXIST = "errorProviderDoesNotExist"
    AUTH_FLOW_ERROR = "errorAuthFlowError"
    DIFFERENT_PROVIDER = "errorDifferentProvider"
    GROUP_INVITATION_EMAIL_MISMATCH = "errorWorkspaceInvitationEmailMismatch"
    SIGNUP_DISABLED = "errorSignupDisabled"


class map_sso_exceptions(ContextDecorator):
    """
    A context manager and decorator to map exceptions to SSO error codes. If the
    enclosed code block or decorated function raises an exception that is in the
    mapping, the provided redirect function will be called with the mapped error code.
    If the exception is not in the mapping, it will be raised normally.

    :param mapping: A dictionary that maps exceptions to SSO error codes.
    :param on_error: A callable that takes an error code and handles the action.
    """

    def __init__(
        self,
        mapping: Dict[Type[Exception], str],
        on_error: Callable[[str], None] | None = None,
    ):
        self.mapping = mapping
        if on_error is None:
            self.on_error = redirect_to_sign_in_error_page
        else:
            self.on_error = on_error

    def __enter__(self):
        pass

    # Context manager
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            # No exception occurred
            return False

        for exception, error_code in self.mapping.items():
            if isinstance(exc_value, exception):
                self.on_error(error_code)
                return True  # Swallow the exception after handling it

        # If exception not handled, propagate it
        return False

    # Decorator version
    def __call__(self, func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                for exception, error_code in self.mapping.items():
                    if isinstance(e, exception):
                        return self.on_error(error_code)
                raise e

        return wrapped_function


def urlencode_query_params(url: str, query_params: Dict[str, str]) -> str:
    """
    Adds the query parameters to the provided url.

    :param url: The url to which the query parameters should be added.
    :param query_params: The query parameters that should be added to the url.
    :return: The url with the query parameters added.
    """

    req = PreparedRequest()
    req.prepare_url(url, query_params)
    return req.url


def redirect_to_sign_in_error_page(
    error_code: Optional[SsoErrorCode] = None,
) -> HttpResponse:
    """
    Redirects the user to the error page in the frontend providing a message as
    query parameter if provided.

    :param error_message: The message that should be shown to the user.
    :return: The redirect response to the frontend error page with the error
        message encoded as query param.
    """

    frontend_error_page_url = get_frontend_login_error_url()

    if error_code:
        frontend_error_page_url = urlencode_query_params(
            frontend_error_page_url, {"error": error_code.value}
        )
    return redirect(frontend_error_page_url)


def get_valid_frontend_url(
    requested_original_url: Optional[str] = None,
    query_params: Optional[Dict[str, str]] = None,
    default_frontend_urls: list[str] | None = None,
    allow_any_path: bool = True,
):
    """
    Returns a valid absolute frontend url based on the original url requested
    before the redirection to the login (can be relative or absolute). If the
    original url is relative, it will be prefixed with the default hostname to
    make the IdP redirection work. If the original url doesn't match any of the given
    default_front_urls, the first default frontend url will be used instead.

    :param requested_original_url: The url to which the user should be
        redirected after a successful login.
    :param query_params: The query parameters to add to the URL.
    :param default_frontend_urls: The first one is the default fallback frontend URL.
      Baserow one is used if None. Others are also allowed as valid URLs.
    :return: The url with the token as a query parameter.
    """

    requested_url_parsed = urlparse(requested_original_url or "")

    if default_frontend_urls is None:
        default_frontend_urls = [get_frontend_default_redirect_url()]

    default_frontend_urls_parsed = [urlparse(u) for u in default_frontend_urls]
    default_frontend_url_parsed = default_frontend_urls_parsed[0]

    matching_url = default_frontend_url_parsed

    if requested_url_parsed.hostname is None:
        # provide a correct absolute url if the requested one is relative
        requested_url_parsed = default_frontend_url_parsed._replace(
            path=requested_url_parsed.path
        )

    else:
        found = False
        for allowed_url in default_frontend_urls_parsed:
            if requested_url_parsed.hostname == allowed_url.hostname:
                matching_url = allowed_url
                found = True

        if not found:
            # None are matching -> redirecting to main homepage
            requested_url_parsed = default_frontend_url_parsed
            matching_url = default_frontend_url_parsed

    if allow_any_path:
        if requested_url_parsed.path in ["", "/"]:
            # use the default frontend path if the requested one is empty
            requested_url_parsed = requested_url_parsed._replace(path=matching_url.path)
    elif not requested_url_parsed.geturl().startswith(matching_url.geturl()):
        # if using a path that doesn't match the allowed urls, we reset to default url
        requested_url_parsed = matching_url

    if query_params:
        return urlencode_query_params(requested_url_parsed.geturl(), query_params)

    return requested_url_parsed.geturl()


def urlencode_user_tokens(frontend_url: str, user: AbstractUser) -> str:
    """
    Adds the token and user_session as a query parameters to the provided frontend url.
    Please ensure to call the get_url_for_frontend_page_if_valid_or_default() method
    before calling this method, so to be sure to encode the refresh token in a
    valid Baserow frontend url.

    :param frontend_url: The valid frontend url to which the user should be
        redirected after a successful login.
    :param user: The user that sign in with an external provider and is going to
        start a new session in Baserow.
    :return: The url with the token and user_session as query parameters.
    """

    user_tokens = generate_session_tokens_for_user(user, include_refresh_token=True)
    refresh_token = user_tokens["refresh_token"]
    user_session = sign_user_session(user.id, refresh_token)
    return urlencode_query_params(
        frontend_url,
        {
            "token": refresh_token,
            "user_session": user_session,
        },
    )


def redirect_user_on_success(
    user: AbstractUser, requested_original_url: Optional[str] = None
) -> HttpResponse:
    """
    Ensure that the requested original url is valid or take the frontend default
    url. It adds the JWT token as query parameter to the url so that the user
    can start a new session.

    :param user: The user that sign in with an external provider and is going to
        start a new session in Baserow.
    :param requested_original_url: The url to which the user should be
        redirected after a successful login.
    :return: The redirect HTTP response to the url with the token as a query
        parameter.
    """

    valid_frontend_url = get_valid_frontend_url(requested_original_url)
    redirect_url = urlencode_user_tokens(valid_frontend_url, user)
    return redirect(redirect_url)


def get_frontend_default_redirect_url() -> str:
    """
    Returns the url to the frontend dashboard.

    :return: The absolute url to the Baserow dashboard.
    """

    return urljoin(settings.PUBLIC_WEB_FRONTEND_URL, "/dashboard")


def get_frontend_login_error_url() -> str:
    """
    Returns the url to the frontend login error page.

    :return: The absolute url to the Baserow login error page.
    """

    return urljoin(settings.PUBLIC_WEB_FRONTEND_URL, "/login/error")


def get_frontend_login_saml_url() -> str:
    """
    Returns the url to the frontend SAML login page.

    :return: The absolute url to the Baserow SAML login page.
    """

    return urljoin(settings.PUBLIC_WEB_FRONTEND_URL, "/login/saml")


def get_standardized_url(url: str) -> str:
    """
    Standardize the full URL, keeping all components but normalizing the port.
    Ignores port 80 for HTTP and port 443 for HTTPS.

    :param url: The full URL as a string.
    :return: A standardized URL string.
    """

    parsed = urlparse(url)

    default_ports = {"http": 80, "https": 443}
    netloc = (
        parsed.hostname
        if parsed.port == default_ports.get(parsed.scheme)
        else parsed.netloc
    )
    path = (
        "/" if not parsed.path or parsed.path == "/" else "/" + parsed.path.strip("/")
    )

    return parsed._replace(netloc=netloc, path=path).geturl()
