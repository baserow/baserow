from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.contrib.whiteboard.api.comments.errors import (
    ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE,
    ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST,
    ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR,
    ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH,
)
from baserow.contrib.whiteboard.api.comments.serializers import (
    CreateWhiteboardCommentSerializer,
    ResolveWhiteboardCommentSerializer,
    UpdateWhiteboardCommentSerializer,
    WhiteboardCommentSerializer,
)
from baserow.contrib.whiteboard.api.errors import ERROR_WHITEBOARD_DOES_NOT_EXIST
from baserow.contrib.whiteboard.comments.exceptions import (
    InvalidWhiteboardCommentMessage,
    WhiteboardCommentDoesNotExist,
    WhiteboardCommentNotAuthor,
    WhiteboardCommentParentMismatch,
)
from baserow.contrib.whiteboard.comments.handler import WhiteboardCommentHandler
from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist

COMMON_ERRORS = {
    WhiteboardDoesNotExist: ERROR_WHITEBOARD_DOES_NOT_EXIST,
    WhiteboardCommentDoesNotExist: ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST,
    WhiteboardCommentNotAuthor: ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR,
    InvalidWhiteboardCommentMessage: ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE,
    WhiteboardCommentParentMismatch: ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH,
}


class WhiteboardCommentsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Whiteboard comments"],
        operation_id="list_whiteboard_comments",
        description=(
            "Lists every comment on the whiteboard, ordered by creation "
            "time, with replies grouped right after their thread root."
        ),
        responses={
            200: WhiteboardCommentSerializer(many=True),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WHITEBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_ERRORS)
    def get(self, request, whiteboard_id):
        comments = WhiteboardCommentHandler().list_comments(
            request.user, int(whiteboard_id)
        )
        return Response(
            WhiteboardCommentSerializer(comments, many=True).data,
            status=HTTP_200_OK,
        )

    @extend_schema(
        tags=["Whiteboard comments"],
        operation_id="create_whiteboard_comment",
        request=CreateWhiteboardCommentSerializer,
        responses={
            200: WhiteboardCommentSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE",
                    "ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH",
                ]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_WHITEBOARD_DOES_NOT_EXIST",
                    "ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(COMMON_ERRORS)
    @validate_body(CreateWhiteboardCommentSerializer)
    def post(self, request, data, whiteboard_id):
        comment = WhiteboardCommentHandler().create_comment(
            user=request.user,
            whiteboard_id=int(whiteboard_id),
            message=data["message"],
            x=data.get("x"),
            y=data.get("y"),
            parent_comment_id=data.get("parent_comment_id"),
        )
        return Response(WhiteboardCommentSerializer(comment).data, status=HTTP_200_OK)


class WhiteboardCommentView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Whiteboard comments"],
        operation_id="update_whiteboard_comment",
        request=UpdateWhiteboardCommentSerializer,
        responses={
            200: WhiteboardCommentSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_WHITEBOARD_COMMENT_MESSAGE",
                ]
            ),
            401: get_error_schema(
                [
                    "ERROR_PERMISSION_DENIED",
                    "ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR",
                ]
            ),
            404: get_error_schema(["ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_ERRORS)
    @validate_body(UpdateWhiteboardCommentSerializer)
    def patch(self, request, data, comment_id):
        handler = WhiteboardCommentHandler()
        comment = handler.get_comment(int(comment_id))
        comment = handler.update_comment(request.user, comment, data["message"])
        return Response(WhiteboardCommentSerializer(comment).data, status=HTTP_200_OK)

    @extend_schema(
        tags=["Whiteboard comments"],
        operation_id="delete_whiteboard_comment",
        responses={
            204: None,
            401: get_error_schema(
                [
                    "ERROR_PERMISSION_DENIED",
                    "ERROR_WHITEBOARD_COMMENT_NOT_AUTHOR",
                ]
            ),
            404: get_error_schema(["ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_ERRORS)
    def delete(self, request, comment_id):
        handler = WhiteboardCommentHandler()
        comment = handler.get_comment(int(comment_id))
        handler.delete_comment(request.user, comment)
        return Response(status=HTTP_204_NO_CONTENT)


class WhiteboardCommentResolveView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Whiteboard comments"],
        operation_id="resolve_whiteboard_comment",
        request=ResolveWhiteboardCommentSerializer,
        responses={
            200: WhiteboardCommentSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WHITEBOARD_COMMENT_PARENT_MISMATCH",
                ]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WHITEBOARD_COMMENT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_ERRORS)
    @validate_body(ResolveWhiteboardCommentSerializer)
    def post(self, request, data, comment_id):
        handler = WhiteboardCommentHandler()
        comment = handler.get_comment(int(comment_id))
        comment = handler.resolve_comment(request.user, comment, data["resolved"])
        return Response(WhiteboardCommentSerializer(comment).data, status=HTTP_200_OK)
