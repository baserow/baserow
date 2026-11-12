from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_INVALID_SORT_ATTRIBUTE,
    ERROR_INVALID_SORT_DIRECTION,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.exceptions import (
    InvalidSortAttributeException,
    InvalidSortDirectionException,
)
from baserow.api.identities.errors import (
    ERROR_IDENTITY_DOES_NOT_EXIST,
    ERROR_IDENTITY_ROLE_DOES_NOT_EXIST,
)
from baserow.api.identities.serializers import (
    IdentityListParamsSerializer,
    IdentityListSerializer,
    IdentityRequestSerializer,
    IdentitySerializer,
    UpdateIdentityRequestSerializer,
)
from baserow.api.mixins import SearchableViewMixin, SortableViewMixin
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.feature_flags import FF_IDENTITIES, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.identities.exceptions import (
    IdentityDoesNotExist,
    IdentityRoleDoesNotExist,
)
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.identities.service import IdentityService

WORKSPACE_ID_PATH_PARAMETER = OpenApiParameter(
    name="workspace_id",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    description="The workspace whose identities are being managed.",
)
IDENTITY_ID_PATH_PARAMETER = OpenApiParameter(
    name="identity_id",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    description="The identity being managed.",
)


class WorkspaceIdentitiesView(APIView, SearchableViewMixin, SortableViewMixin):
    """Lists identities in a workspace and creates new workspace identities."""

    permission_classes = (IsAuthenticated,)
    search_fields = ["first_name"]
    sort_field_mapping = {
        "name": "first_name",
        "role_uid": "workspaceuser__permissions",
        "last_active": "profile__last_active",
        "created_on": "date_joined",
    }

    @extend_schema(
        parameters=[
            WORKSPACE_ID_PATH_PARAMETER,
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Selects which page of identities to return.",
            ),
            OpenApiParameter(
                name="size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Sets the number of identities returned per page.",
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filters identities by name.",
            ),
            OpenApiParameter(
                name="sorts",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Orders identities by a comma-separated list of fields.",
            ),
        ],
        tags=["Identities"],
        operation_id="list_workspace_identities",
        description="Lists the identities in a workspace.",
        responses={
            200: get_example_pagination_serializer_class(
                IdentityListSerializer, serializer_name="IdentityPagination"
            ),
            400: get_error_schema(["ERROR_PAGE_SIZE_LIMIT"]),
        },
    )
    @validate_query_parameters(IdentityListParamsSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            InvalidSortAttributeException: ERROR_INVALID_SORT_ATTRIBUTE,
            InvalidSortDirectionException: ERROR_INVALID_SORT_DIRECTION,
        }
    )
    def get(self, request, workspace_id, query_params):
        """Returns a paginated, searchable, and sortable list of workspace identities."""

        workspace = CoreHandler().get_workspace(workspace_id)
        queryset = IdentityService().list_identities(request.user, workspace)
        queryset = self.apply_search(query_params.get("search"), queryset)
        queryset = self.apply_sorts_or_default_sort(query_params.get("sorts"), queryset)
        # Duplicate sort values need a unique tie-breaker for stable page boundaries.
        if "id" not in queryset.query.order_by:
            queryset = queryset.order_by(*queryset.query.order_by, "id")
        paginator = PageNumberPagination(limit_page_size=200)
        page = paginator.paginate_queryset(queryset, request, view=self)
        serialized_identities = (
            identity_extension_type_registry.annotate_serialized_identities(
                workspace, page, IdentitySerializer(page, many=True).data, request.user
            )
        )
        return paginator.get_paginated_response(serialized_identities)

    @extend_schema(
        parameters=[WORKSPACE_ID_PATH_PARAMETER],
        tags=["Identities"],
        operation_id="create_workspace_identity",
        description="Creates a new identity in a workspace.",
        request=IdentityRequestSerializer,
        responses={
            200: IdentitySerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_IDENTITY_ROLE_DOES_NOT_EXIST"]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @transaction.atomic
    @validate_body(IdentityRequestSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            IdentityRoleDoesNotExist: ERROR_IDENTITY_ROLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request, data, workspace_id):
        """Creates a new identity in the workspace."""

        feature_flag_is_enabled(FF_IDENTITIES, raise_if_disabled=True)
        workspace = CoreHandler().get_workspace(workspace_id)
        identity = IdentityService().create_identity(request.user, workspace, **data)
        return Response(IdentitySerializer(identity).data)


class IdentityView(APIView):
    """Updates and deletes an individual identity."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[IDENTITY_ID_PATH_PARAMETER],
        tags=["Identities"],
        operation_id="update_identity",
        description="Updates an existing identity.",
        request=UpdateIdentityRequestSerializer,
        responses={
            200: IdentitySerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_IDENTITY_ROLE_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @validate_body(UpdateIdentityRequestSerializer)
    @map_exceptions(
        {
            IdentityDoesNotExist: ERROR_IDENTITY_DOES_NOT_EXIST,
            IdentityRoleDoesNotExist: ERROR_IDENTITY_ROLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def patch(self, request, data, identity_id):
        """Updates an existing identity."""

        identity = IdentityHandler().get_identity(identity_id)
        identity = IdentityService().update_identity(request.user, identity, **data)
        return Response(IdentitySerializer(identity).data)

    @extend_schema(
        parameters=[IDENTITY_ID_PATH_PARAMETER],
        tags=["Identities"],
        operation_id="delete_identity",
        description="Deletes an existing identity.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            IdentityDoesNotExist: ERROR_IDENTITY_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, identity_id):
        """Deletes an existing identity."""

        identity = IdentityHandler().get_identity(identity_id)
        IdentityService().delete_identity(request.user, identity)
        return Response(status=204)
