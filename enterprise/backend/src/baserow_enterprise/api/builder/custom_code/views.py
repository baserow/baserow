from django.conf import settings
from django.http import Http404, HttpResponse

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions
from baserow.api.openapi import AutoSchema
from baserow.api.schemas import get_error_schema
from baserow.contrib.builder.preview.authentication import (
    BuilderPreviewAuthentication,
)
from baserow.contrib.builder.service import BuilderService
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow_enterprise.features import BUILDER_CUSTOM_CODE
from baserow_premium.license.handler import LicenseHandler


class CustomCodeSchema(AutoSchema):
    def get_response_serializers(self):
        return {
            200: self.view.serializer_class,
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        }

    def get_operation_id(self):
        return self.view.operation_id


class PublicCustomCodeView(APIView):
    """
    Returns custom CSS, JS, or head HTML for a builder application.
    """

    permission_classes = (AllowAny,)
    serializer_class = OpenApiTypes.STR
    operation_id = "get_public_builder_custom_code"
    schema = CustomCodeSchema()

    def can_render_html(self, builder):
        return builder.is_published

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
                description="Type of custom code to return.",
                enum=["css", "js", "html"],
                default="css",
            ),
        ],
        tags=["Builder public"],
        description="Returns the custom code for the given builder.",
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, builder_id, code_type):
        """
        Return custom code for the given builder.
        """

        builder = BuilderService().get_builder(request.user, builder_id)

        if builder.untrusted_content or not LicenseHandler.workspace_has_feature(
            BUILDER_CUSTOM_CODE, builder.get_workspace()
        ):
            if code_type == "html":
                raise Http404
            return HttpResponse("Not found", status=404)

        if code_type == "html":
            if not self.can_render_html(builder):
                raise Http404
            return Response(
                {"html": builder.custom_code.html},
                headers={"Cache-Control": "no-store"},
            )

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

    def can_render_html(self, builder):
        # Editor and preview cookies share a hostname even across different ports.
        return (
            not builder.is_published
            and settings.BUILDER_PREVIEW_HOSTNAME is not None
            and settings.PUBLIC_WEB_FRONTEND_HOSTNAME is not None
            and settings.BUILDER_PREVIEW_HOSTNAME
            != settings.PUBLIC_WEB_FRONTEND_HOSTNAME
        )
