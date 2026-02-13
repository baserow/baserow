from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.database.api.rows.errors import ERROR_ROW_DOES_NOT_EXIST
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow_premium.api.row_comments.errors import (
    ERROR_INVALID_COMMENT_MENTION,
    ERROR_ROW_COMMENT_DOES_NOT_EXIST,
    ERROR_USER_NOT_COMMENT_AUTHOR,
)
from baserow_premium.row_comments.actions import (
    CreateRowCommentActionType,
    DeleteRowCommentActionType,
    UpdateRowCommentActionType,
)
from baserow_premium.row_comments.exceptions import (
    InvalidRowCommentMentionException,
    RowCommentDoesNotExist,
    UserNotRowCommentAuthorException,
)
from baserow_premium.row_comments.handler import RowCommentHandler

from .serializers import (
    RowCommentCreateSerializer,
    RowCommentSerializer,
    RowCommentsNotificationModeSerializer,
)


class RowCommentsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table the row is in.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The row to get row comments for.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines how many rows should be returned.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Can only be used in combination with the `limit` "
                "parameter and defines from which offset the rows should "
                "be returned.",
            ),
            OpenApiParameter(
                name="page",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines which page of rows should be returned. Either "
                "the `page` or `limit` can be provided, not both.",
            ),
            OpenApiParameter(
                name="size",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Can only be used in combination with the `page` parameter "
                "and defines how many rows should be returned.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="get_row_comments",
        description=(
            "Returns all row comments for the specified table and row."
            "\n\nThis is a **premium** feature."
        ),
        responses={
            200: get_example_pagination_serializer_class(RowCommentSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_TABLE_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, table_id, row_id):
        comments = RowCommentHandler.get_comments(
            request.user, table_id, row_id, include_trash=True
        )

        if LimitOffsetPagination.limit_query_param in request.GET:
            paginator = LimitOffsetPagination()
            paginator.max_limit = settings.ROW_COMMENT_PAGE_SIZE_LIMIT
        else:
            paginator = PageNumberPagination(
                limit_page_size=settings.ROW_COMMENT_PAGE_SIZE_LIMIT
            )

        page = paginator.paginate_queryset(comments, request, self)
        context = {"user": request.user}
        serializer = RowCommentSerializer(page, many=True, context=context)

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table to find the row to comment on in.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The row to create a comment for.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="create_row_comment",
        description="Creates a comment on the specified row.\n\nThis is a **premium** feature.",
        request=RowCommentCreateSerializer,
        responses={
            200: RowCommentSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_INVALID_COMMENT_MENTION"]
            ),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            InvalidRowCommentMentionException: ERROR_INVALID_COMMENT_MENTION,
        }
    )
    @validate_body(RowCommentCreateSerializer)
    @transaction.atomic
    def post(self, request, table_id, row_id, data):
        new_row_comment = action_type_registry.get(CreateRowCommentActionType.type).do(
            request.user, table_id, row_id, data["message"]
        )
        context = {"user": request.user}
        return Response(RowCommentSerializer(new_row_comment, context=context).data)


class RowCommentView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table the row is in.",
            ),
            OpenApiParameter(
                name="comment_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The row comment to update.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="update_row_comment",
        description="Update a row comment.\n\nThis is a **premium** feature.",
        responses={
            200: RowCommentSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_NOT_COMMENT_AUTHOR",
                    "ERROR_INVALID_COMMENT_MENTION",
                    "ERROR_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_COMMENT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowCommentDoesNotExist: ERROR_ROW_COMMENT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserNotRowCommentAuthorException: ERROR_USER_NOT_COMMENT_AUTHOR,
            InvalidRowCommentMentionException: ERROR_INVALID_COMMENT_MENTION,
        }
    )
    @validate_body(RowCommentCreateSerializer)
    @transaction.atomic
    def patch(self, request, table_id, comment_id, data):
        comment = data.get("message", data.get("comment", None))
        updated_row_comment = action_type_registry.get(
            UpdateRowCommentActionType.type
        ).do(request.user, table_id, comment_id, comment)
        context = {"user": request.user}
        return Response(RowCommentSerializer(updated_row_comment, context=context).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table the row is in.",
            ),
            OpenApiParameter(
                name="comment_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The row comment to delete.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="delete_row_comment",
        description="Delete a row comment.\n\nThis is a **premium** feature.",
        responses={
            200: RowCommentSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_NOT_COMMENT_AUTHOR"]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_COMMENT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowCommentDoesNotExist: ERROR_ROW_COMMENT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserNotRowCommentAuthorException: ERROR_USER_NOT_COMMENT_AUTHOR,
        }
    )
    @transaction.atomic
    def delete(self, request, table_id, comment_id):
        trashed_comment = action_type_registry.get(DeleteRowCommentActionType.type).do(
            request.user, table_id, comment_id
        )
        context = {"user": request.user}
        return Response(RowCommentSerializer(trashed_comment, context=context).data)


class RowCommentsNotificationModeView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table id where the row is in.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The row on which to manage the comment subscription.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="update_row_comment_notification_mode",
        description=(
            "Updates the user's notification preferences for comments made on a specified table row."
            "\n\nThis is a **premium** feature."
        ),
        request=RowCommentsNotificationModeSerializer,
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_TABLE_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(RowCommentsNotificationModeSerializer, return_validated=True)
    @transaction.atomic
    def put(self, request, table_id, row_id, data):
        notification_mode = data["mode"]
        RowCommentHandler.update_row_comments_notification_mode(
            request.user, table_id, row_id, notification_mode
        )
        return Response(status=204)
