from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.admin.views import AdminListingView
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.pagination import PageNumberPaginationWithApproximateCount
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.admin.views.handler import ViewsAdminHandler
from baserow.contrib.database.api.views.errors import (
    ERROR_CANNOT_SHARE_VIEW_TYPE,
    ERROR_VIEW_DOES_NOT_EXIST,
)
from baserow.contrib.database.views.exceptions import (
    CannotShareViewTypeError,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View

from .serializers import AdminViewSerializer, AdminViewUpdateSerializer


class AdminViewsView(AdminListingView):
    serializer_class = AdminViewSerializer
    pagination_class = PageNumberPaginationWithApproximateCount
    search_fields = [
        "id",
        "name",
        "slug",
        "table__id",
        "table__name",
        "table__database__id",
        "table__database__name",
        "table__database__workspace__id",
        "table__database__workspace__name",
        "owned_by__id",
        "owned_by__username",
    ]
    sort_field_mapping = {
        "id": "id",
        "name": "name",
        "type": "content_type__model",
        "database_name": "table__database__name",
        "workspace_name": "table__database__workspace__name",
        "public": "public",
        "owned_by_username": "owned_by__username",
        "created_on": "created_on",
    }
    default_order_by = "-id"

    def get_queryset(self, request):
        queryset = View.objects.select_related(
            "table__database__workspace", "owned_by", "content_type"
        ).filter(
            table__trashed=False,
            table__database__trashed=False,
            table__database__workspace__isnull=False,
            table__database__workspace__trashed=False,
            table__database__workspace__template__isnull=True,
        )

        only_public = request.GET.get("only_public", "false").lower() in ("true", "1")
        if only_public:
            queryset = queryset.filter(public=True)

        return queryset

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_database_views",
        description="Returns all database views in the instance with information about "
        "the table, database and workspace they belong to, if the requesting user is "
        "staff. This can for example be used to find and intervene with publicly "
        "shared views that are being abused.",
        **AdminListingView.get_extend_schema_parameters(
            "views",
            serializer_class,
            search_fields,
            sort_field_mapping,
            extra_parameters=[
                OpenApiParameter(
                    name="only_public",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.BOOL,
                    description="If set to `true`, only publicly shared views are "
                    "returned.",
                ),
            ],
        ),
    )
    def get(self, request):
        return super().get(request)


class AdminViewView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        request=AdminViewUpdateSerializer,
        operation_id="admin_update_database_view",
        description="Updates whether the specified view is publicly shared, if the "
        "requesting user is staff. This works even if the requesting user is not a "
        "member of the workspace the view belongs to, and can for example be used "
        "to unshare a publicly shared view that's being abused.",
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the view to update.",
            ),
        ],
        responses={
            200: AdminViewSerializer,
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_CANNOT_SHARE_VIEW_TYPE"]
            ),
            401: None,
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(AdminViewUpdateSerializer)
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CannotShareViewTypeError: ERROR_CANNOT_SHARE_VIEW_TYPE,
        }
    )
    @transaction.atomic
    def patch(self, request, view_id, data):
        view = ViewHandler().get_view(int(view_id))
        view = ViewsAdminHandler().update_view_public(
            request.user, view, data["public"]
        )

        return Response(AdminViewSerializer(view).data)


class AdminViewRotateSlugView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_rotate_database_view_slug",
        description="Rotates the slug of the specified view, permanently "
        "invalidating the current public URL, if the requesting user is staff. "
        "This works even if the requesting user is not a member of the workspace "
        "the view belongs to.",
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the view whose slug must be rotated.",
            ),
        ],
        responses={
            200: AdminViewSerializer,
            400: get_error_schema(["ERROR_CANNOT_SHARE_VIEW_TYPE"]),
            401: None,
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CannotShareViewTypeError: ERROR_CANNOT_SHARE_VIEW_TYPE,
        }
    )
    @transaction.atomic
    def post(self, request, view_id):
        view = ViewHandler().get_view(int(view_id))
        view = ViewsAdminHandler().rotate_view_slug(request.user, view)

        return Response(AdminViewSerializer(view).data)
