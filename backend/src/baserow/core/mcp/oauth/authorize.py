from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpRequest, QueryDict

from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError
from oauth2_provider.oauth2_backends import get_oauthlib_core
from oauth2_provider.settings import oauth2_settings
from oauthlib.oauth2 import AccessDeniedError, InvalidRequestError
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error

from baserow.core.mcp.models import MCPEndpoint

from .validators import (
    CONSENT_CREDENTIAL,
    MCP_SCOPE,
    OFFLINE_ACCESS_SCOPE,
    endpoint_scope,
)

AUTHORIZE_PATH = "/oauth/authorize/"


def _authorize_request(original_request, user, query: str) -> HttpRequest:
    """
    The library reads the authorization parameters from the request URI, so we
    rebuild a GET request for the authorize endpoint carrying the original query.
    """

    request = HttpRequest()
    request.method = "GET"
    request.path = request.path_info = AUTHORIZE_PATH
    request.META = {
        **original_request.META,
        "REQUEST_METHOD": "GET",
        "PATH_INFO": AUTHORIZE_PATH,
        "QUERY_STRING": query,
    }
    request.GET = QueryDict(query)
    request.user = user
    return request


def _add_query_param(uri: str, name: str, value: str) -> str:
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True) + [(name, value)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def with_iss(request: HttpRequest, uri: str) -> str:
    """
    Adds the RFC 9207 `iss` parameter to a redirect back to the client, like the
    library does for successful responses.
    """

    if not oauth2_settings.COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS:
        return uri
    issuer = oauth2_settings.oauth2_authorization_server_issuer(request)
    return _add_query_param(uri, "iss", issuer)


def is_redirectable(error: OAuthToolkitError) -> bool:
    """
    Whether the error may be sent back to the client's redirect URI. Fatal errors
    carry the unvalidated, client-supplied URI, so they never are.
    """

    return not isinstance(error, FatalClientError) and bool(
        error.oauthlib_error.redirect_uri
    )


def error_redirect_url(request: HttpRequest, error: OAuthToolkitError) -> str:
    """The client redirect URI carrying the error, `state` and `iss`."""

    oauthlib_error = error.oauthlib_error
    return with_iss(request, oauthlib_error.in_uri(oauthlib_error.redirect_uri))


def _validate(request: HttpRequest):
    scopes, credentials = get_oauthlib_core().validate_authorization_request(request)
    state = credentials.get("state")
    redirect_uri = credentials["redirect_uri"]

    # Only S256 is supported; the library would otherwise accept `plain` here and
    # fail later when the code is created.
    if request.GET.get("code_challenge_method") != "S256":
        raise OAuthToolkitError(
            error=InvalidRequestError(
                description="Only the S256 code_challenge_method is supported.",
                state=state,
            ),
            redirect_uri=redirect_uri,
        )

    # The token audience is pinned to the MCP resource; a client asking for any other
    # resource is rejected, a missing one is accepted.
    if any(r != settings.MCP_RESOURCE_URL for r in request.GET.getlist("resource")):
        raise OAuthToolkitError(
            error=CustomOAuth2Error(
                error="invalid_target",
                description="The requested resource is not supported.",
                state=state,
            ),
            redirect_uri=redirect_uri,
        )

    return scopes, credentials


def validate_query(original_request, user, query: str):
    """
    :raises OAuthToolkitError: When the authorization request is invalid.
    :return: The rebuilt authorize request and its validated credentials, to pass
        to `issue_code` or `deny_url`.
    """

    request = _authorize_request(original_request, user, query)
    _, credentials = _validate(request)
    return request, credentials


def deny_url(request: HttpRequest, credentials: dict) -> str:
    """The client redirect URI carrying an `access_denied` error."""

    error = AccessDeniedError(state=credentials.get("state"))
    return with_iss(request, error.in_uri(credentials["redirect_uri"]))


def issue_code(request: HttpRequest, credentials: dict, endpoint: MCPEndpoint) -> str:
    """
    Returns the client redirect URI with an authorization code bound to the
    endpoint. `request` and `credentials` come from `validate_query`.

    :raises OAuthToolkitError: When the library rejects the request.
    """

    credentials = dict(credentials)
    # `validate_authorization_request` doesn't carry the RFC 8707 `resource`
    # through, so set it like `AuthorizationView.form_valid` does.
    credentials["resource"] = [settings.MCP_RESOURCE_URL]
    # Lets the validator accept the endpoint scope, which clients can't request.
    credentials[CONSENT_CREDENTIAL] = True

    scopes = [MCP_SCOPE, endpoint_scope(endpoint.id)]
    if OFFLINE_ACCESS_SCOPE in request.GET.get("scope", "").split():
        scopes.append(OFFLINE_ACCESS_SCOPE)
    uri, _, _, _ = get_oauthlib_core().create_authorization_response(
        request, scopes=scopes, credentials=credentials, allow=True
    )
    return uri
