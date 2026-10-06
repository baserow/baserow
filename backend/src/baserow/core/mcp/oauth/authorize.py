from django.http import HttpRequest, QueryDict

from oauth2_provider.oauth2_backends import get_oauthlib_core
from oauthlib.oauth2 import AccessDeniedError

from baserow.core.mcp.models import MCPEndpoint

from .validators import MCP_SCOPE, endpoint_scope

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


def validate_query(original_request, user, query: str):
    """
    :raises OAuthToolkitError: When the authorization request is invalid.
    :return: The requested scopes and the credentials of the request.
    """

    request = _authorize_request(original_request, user, query)
    return get_oauthlib_core().validate_authorization_request(request)


def issue_code(
    original_request, user, query: str, endpoint: MCPEndpoint | None, allow: bool
) -> str:
    """
    Returns the URL the browser must be sent to: the client redirect URI with either
    an authorization code bound to the endpoint, or an `access_denied` error.

    :raises OAuthToolkitError: When the authorization request is invalid.
    """

    request = _authorize_request(original_request, user, query)
    core = get_oauthlib_core()
    _, credentials = core.validate_authorization_request(request)

    if not allow:
        error = AccessDeniedError(state=credentials.get("state"))
        return error.in_uri(credentials["redirect_uri"])

    # `validate_authorization_request` doesn't carry the RFC 8707 `resource` through,
    # so add it like the library's own `AuthorizationView.form_valid` does.
    resources = request.GET.getlist("resource")
    if resources:
        credentials["resource"] = resources

    scopes = [MCP_SCOPE, endpoint_scope(endpoint.id)]
    uri, _, _, _ = core.create_authorization_response(
        request, scopes=scopes, credentials=credentials, allow=True
    )
    return uri
