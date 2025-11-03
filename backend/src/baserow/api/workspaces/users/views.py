from django.db import transaction
from django.db.models import Prefetch

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
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
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.exceptions import (
    InvalidSortAttributeException,
    InvalidSortDirectionException,
)
from baserow.api.mixins import SearchableViewMixin, SortableViewMixin
from baserow.api.schemas import get_error_schema
from baserow.api.user.registries import member_data_registry
from baserow.api.workspaces.users.errors import (
    ERROR_CANNOT_DELETE_YOURSELF_FROM_GROUP,
    ERROR_GROUP_USER_DOES_NOT_EXIST,
)
from baserow.core.db import specific_queryset
from baserow.core.exceptions import (
    CannotDeleteYourselfFromWorkspace,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceUserDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel

from .generated_serializers import ListWorkspaceUsersWithMemberDataSerializer
from .serializers import (
    GetWorkspaceUsersViewParamsSerializer,
    UpdateWorkspaceUserSerializer,
    WorkspaceUserSerializer,
)


class WorkspaceUsersView(APIView, SearchableViewMixin, SortableViewMixin):
    search_fields = ["user__username", "user__email"]
    sort_field_mapping = {
        "name": "user__username",
        "email": "user__email",
        "role_uid": "permissions",
    }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Lists workspace users related to the provided workspace "
                "value.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Search for workspace users by username, or email.",
            ),
            OpenApiParameter(
                name="sorts",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Sort workspace users by name, email or role.",
            ),
        ],
        tags=["Workspaces"],
        operation_id="list_workspace_users",
        description=(
            "Lists all the users that are in a workspace if the authorized user has admin "
            "permissions to the related workspace. To add a user to a workspace an invitation "
            "must be sent first."
        ),
        responses={
            200: ListWorkspaceUsersWithMemberDataSerializer(many=True),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_INVALID_SORT_DIRECTION",
                    "ERROR_INVALID_SORT_ATTRIBUTE",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            InvalidSortDirectionException: ERROR_INVALID_SORT_DIRECTION,
            InvalidSortAttributeException: ERROR_INVALID_SORT_ATTRIBUTE,
        }
    )
    @validate_query_parameters(GetWorkspaceUsersViewParamsSerializer)
    def get(self, request, workspace_id, query_params):
        """Responds with a list of serialized users that are part of the workspace."""

        search = query_params.get("search")
        sorts = query_params.get("sorts")

        workspace = CoreHandler().get_workspace(workspace_id)

        CoreHandler().check_permissions(
            request.user,
            ListWorkspaceUsersWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        qs = (
            WorkspaceUser.objects.filter(workspace=workspace)
            .select_related("workspace", "user", "user__profile")
            .prefetch_related(
                Prefetch(
                    "user__two_factor_auth_providers",
                    queryset=specific_queryset(
                        TwoFactorAuthProviderModel.objects.all()
                    ),
                )
            )
        )

        qs = self.apply_search(search, qs)
        qs = self.apply_sorts_or_default_sort(sorts, qs)

        serializer = ListWorkspaceUsersWithMemberDataSerializer(qs, many=True)
        # Iterate over any registered `member_data_registry`
        # member data types and annotate the response with it.
        for data_type in member_data_registry.get_all():
            data_type.annotate_serialized_workspace_members_data(
                workspace, serializer.data, request.user
            )

        return Response(serializer.data)


class WorkspaceUserView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the workspace user related to the provided value.",
            )
        ],
        tags=["Workspaces"],
        operation_id="update_workspace_user",
        description=(
            "Updates the existing workspace user related to the provided "
            "`workspace_user_id` param if the authorized user has admin rights to "
            "the related workspace."
        ),
        request=UpdateWorkspaceUserSerializer,
        responses={
            200: WorkspaceUserSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_USER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateWorkspaceUserSerializer)
    @map_exceptions(
        {
            WorkspaceUserDoesNotExist: ERROR_GROUP_USER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def patch(self, request, data, workspace_user_id):
        """
        Updates the workspace user if the user has admin permissions to the workspace.
        """

        workspace_user = CoreHandler().get_workspace_user(
            workspace_user_id,
            base_queryset=WorkspaceUser.objects.select_for_update(of=("self",)),
        )
        workspace_user = CoreHandler().update_workspace_user(
            request.user, workspace_user, **data
        )
        return Response(WorkspaceUserSerializer(workspace_user).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the workspace user related to the provided "
                "value.",
            )
        ],
        tags=["Workspaces"],
        operation_id="delete_workspace_user",
        description=(
            "Deletes a workspace user if the authorized user has admin rights to "
            "the related workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_INVALID_GROUP_PERMISSIONS"]
            ),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceUserDoesNotExist: ERROR_GROUP_USER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            CannotDeleteYourselfFromWorkspace: ERROR_CANNOT_DELETE_YOURSELF_FROM_GROUP,
        }
    )
    def delete(self, request, workspace_user_id):
        """Deletes an existing workspace_user if the user belongs to the workspace."""

        workspace_user = CoreHandler().get_workspace_user(
            workspace_user_id,
            base_queryset=WorkspaceUser.objects.select_for_update(of=("self",)),
        )
        CoreHandler().delete_workspace_user(request.user, workspace_user)
        return Response(status=204)
