import base64
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.views import View

from oauth2_provider import cimd
from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.views import OAuthProtectedResourceMetadataView
from oauthlib.oauth2.rfc6749.errors import InvalidClientIdError

from .authorize import validate_query
from .throttling import MCPOAuthAuthorizeRateThrottle, rate_limited
from .validators import MCP_SCOPE

# The consent page shows its own text for these codes. Re-adding the server
# registers an unknown client again; a rejected CIMD client fails the same way
# every time, so it can't help there.
UNKNOWN_CLIENT_ERROR = "unknown_client"
CLIENT_REJECTED_ERROR = "client_rejected"


def _consent_error_url(request, oauthlib_error) -> str:
    """
    The consent page URL that shows an authorize error. Only an error code is
    sent, which the page maps to its own text, so the URL can't put arbitrary text
    on a Baserow page.
    """

    error = oauthlib_error.error
    if isinstance(oauthlib_error, InvalidClientIdError):
        # A registered client that was cleaned up keeps sending its stored
        # client_id, and the app only registers again once it's re-added. A CIMD
        # client is fetched every time, so it was refused: its host isn't allowed,
        # CIMD is off, or its document is invalid. The reason is in the server log.
        if cimd.is_cimd_client_id(request.GET.get("client_id", "")):
            error = CLIENT_REJECTED_ERROR
        else:
            error = UNKNOWN_CLIENT_ERROR
    frontend_url = settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/mcp-authorize?{urlencode({'error': error})}"


class MCPAuthorizeRedirectView(View):
    """
    Validates the authorization request and sends the browser to the Baserow consent
    page, which handles login (JWT) and posts back to the consent API.
    """

    def get(self, request):
        limited = rate_limited(MCPOAuthAuthorizeRateThrottle(), request, self)
        if limited is not None:
            return limited

        try:
            validate_query(request, request.user, request.META.get("QUERY_STRING", ""))
        except OAuthToolkitError as error:
            # Never redirected to the client: anyone can register any https redirect
            # URI, and nobody has signed in or clicked anything yet, so that would
            # be an open redirect (RFC 9700 4.11.1). Baserow's consent page shows it.
            return HttpResponseRedirect(
                _consent_error_url(request, error.oauthlib_error)
            )

        # The consent page gets the query as unpadded base64url in its path. SSO
        # sign-in only keeps the path of the page to return to, and the login
        # redirect passes it through encodeURI and the router, which leave base64url
        # characters alone.
        query = request.META.get("QUERY_STRING", "")
        encoded = base64.urlsafe_b64encode(query.encode()).rstrip(b"=").decode()
        frontend_url = settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(f"{frontend_url}/mcp-authorize/{encoded}")


class MCPProtectedResourceMetadataView(OAuthProtectedResourceMetadataView):
    """
    Lists only `mcp`: `offline_access` is requested from the authorization server
    and has no meaning for the resource itself.
    """

    def get_scopes_supported(self):
        return [MCP_SCOPE]


def openai_apps_challenge(request):
    """
    Returns the token OpenAI fetches to verify the domain of the MCP server, or a
    404 when it isn't set.
    """

    token = settings.BASEROW_MCP_OPENAI_APPS_CHALLENGE
    if not token:
        raise Http404()
    return HttpResponse(token, content_type="text/plain")
