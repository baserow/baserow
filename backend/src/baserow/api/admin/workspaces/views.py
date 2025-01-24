from django.db import transaction
from django.db.models import Count

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.admin.views import AdminListingView
from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST
from baserow.api.schemas import get_error_schema
from baserow.core.admin.workspaces.exceptions import CannotDeleteATemplateGroupError
from baserow.core.admin.workspaces.handler import WorkspacesAdminHandler
from baserow.core.exceptions import WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.usage.handler import UsageHandler

from .errors import ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP
from .serializers import WorkspacesAdminResponseSerializer


class WorkspacesAdminView(AdminListingView):
    serializer_class = WorkspacesAdminResponseSerializer
    search_fields = ["id", "name"]
    sort_field_mapping = {
        "id": "id",
        "name": "name",
        "application_count": "application_count",
        "created_on": "created_on",
        "row_count": "row_count",
        "storage_usage": "storage_usage",
    }

    def get_queryset(self, request):
        return (
            Workspace.objects.prefetch_related(
                "workspaceuser_set", "workspaceuser_set__user"
            )
            .annotate(
                application_count=Count("application"),
                template_count=Count("template"),
                **{
                    WorkspacesAdminResponseSerializer.ROW_COUNT_ANNOTATION_NAME: UsageHandler.get_workspace_row_count_annotation()
                },
            )
            .exclude(template_count__gt=0)
        )

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_workspaces",
        description="Returns all workspaces with detailed information on each workspace, "
        "if the requesting user is staff.",
        **AdminListingView.get_extend_schema_parameters(
            "workspaces", serializer_class, search_fields, sort_field_mapping
        ),
    )
    def get(self, request):
        return super().get(request)


class WorkspaceAdminView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_delete_workspace",
        description="Deletes the specified workspace and the applications inside that "
        "workspace, if the requesting user is staff.",
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace to delete",
            ),
        ],
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_FEATURE_NOT_AVAILABLE"]
            ),
            401: None,
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            CannotDeleteATemplateGroupError: ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP,
        }
    )
    @transaction.atomic
    def delete(self, request, workspace_id):
        """Deletes the specified workspace"""

        workspace = CoreHandler().get_workspace(
            workspace_id,
            base_queryset=Workspace.objects.select_for_update(of=("self",)),
        )
        handler = WorkspacesAdminHandler()
        handler.delete_workspace(request.user, workspace)

        return Response(status=204)
