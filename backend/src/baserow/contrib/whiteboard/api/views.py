from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.contrib.whiteboard.api.errors import ERROR_WHITEBOARD_DOES_NOT_EXIST
from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler
from baserow.contrib.whiteboard.operations import (
    ReadWhiteboardOperationType,
    UpdateWhiteboardContentOperationType,
)
from baserow.contrib.whiteboard.ws.signals import whiteboard_content_updated
from baserow.core.handler import CoreHandler

from .serializers import WhiteboardContentSerializer


class WhiteboardView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="whiteboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the persisted Excalidraw scene of the "
                "whiteboard related to the provided id.",
            )
        ],
        tags=["Whiteboard"],
        operation_id="get_whiteboard_content",
        description=(
            "Returns the persisted Excalidraw scene state of the whiteboard "
            "with the provided id, if the user has access to the related "
            "workspace."
        ),
        responses={
            200: WhiteboardContentSerializer,
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WHITEBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WhiteboardDoesNotExist: ERROR_WHITEBOARD_DOES_NOT_EXIST,
        }
    )
    def get(self, request, whiteboard_id):
        whiteboard = WhiteboardHandler().get_whiteboard(int(whiteboard_id))
        CoreHandler().check_permissions(
            request.user,
            ReadWhiteboardOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        return Response({"content": whiteboard.content or {}})

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="whiteboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the persisted Excalidraw scene of the "
                "whiteboard related to the provided id.",
            )
        ],
        tags=["Whiteboard"],
        operation_id="update_whiteboard_content",
        description=(
            "Replaces the persisted Excalidraw scene state of the whiteboard "
            "with the provided id. The frontend typically calls this endpoint "
            "on a debounced auto-save."
        ),
        request=WhiteboardContentSerializer,
        responses={
            200: WhiteboardContentSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WHITEBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WhiteboardDoesNotExist: ERROR_WHITEBOARD_DOES_NOT_EXIST,
        }
    )
    @validate_body(WhiteboardContentSerializer)
    def put(self, request, data, whiteboard_id):
        with transaction.atomic():
            whiteboard = WhiteboardHandler().get_whiteboard(int(whiteboard_id))
            CoreHandler().check_permissions(
                request.user,
                UpdateWhiteboardContentOperationType.type,
                workspace=whiteboard.workspace,
                context=whiteboard,
            )
            whiteboard.content = data["content"] or {}
            whiteboard.save(update_fields=["content"])

        whiteboard_content_updated.send(
            sender=self.__class__,
            whiteboard=whiteboard,
            user=request.user,
        )
        return Response({"content": whiteboard.content})
