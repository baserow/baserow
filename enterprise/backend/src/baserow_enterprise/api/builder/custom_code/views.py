from django.http import HttpResponse

from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.builder.errors import ERROR_BUILDER_DOES_NOT_EXIST
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.service import BuilderService
from baserow_enterprise.api.authentication import (
    AuthenticateFromUserSessionAuthentication,
)
from baserow_enterprise.features import BUILDER_CUSTOM_CODE


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
            404: get_error_schema(["ERROR_BUILDER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST,
        }
    )
    def get(self, request, builder_id, code_type):
        """
        Return the CSS/JS for the given builder
        """

        builder = BuilderService().get_builder(request.user, builder_id)

        if not LicenseHandler.workspace_has_feature(
            BUILDER_CUSTOM_CODE, builder.get_workspace()
        ):
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
    authentication_classes = APIView.authentication_classes + [
        AuthenticateFromUserSessionAuthentication
    ]
