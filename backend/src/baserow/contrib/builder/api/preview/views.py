"""API endpoints used to open and authenticate an Application Builder preview.

The preview authentication process works as follows:

1. An editor clicks the preview button. The frontend asks
   :class:`BuilderPreviewGrantView` for a preview URL. This request uses the
   editor's normal login, so Baserow can first check that they are allowed to
   see the builder.
2. The URL contains a short-lived, signed grant which names the one draft
   builder that may be viewed. Frontend middleware sends the browser to
   :class:`BuilderPreviewExchangeView` to consume it.
3. The exchange sets the backend-origin preview cookie used by browser API
   calls, stores a random one-time SSR handoff, and redirects to the preview
   URL with only that opaque handoff code.
4. Preview middleware posts the handoff server-to-server to
   :class:`BuilderPreviewHandoffView`, writes the returned session into an
   HttpOnly preview-origin cookie, and redirects to a URL without credentials.
5. During SSR, Nuxt forwards only that companion credential under the backend
   cookie name. ``BuilderPreviewAuthentication`` represents the visitor as a
   restricted preview actor which can render only the builder named in the
   original grant.

The pass and cookie expire after ``BUILDER_PREVIEW_GRANT_TTL``. The first exchange
atomically creates a short-lived global-cache entry, so later exchanges of the
same pass are rejected.
"""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.applications.serializers import (
    PublicPolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.contrib.builder.api.preview.serializers import (
    BuilderPreviewGrantRequestSerializer,
    BuilderPreviewGrantResponseSerializer,
    BuilderPreviewHandoffRequestSerializer,
    BuilderPreviewHandoffResponseSerializer,
)
from baserow.contrib.builder.errors import ERROR_BUILDER_DOES_NOT_EXIST
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.preview import (
    BUILDER_PREVIEW_HANDOFF_QUERY_PARAM,
    BuilderPreviewGrantHandler,
    BuilderPreviewGrantInvalid,
    get_builder_preview_cookie_name,
)
from baserow.contrib.builder.preview.authentication import (
    BuilderPreviewAuthentication,
)
from baserow.contrib.builder.service import BuilderService
from baserow.core.exceptions import ApplicationDoesNotExist


class ForcedPublicPolymorphicApplicationResponseSerializer(
    PublicPolymorphicApplicationResponseSerializer
):
    """Serialize the draft as the public-facing ``builder`` application type."""

    forced_type = "builder"


class BuilderPreviewGrantView(APIView):
    """Start the preview process for a logged-in editor.

    This is the only step that uses the editor's normal account login. It makes
    sure the editor may read the requested builder before issuing a temporary
    preview pass. The returned URL is then opened by the browser to continue
    with :class:`BuilderPreviewExchangeView`.
    """

    @extend_schema(
        tags=["Builder preview"],
        operation_id="create_builder_preview_grant",
        request=BuilderPreviewGrantRequestSerializer,
        responses={
            200: BuilderPreviewGrantResponseSerializer,
            404: get_error_schema(
                ["ERROR_BUILDER_DOES_NOT_EXIST", "ERROR_APPLICATION_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST,
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    @validate_body(BuilderPreviewGrantRequestSerializer)
    def post(self, request, data, builder_id: int):
        """Return a preview URL containing a short-lived signed token.

        ``BuilderService.get_builder`` checks the editor's access. The signed
        token identifies that builder and the editor who requested the preview,
        while ``path`` preserves the page the editor wanted to preview. No
        preview cookie is created at this stage.
        """

        builder = BuilderService().get_builder(request.user, builder_id)
        token = BuilderPreviewGrantHandler().create_grant(builder, request.user)
        url = BuilderPreviewGrantHandler().get_preview_url(
            builder.id, data["path"], token
        )
        return Response({"url": url})


class BuilderPreviewCurrentView(APIView):
    """Tell the preview frontend which draft builder its cookie allows.

    This endpoint is called after the token exchange. Although it allows an
    unauthenticated HTTP request to reach the view, ``BuilderPreviewAuthentication``
    reads the protected preview cookie first. A valid cookie becomes a
    restricted preview actor containing the permitted builder's ID.
    """

    permission_classes = (AllowAny,)
    authentication_classes = (BuilderPreviewAuthentication,)

    @extend_schema(
        tags=["Builder preview"],
        operation_id="get_current_builder_preview",
        description=(
            "Returns the public serialized draft builder related to the current "
            "preview session cookie."
        ),
        responses={
            200: ForcedPublicPolymorphicApplicationResponseSerializer,
            401: get_error_schema(["ERROR_BUILDER_PREVIEW_SESSION_INVALID"]),
            404: get_error_schema(
                ["ERROR_BUILDER_DOES_NOT_EXIST", "ERROR_APPLICATION_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST,
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request):
        """Return the public-shaped data for the permitted draft builder.

        The builder ID comes only from the authenticated preview actor, not
        from the URL or other browser input. This prevents one preview pass from
        being used to request a different draft builder.
        """

        builder_id = getattr(request.user, "builder_id", None)
        if builder_id is None:
            raise BuilderDoesNotExist

        builder = BuilderService().get_builder(request.user, builder_id)
        return Response(
            ForcedPublicPolymorphicApplicationResponseSerializer(builder).data
        )


class BuilderPreviewExchangeView(APIView):
    """Turn the token in a preview URL into a browser cookie and SSR handoff.

    The browser reaches this endpoint before loading the clean preview page.
    No existing login is required because the signed, unexpired token is the
    proof of access. After validation, a separate preview-session token is placed
    in an HttpOnly backend-origin cookie and behind a random one-time handoff.
    The browser is redirected with the opaque handoff, never the session itself.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The one-time builder preview token to exchange.",
            ),
            OpenApiParameter(
                name="redirect",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.URI,
                description="The clean frontend preview URL to redirect to.",
            ),
        ],
        tags=["Builder preview"],
        operation_id="exchange_builder_preview_grant",
        responses={302: None, 404: None},
    )
    def get(self, request, token: str):
        """Consume the preview pass, set a session cookie, and redirect the browser.

        Invalid or expired tokens return ``404`` without creating a cookie. The
        requested redirect is accepted only when it points to the configured
        preview website; otherwise a safe preview root URL is used. Cookie
        security flags are selected according to whether the backend and
        preview website are considered the same browser site.
        """

        try:
            actor, session_token = BuilderPreviewGrantHandler().exchange_token(token)
        except BuilderPreviewGrantInvalid:
            return Response(status=404)

        redirect_to = request.GET.get("redirect")
        if not self._is_allowed_redirect(redirect_to):
            redirect_to = (
                BuilderPreviewGrantHandler()
                .get_preview_url(actor.builder_id, "/", "")
                .split("?", 1)[0]
            )

        preview_url = urlparse(settings.BUILDER_PREVIEW_URL)
        backend_url = urlparse(settings.PUBLIC_BACKEND_URL)
        same_site = (
            "Lax"
            if self._is_same_site(preview_url.hostname, backend_url.hostname)
            else "None"
        )
        secure = backend_url.scheme == "https" or same_site == "None"
        handoff_code = BuilderPreviewGrantHandler().create_handoff(session_token)
        redirect_to = self._add_handoff_to_redirect(redirect_to, handoff_code)
        response = HttpResponseRedirect(redirect_to)
        response.set_cookie(
            get_builder_preview_cookie_name(),
            session_token,
            max_age=int(settings.BUILDER_PREVIEW_GRANT_TTL.total_seconds()),
            httponly=True,
            secure=secure,
            samesite=same_site,
            path="/api/",
        )
        return response

    @staticmethod
    def _add_handoff_to_redirect(redirect_to: str, handoff_code: str) -> str:
        """Add the opaque handoff while preserving the redirect query and fragment."""

        parsed = urlparse(redirect_to)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != BUILDER_PREVIEW_HANDOFF_QUERY_PARAM
        ]
        query.append((BUILDER_PREVIEW_HANDOFF_QUERY_PARAM, handoff_code))
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _is_allowed_redirect(self, redirect_to):
        """Check that the post-exchange redirect stays on the preview website.

        Without this check, an attacker could build a Baserow exchange link that
        forwards a visitor to an unrelated website after the cookie is created.
        The URL must use the configured preview host and, when configured, HTTPS.
        """

        if not redirect_to:
            return False

        parsed = urlparse(settings.BUILDER_PREVIEW_URL)
        allowed_host = parsed.netloc
        return url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={allowed_host},
            require_https=parsed.scheme == "https",
        )

    def _is_same_site(self, preview_hostname, backend_hostname):
        """Decide whether browser cookie rules see both hosts as one site.

        Equal hosts are the same site. Local development treats ``localhost``
        and ``127.0.0.1`` as equivalent; otherwise the comparison uses the
        registrable domain, so sibling hosts such as ``api.example.com`` and
        ``preview.example.com`` are treated as the same site.
        """

        if not preview_hostname or not backend_hostname:
            return False
        if preview_hostname == backend_hostname:
            return True
        if preview_hostname in {"localhost", "127.0.0.1"}:
            return backend_hostname in {"localhost", "127.0.0.1"}
        if backend_hostname in {"localhost", "127.0.0.1"}:
            return False

        return self._registrable_domain(preview_hostname) == self._registrable_domain(
            backend_hostname
        )

    def _registrable_domain(self, hostname):
        """Return the last two hostname parts used by the same-site check."""

        parts = hostname.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


class BuilderPreviewHandoffView(APIView):
    """Let the preview Nuxt server consume an opaque one-time handoff code."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        tags=["Builder preview"],
        operation_id="exchange_builder_preview_handoff",
        request=BuilderPreviewHandoffRequestSerializer,
        responses={
            200: BuilderPreviewHandoffResponseSerializer,
            404: None,
        },
    )
    @validate_body(BuilderPreviewHandoffRequestSerializer)
    def post(self, request, data):
        try:
            preview_session, expires_in = BuilderPreviewGrantHandler().exchange_handoff(
                data[BUILDER_PREVIEW_HANDOFF_QUERY_PARAM]
            )
        except BuilderPreviewGrantInvalid:
            response = Response(status=404)
        else:
            response = Response(
                {
                    "preview_session": preview_session,
                    "expires_in": expires_in,
                }
            )
        return response
