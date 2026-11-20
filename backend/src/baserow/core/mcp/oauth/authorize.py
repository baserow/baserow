from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.http import HttpRequest, QueryDict

from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError
from oauth2_provider.oauth2_backends import _add_iss_to_redirect, get_oauthlib_core
from oauth2_provider.settings import oauth2_settings
from oauthlib.oauth2 import AccessDeniedError, InvalidRequestError
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error, InvalidRedirectURIError

from baserow.core.mcp.models import MCPEndpoint

from .validators import (
    CONSENT_CREDENTIAL,
    MCP_SCOPE,
    OFFLINE_ACCESS_SCOPE,
    endpoint_scope,
    is_allowed_redirect_uri,
    legacy_resource_key,
)

AUTHORIZE_PATH = "/oauth/authorize/"


def requested_legacy_key(request: HttpRequest) -> str | None:
    """
    The endpoint key of the old endpoint URL the client asked to sign in for, or
    None when it asked for `/mcp` or no resource. The request has been validated
    by `validate_query`, so all its resources name the same key.
    """

    for resource in request.GET.getlist("resource"):
        key = legacy_resource_key(resource)
        if key is not None:
            return key
    return None


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


def with_iss(request: HttpRequest, uri: str) -> str:
    """
    Adds the RFC 9207 `iss` parameter to a redirect back to the client with the
    library's own helper, which it uses for successful responses. It replaces an
    `iss` the redirect URI already carries and puts it in the fragment when the
    response is there.
    """

    if not oauth2_settings.COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS:
        return uri
    issuer = oauth2_settings.oauth2_authorization_server_issuer(request)
    return _add_iss_to_redirect(uri, issuer)


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

    # Registration enforces this for DCR clients; a CIMD client's document can
    # list any redirect URI the library accepts, so it's checked for every client.
    if not is_allowed_redirect_uri(redirect_uri):
        raise FatalClientError(
            error=InvalidRedirectURIError(
                description="Redirect URIs must use https or a loopback http address.",
                state=state,
            ),
            redirect_uri=redirect_uri,
        )

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
    # resource is rejected, a missing one is accepted. The old endpoint URL is
    # accepted too, so the consent page can offer only that endpoint's tools.
    resources = request.GET.getlist("resource")
    legacy_keys = {legacy_resource_key(r) for r in resources} - {None}
    if len(legacy_keys) > 1 or any(
        r != settings.MCP_RESOURCE_URL and legacy_resource_key(r) is None
        for r in resources
    ):
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
    error.response_mode = credentials["request"].response_mode
    return with_iss(request, error.in_uri(credentials["redirect_uri"]))


def _params(uri: str) -> list[tuple[str, str]]:
    """The query and fragment parameters, as the response can be in either."""

    parts = urlsplit(uri)
    return parse_qsl(parts.query, keep_blank_values=True) + parse_qsl(
        parts.fragment, keep_blank_values=True
    )


def _added_params(redirect_uri: str, uri: str) -> dict[str, list[str]]:
    """The parameters of `uri` that `redirect_uri` doesn't already carry."""

    added = _params(uri)
    for pair in _params(redirect_uri):
        if pair in added:
            added.remove(pair)
    query = {}
    for name, value in added:
        query.setdefault(name, []).append(value)
    return query


def issue_code(request: HttpRequest, credentials: dict, endpoint: MCPEndpoint) -> str:
    """
    Returns the client redirect URI with an authorization code bound to the
    endpoint. `request` and `credentials` come from `validate_query`.

    :raises OAuthToolkitError: When the library rejects the request, including
        when it answers with an error redirect instead of a code.
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
    # oauthlib re-validates while issuing and returns non-fatal errors as a
    # redirect instead of raising, so check a code was actually issued. Only the
    # parameters it added count: the registered URI may carry its own `error`.
    params = _added_params(credentials["redirect_uri"], uri or "")
    if "code" not in params or "error" in params:
        error = CustomOAuth2Error(
            error=params.get("error", ["server_error"])[0],
            description=params.get("error_description", [None])[0],
            state=credentials.get("state"),
        )
        error.response_mode = credentials["request"].response_mode
        raise OAuthToolkitError(error=error, redirect_uri=credentials["redirect_uri"])
    return uri
