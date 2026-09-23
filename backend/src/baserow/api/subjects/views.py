from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_query_parameters
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST
from baserow.api.pagination import PageNumberPagination
from baserow.core.exceptions import WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.registries import subject_type_registry
from baserow.core.subject_options import SubjectOptionsHandler
from baserow.core.types import PermissionCheck

from .serializers import SubjectOptionSerializer, SubjectOptionsQueryParamsSerializer


class SubjectOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Subjects"],
        operation_id="list_subject_options",
        parameters=[SubjectOptionsQueryParamsSerializer],
        responses={200: SubjectOptionSerializer(many=True)},
        description="Returns searchable options supplied by registered subject types.",
    )
    @map_exceptions({WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST})
    @validate_query_parameters(
        SubjectOptionsQueryParamsSerializer, return_validated=True
    )
    def get(self, request, query_params):
        """Return subject options after checking the requested disclosure scope."""

        workspace_id = query_params.get("workspace_id")
        workspace = None
        if workspace_id is not None:
            workspace = CoreHandler().get_workspace(workspace_id)
            requested_types = query_params.get("subject_types") or set(
                subject_type_registry.get_types()
            )
            operation_types = {
                subject_type_registry.get(subject_type_name).options_list_operation_type
                for subject_type_name in requested_types
            }
            checks = [
                PermissionCheck(request.user, operation_type, workspace)
                for operation_type in operation_types
                if operation_type is not None
            ]
            CoreHandler().check_multiple_permissions(
                checks, workspace=workspace, raise_exception=True
            )
        elif not request.user.is_staff:
            raise PermissionDenied()

        queryset = SubjectOptionsHandler.get_options(
            workspace=workspace,
            search=query_params.get("search") or "",
            subject_types=query_params.get("subject_types"),
        )
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = SubjectOptionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
