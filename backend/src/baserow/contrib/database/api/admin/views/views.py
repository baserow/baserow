from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.admin.views import AdminListingView
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.pagination import PageNumberPaginationWithApproximateCount
from baserow.api.schemas import get_error_schema
from baserow.config.settings.utils import str_to_bool
from baserow.contrib.database.admin.views.actions import (
    RotateViewSlugAdminActionType,
    UpdateViewPublicAdminActionType,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_CANNOT_SHARE_VIEW_TYPE,
    ERROR_VIEW_DOES_NOT_EXIST,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.exceptions import (
    CannotShareViewTypeError,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.action.registries import action_type_registry
from baserow.core.db import parse_int_field_value
from baserow.core.models import Application, Template

from .serializers import AdminViewSerializer, AdminViewUpdateSerializer

User = get_user_model()


class AdminViewsView(AdminListingView):
    serializer_class = AdminViewSerializer
    pagination_class = PageNumberPaginationWithApproximateCount
    # Emptied so the generated schema does not describe a search this endpoint no
    # longer does. What it matches is documented on the `search` parameter instead.
    search_fields = []
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
        # Joining the database, workspace and template tables in lets Postgres start
        # from `core_workspace` and walk every workspace in the instance down to its
        # views, which is far more work than looking up the parents of the views that
        # match. Keeping the parent checks in a subquery and fetching the rows to
        # display separately leaves `database_view` as the only table the outer query
        # can be driven from.
        parent_is_visible = Exists(
            Application.objects.filter(
                id=OuterRef("table__database_id"),
                trashed=False,
                workspace_id__isnull=False,
                workspace__trashed=False,
            ).filter(
                ~Exists(Template.objects.filter(workspace_id=OuterRef("workspace_id")))
            )
        )

        queryset = (
            View.objects.filter(trashed=False, table__trashed=False)
            .filter(parent_is_visible)
            .prefetch_related("table__database__workspace", "owned_by")
        )

        if str_to_bool(str(request.GET.get("only_public"))):
            queryset = queryset.filter(public=True)

        return queryset

    def apply_filters(self, query_params, queryset):
        queryset = super().apply_filters(query_params, queryset)

        workspace_id = parse_int_field_value(query_params.get("workspace_id"))
        if workspace_id is None:
            return queryset

        # Resolved through the applications of the workspace so that the outer query
        # only has to match `database_table.database_id`. Following the relationship
        # instead joins in the multi table inheritance parent of `Database`, which
        # this endpoint has no other reason to touch.
        return queryset.filter(
            table__database_id__in=Application.objects.filter(
                workspace_id=workspace_id
            ).values("id")
        )

    def apply_search(self, search, queryset):
        if not search:
            return queryset

        # Every branch is an exact match on an indexed column of `database_view`,
        # which lets Postgres combine them into one bitmap of seeks. A single branch
        # it cannot answer from an index, or one reading another table, would make it
        # scan for all of them instead.
        q = Q(slug=search) | Q(
            owned_by_id__in=User.objects.filter(username=search).values("id")
        )

        value = parse_int_field_value(search)
        if value is not None:
            q |= (
                Q(id=value)
                | Q(table_id=value)
                | Q(owned_by_id=value)
                | Q(table_id__in=Table.objects.filter(database_id=value).values("id"))
                | Q(
                    table_id__in=Table.objects.filter(
                        database_id__in=Application.objects.filter(
                            workspace_id=value
                        ).values("id")
                    ).values("id")
                )
            )

        return queryset.filter(q)

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
                    name="search",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.STR,
                    description="If provided, only views matching it exactly by "
                    "slug, by the email address of their owner, or by the id of the "
                    "view, its table, its database, its workspace or its owner are "
                    "returned. Names are not searched.",
                ),
                OpenApiParameter(
                    name="only_public",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.BOOL,
                    description="If set to `true`, only publicly shared views are "
                    "returned.",
                ),
                OpenApiParameter(
                    name="workspace_id",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.INT,
                    description="If provided, only views in the workspace with this "
                    "id are returned.",
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
        view = action_type_registry.get_by_type(UpdateViewPublicAdminActionType).do(
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
        view = action_type_registry.get_by_type(RotateViewSlugAdminActionType).do(
            request.user, view
        )

        return Response(AdminViewSerializer(view).data)
