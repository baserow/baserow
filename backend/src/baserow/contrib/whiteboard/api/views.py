from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler
from baserow.core.handler import CoreHandler
from baserow.core.operations import (
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
)
from baserow.ws.registries import page_registry

from .errors import ERROR_WHITEBOARD_DOES_NOT_EXIST
from .serializers import BroadcastChangesSerializer, WhiteboardContentSerializer


class WhiteboardView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="whiteboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the whiteboard to get the content for.",
            )
        ],
        tags=["Whiteboard"],
        operation_id="get_whiteboard_content",
        description="Returns the tldraw content of the specified whiteboard.",
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
        whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)

        CoreHandler().check_permissions(
            request.user,
            ReadApplicationOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )

        return Response({"content": whiteboard.content})

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="whiteboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the whiteboard to save the content for.",
            )
        ],
        tags=["Whiteboard"],
        operation_id="save_whiteboard_content",
        description="Saves the tldraw snapshot content of the specified whiteboard.",
        request=WhiteboardContentSerializer,
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
    def put(self, request, whiteboard_id):
        whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)

        CoreHandler().check_permissions(
            request.user,
            UpdateApplicationOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )

        serializer = WhiteboardContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        whiteboard.content = serializer.validated_data["content"]
        whiteboard.save(update_fields=["content"])

        page_type = page_registry.get("whiteboard")
        page_type.broadcast(
            {
                "type": "whiteboard_content_updated",
                "whiteboard_id": whiteboard_id,
            },
            whiteboard_id=whiteboard_id,
            ignore_web_socket_id=getattr(request.user, "web_socket_id", None),
        )

        return Response({"content": whiteboard.content})


class BroadcastChangesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="whiteboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the whiteboard to broadcast changes for.",
            )
        ],
        tags=["Whiteboard"],
        operation_id="broadcast_whiteboard_changes",
        description=(
            "Broadcasts tldraw shape changes to all other connected clients "
            "via WebSocket. Does not persist to the database."
        ),
        request=BroadcastChangesSerializer,
        responses={
            204: None,
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WHITEBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WhiteboardDoesNotExist: ERROR_WHITEBOARD_DOES_NOT_EXIST,
        }
    )
    def post(self, request, whiteboard_id):
        whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)

        CoreHandler().check_permissions(
            request.user,
            UpdateApplicationOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )

        serializer = BroadcastChangesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        page_type = page_registry.get("whiteboard")
        page_type.broadcast(
            {
                "type": "whiteboard_changes",
                "whiteboard_id": whiteboard_id,
                "changes": serializer.validated_data["changes"],
            },
            whiteboard_id=whiteboard_id,
            ignore_web_socket_id=getattr(request.user, "web_socket_id", None),
        )

        return Response(status=204)
