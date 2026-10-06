from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.views import View

from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError
from oauth2_provider.oauth2_backends import get_oauthlib_core


class MCPAuthorizeRedirectView(View):
    """
    Validates the authorization request and sends the browser to the Baserow consent
    page, which handles login (JWT) and posts back to the consent API.
    """

    def get(self, request):
        try:
            get_oauthlib_core().validate_authorization_request(request)
        except OAuthToolkitError as error:
            oauthlib_error = error.oauthlib_error
            # Fatal errors (unknown client, invalid redirect URI) must never redirect
            # to the client-supplied URI, so they are shown instead.
            if isinstance(error, FatalClientError) or not oauthlib_error.redirect_uri:
                return HttpResponseBadRequest(
                    oauthlib_error.description or oauthlib_error.error
                )
            return HttpResponseRedirect(
                oauthlib_error.in_uri(oauthlib_error.redirect_uri)
            )

        query = request.META.get("QUERY_STRING", "")
        return HttpResponseRedirect(
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/mcp/authorize?{query}"
        )
