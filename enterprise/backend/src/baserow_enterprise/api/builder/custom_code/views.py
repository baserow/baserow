from urllib.parse import urlsplit

from django.conf import settings
from django.http import Http404, HttpResponse

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.builder.preview.authentication import (
    BuilderPreviewAuthentication,
)
from baserow.contrib.builder.service import BuilderService
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow_enterprise.api.builder.custom_code.serializers import CustomHtmlSerializer
from baserow_enterprise.features import BUILDER_CUSTOM_CODE
from baserow_premium.license.handler import LicenseHandler


def _can_serve_custom_code(builder):
    return not builder.untrusted_content and LicenseHandler.workspace_has_feature(
        BUILDER_CUSTOM_CODE, builder.get_workspace()
    )


def _http_hostname(url):
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    if parsed.scheme in ("http", "https"):
        return parsed.hostname

    return None


class PublicCustomCodeView(APIView):
    """
    This view is meant to return custom CSS and JS file for a builder application.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The builder Id we want the custom code for.",
            ),
            OpenApiParameter(
                name="type",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Type of code to return: 'css' or 'js'",
                enum=["css", "js"],
                default="css",
            ),
        ],
        tags=["Builder public"],
        operation_id="get_public_builder_custom_code",
        description=("Returns the css/js for the given builder."),
        responses={
            200: str,
            404: get_error_schema(
                [
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, builder_id, code_type):
        """
        Return the CSS/JS for the given builder
        """

        builder = BuilderService().get_builder(request.user, builder_id)

        if not _can_serve_custom_code(builder):
            return HttpResponse("Not found", status=404)

        # Get the appropriate content and content-type
        if code_type == "css":
            content = builder.custom_code.css
            content_type = "text/css; charset=utf-8"
        else:  # js
            content = builder.custom_code.js
            content_type = "application/javascript; charset=utf-8"
        return HttpResponse(content, content_type=content_type)


# This version is for authorized users only while in preview
class CustomCodeView(PublicCustomCodeView):
    authentication_classes = (BuilderPreviewAuthentication,)


class PublicCustomHtmlView(APIView):
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)

    def can_render_builder(self, builder):
        return builder.is_published

    @extend_schema(
        tags=["Builder public"],
        operation_id="get_public_builder_custom_html",
        description="Returns the custom head HTML for a published builder.",
        responses={
            200: CustomHtmlSerializer,
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST})
    def get(self, request, builder_id):
        builder = BuilderService().get_builder(request.user, builder_id)
        if not self.can_render_builder(builder) or not _can_serve_custom_code(builder):
            raise Http404

        return Response(
            {"html": builder.custom_code.html}, headers={"Cache-Control": "no-store"}
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Builder preview"],
        operation_id="get_preview_builder_custom_html",
        description="Returns the custom head HTML for an authorized builder preview.",
    )
)
class PreviewCustomHtmlView(PublicCustomHtmlView):
    authentication_classes = (BuilderPreviewAuthentication,)

    def can_render_builder(self, builder):
        preview_hostname = _http_hostname(settings.BUILDER_PREVIEW_URL)
        editor_hostname = _http_hostname(settings.PUBLIC_WEB_FRONTEND_URL)
        # The editor and preview can share browser cookies across ports.
        return (
            not builder.is_published
            and preview_hostname is not None
            and editor_hostname is not None
            and preview_hostname != editor_hostname
        )
