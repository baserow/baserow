from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_query_parameters
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.api.search.serializers import (
    WorkspaceSearchResponseSerializer,
    WorkspaceSearchSerializer,
)
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.search.handler import WorkspaceSearchHandler


class WorkspaceSearchView(APIView):
    """
    API view for workspace search functionality.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Workspace ID to search within",
            ),
        ],
        request=WorkspaceSearchSerializer,
        responses={
            200: WorkspaceSearchResponseSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_INVALID_SEARCH_QUERY"]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
        tags=["Search"],
        operation_id="workspace_search",
        description="Search across all searchable content within a workspace",
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(WorkspaceSearchSerializer, return_validated=True)
    def get(self, request, workspace_id, query_params):
        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            request.user,
            ReadWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        handler = WorkspaceSearchHandler()
        result_data = handler.search_workspace(
            user=request.user,
            workspace=workspace,
            query=query_params["query"],
            limit=query_params["limit"],
            offset=query_params["offset"],
        )
        serializer = WorkspaceSearchResponseSerializer(data=result_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
