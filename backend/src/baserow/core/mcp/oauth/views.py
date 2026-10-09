import base64
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views import View

from oauth2_provider import cimd
from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.views import OAuthProtectedResourceMetadataView
from oauthlib.oauth2.rfc6749.errors import InvalidClientIdError

from .authorize import error_redirect_url, is_redirectable, validate_query
from .throttling import MCPOAuthAuthorizeRateThrottle, rate_limited
from .validators import MCP_SCOPE

UNKNOWN_CLIENT_MESSAGE = (
    "This app's sign-in registration is unknown or has expired. Remove the Baserow "
    "server from the app and add it again."
)


def _consent_error_url(request, oauthlib_error) -> str:
    """
    The consent page URL that shows a fatal authorize error (unknown client,
    invalid redirect URI) in the styled error card.
    """

    description = oauthlib_error.description or oauthlib_error.error
    # A registered client that was cleaned up keeps sending its stored client_id,
    # and the app only registers again once it's re-added. CIMD clients are
    # fetched again instead, so it doesn't apply to them.
    if isinstance(oauthlib_error, InvalidClientIdError) and not cimd.is_cimd_client_id(
        request.GET.get("client_id", "")
    ):
        description = UNKNOWN_CLIENT_MESSAGE
    query = urlencode({"error": oauthlib_error.error, "error_description": description})
    frontend_url = settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/mcp-authorize?{query}"


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
            # Fatal errors (unknown client, invalid redirect URI) must never redirect
            # to the client-supplied URI, so Baserow's consent page shows them.
            if not is_redirectable(error):
                return HttpResponseRedirect(
                    _consent_error_url(request, error.oauthlib_error)
                )
            return HttpResponseRedirect(error_redirect_url(request, error))

        # The consent page gets the query as unpadded base64url: the login redirect
        # passes it through encodeURI and the router, which would re-encode a plain
        # query string, but leave base64url characters alone.
        query = request.META.get("QUERY_STRING", "")
        encoded = base64.urlsafe_b64encode(query.encode()).rstrip(b"=").decode()
        frontend_url = settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(f"{frontend_url}/mcp-authorize?request={encoded}")


class MCPProtectedResourceMetadataView(OAuthProtectedResourceMetadataView):
    """
    Lists only `mcp`: `offline_access` is requested from the authorization server
    and has no meaning for the resource itself.
    """

    def get_scopes_supported(self):
        return [MCP_SCOPE]
