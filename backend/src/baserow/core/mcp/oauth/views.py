import base64

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.views import View

from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.views import OAuthProtectedResourceMetadataView

from .authorize import error_redirect_url, is_redirectable, validate_query
from .validators import MCP_SCOPE


class MCPAuthorizeRedirectView(View):
    """
    Validates the authorization request and sends the browser to the Baserow consent
    page, which handles login (JWT) and posts back to the consent API.
    """

    def get(self, request):
        try:
            validate_query(request, request.user, request.META.get("QUERY_STRING", ""))
        except OAuthToolkitError as error:
            # Fatal errors (unknown client, invalid redirect URI) must never redirect
            # to the client-supplied URI, so they are shown instead.
            if not is_redirectable(error):
                oauthlib_error = error.oauthlib_error
                return HttpResponseBadRequest(
                    oauthlib_error.description or oauthlib_error.error
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
