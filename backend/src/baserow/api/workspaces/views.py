from typing import Dict

from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.import_export.errors import (
    ERROR_APPLICATION_IDS_NOT_FOUND,
    ERROR_RESOURCE_DOES_NOT_EXIST,
    ERROR_RESOURCE_IS_BEING_IMPORTED,
    ERROR_RESOURCE_IS_INVALID,
    ERROR_UNTRUSTED_PUBLIC_KEY,
)
from baserow.api.import_export.serializers import ImportResourceSerializer
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.api.user_files.errors import ERROR_FILE_SIZE_TOO_LARGE, ERROR_INVALID_FILE
from baserow.api.utils import validate_data
from baserow.api.workspaces.users.serializers import WorkspaceUserWorkspaceSerializer
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    CreateInitialWorkspaceActionType,
    CreateWorkspaceActionType,
    DeleteWorkspaceActionType,
    LeaveWorkspaceActionType,
    OrderWorkspacesActionType,
    UpdateWorkspaceActionType,
)
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceUserIsLastAdmin,
)
from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportApplicationIdsNotFound,
    ImportExportResourceDoesNotExist,
    ImportExportResourceInBeingImported,
    ImportExportResourceInvalidFile,
)
from baserow.core.import_export.handler import (
    ImportExportHandler,
    ImportExportResourceUntrustedSignature,
)
from baserow.core.job_types import ExportApplicationsJobType, ImportApplicationsJobType
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.operations import UpdateWorkspaceOperationType
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    InvalidFileStreamError,
)

from .errors import ERROR_GROUP_USER_IS_LAST_ADMIN
from .serializers import (
    OrderWorkspacesSerializer,
    PermissionObjectSerializer,
    WorkspaceSerializer,
    get_generative_ai_settings_serializer,
)


class ListExportWorkspaceApplicationsSerializer(serializers.Serializer):
    results = ExportApplicationsJobType().response_serializer_class(many=True)


class WorkspacesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="list_workspaces",
        description=(
            "Lists all the workspaces of the authorized user. A workspace can contain "
            "multiple applications like a database. Multiple users can have "
            "access to a workspace. For example each company could have their own workspace "
            "containing databases related to that company. The order of the workspaces "
            "are custom for each user. The order is configurable via the "
            "**order_workspaces** endpoint."
        ),
        responses={200: WorkspaceUserWorkspaceSerializer(many=True)},
    )
    def get(self, request):
        """Responds with a list of serialized workspaces where the user is part of."""

        workspaceuser_workspaces = (
            CoreHandler()
            .get_workspaceuser_workspace_queryset()
            .filter(user=request.user)
        )

        workspaceuser_workspaces = (
            NotificationHandler.annotate_workspaces_with_unread_notifications_count(
                request.user, workspaceuser_workspaces, outer_ref_key="workspace_id"
            )
        )

        serializer = WorkspaceUserWorkspaceSerializer(
            workspaceuser_workspaces, many=True
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[CLIENT_SESSION_ID_SCHEMA_PARAMETER],
        tags=["Workspaces"],
        operation_id="create_workspace",
        description=(
            "Creates a new workspace where only the authorized user has access to. No "
            "initial data like database applications are added, they have to be "
            "created via other endpoints."
        ),
        request=WorkspaceSerializer,
        responses={200: WorkspaceUserWorkspaceSerializer},
    )
    @map_exceptions()
    @transaction.atomic
    @validate_body(WorkspaceSerializer)
    def post(self, request, data):
        """Creates a new workspace for a user."""

        workspace_user = action_type_registry.get_by_type(CreateWorkspaceActionType).do(
            request.user, data["name"]
        )
        return Response(WorkspaceUserWorkspaceSerializer(workspace_user).data)


class WorkspaceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the workspace related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="update_workspace",
        description=(
            "Updates the existing workspace related to the provided `workspace_id` parameter "
            "if the authorized user belongs to the workspace. It is not yet possible to "
            "add additional users to a workspace."
        ),
        request=WorkspaceSerializer,
        responses={
            200: WorkspaceSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(WorkspaceSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def patch(self, request, data, workspace_id):
        """Updates the workspace if it belongs to a user."""

        workspace = CoreHandler().get_workspace_for_update(workspace_id)
        action_type_registry.get_by_type(UpdateWorkspaceActionType).do(
            request.user, workspace, data["name"]
        )
        return Response(WorkspaceSerializer(workspace).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the workspace related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="delete_workspace",
        description=(
            "Deletes an existing workspace if the authorized user belongs to the workspace. "
            "All the applications, databases, tables etc that were in the workspace are "
            "going to be deleted also."
        ),
        request=WorkspaceSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    def delete(self, request, workspace_id: int):
        """Deletes an existing workspace if it belongs to a user."""

        locked_workspace = CoreHandler().get_workspace_for_update(workspace_id)
        action_type_registry.get_by_type(DeleteWorkspaceActionType).do(
            request.user, locked_workspace
        )
        return Response(status=204)


class WorkspaceLeaveView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Leaves the workspace related to the value.",
            )
        ],
        tags=["Workspaces"],
        operation_id="leave_workspace",
        description=(
            "Makes the authenticated user leave the workspace related to the provided "
            "`workspace_id` if the user is in that workspace. If the user is the last admin "
            "in the workspace, they will not be able to leave it. There must always be one "
            "admin in the workspace, otherwise it will be left without control. If that "
            "is the case, they must either delete the workspace or give another member admin "
            "permissions first."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_GROUP_USER_IS_LAST_ADMIN"]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceUserIsLastAdmin: ERROR_GROUP_USER_IS_LAST_ADMIN,
        }
    )
    def post(self, request, workspace_id):
        """Leaves the workspace if the user is a member of it."""

        workspace = CoreHandler().get_workspace(workspace_id)
        action_type_registry.get(LeaveWorkspaceActionType.type).do(
            request.user, workspace
        )

        return Response(status=204)


class WorkspaceOrderView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="order_workspaces",
        description=(
            "Changes the order of the provided workspace ids to the matching position that "
            "the id has in the list. If the authorized user does not belong to the "
            "workspace it will be ignored. The order will be custom for each user."
        ),
        request=OrderWorkspacesSerializer,
        responses={
            204: None,
        },
    )
    @validate_body(OrderWorkspacesSerializer)
    @transaction.atomic
    def post(self, request, data):
        """Updates to order of some workspaces for a user."""

        action_type_registry.get_by_type(OrderWorkspacesActionType).do(
            request.user, data["workspaces"]
        )
        return Response(status=204)


class WorkspacePermissionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace id we want the permission object for.",
            ),
        ],
        tags=["Workspaces"],
        operation_id="workspace_permissions",
        description=(
            "Returns a the permission data necessary to determine the permissions "
            "of a specific user over a specific workspace. \n"
            "See `core.handler.CoreHandler.get_permissions()` for more details."
        ),
        responses={
            200: PermissionObjectSerializer(many=True),
            404: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_GROUP_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, workspace_id):
        """
        Returns the permission object for the given workspace.
        """

        workspace = CoreHandler().get_workspace(workspace_id)

        permissions = CoreHandler().get_permissions(request.user, workspace=workspace)

        return Response(permissions)


class WorkspaceGenerativeAISettingsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="get_workspace_generative_ai_models_settings",
        description=(
            "Returns the generative AI models settings for the given workspace."
        ),
        responses={200: get_generative_ai_settings_serializer()},
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def get(self, request, workspace_id):
        workspace = CoreHandler().get_workspace(workspace_id)

        # Only ADMINs and who can update the workspace can view these settings.
        CoreHandler().check_permissions(
            request.user,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        serializer = get_generative_ai_settings_serializer()
        settings = workspace.generative_ai_models_settings or {}
        return Response(serializer(settings).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the workspace settings for the generative AI models available.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="update_workspace_generative_ai_models_settings",
        description=(
            "Updates the generative AI models settings for the given workspace."
        ),
        request=get_generative_ai_settings_serializer(),
        responses={
            200: WorkspaceSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def patch(self, request, workspace_id):
        data = validate_data(
            get_generative_ai_settings_serializer(),
            request.data,
            return_validated=True,
        )

        handler = CoreHandler()
        workspace = handler.get_workspace_for_update(workspace_id)
        updated_workspace = handler.update_workspace(
            request.user, workspace, generative_ai_models_settings=data
        )
        return Response(WorkspaceSerializer(updated_workspace).data)


class CreateInitialWorkspaceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="create_initial_workspace",
        description=(
            "Creates an initial workspace. This is typically called after the user "
            "signs up and skips the onboarding in the frontend. It contains some "
            "example data."
        ),
        responses={
            200: WorkspaceUserWorkspaceSerializer,
        },
    )
    @transaction.atomic
    @map_exceptions()
    def post(self, request):
        workspace_user = action_type_registry.get_by_type(
            CreateInitialWorkspaceActionType
        ).do(request.user)
        return Response(WorkspaceUserWorkspaceSerializer(workspace_user).data)


class ListExportWorkspaceApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace that is being exported.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="list_workspace_exports",
        description="Lists exports that were created for given workspace.",
        responses={
            200: ListExportWorkspaceApplicationsSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, workspace_id):
        """
        Lists all available exports created for a given workspace.
        """

        exports = ImportExportHandler().list_exports(request.user, workspace_id)
        return Response(
            ListExportWorkspaceApplicationsSerializer({"results": exports}).data
        )


class AsyncExportWorkspaceApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace that must be exported.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="export_workspace_applications_async",
        description=(
            "Export workspace or set of applications application if the authorized user is "
            "in the application's workspace. "
            "All the related children are also going to be exported. For example "
            "in case of a database application all the underlying tables, fields, "
            "views and rows are going to be exported."
            "Roles are not part of the export."
        ),
        request=None,
        responses={
            202: ExportApplicationsJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_APPLICATION_NOT_IN_GROUP",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(
        ExportApplicationsJobType().request_serializer_class, return_validated=True
    )
    def post(self, request, data: Dict, workspace_id: int) -> Response:
        """
        Exports the listed applications of a workspace to a ZIP file containing the
        applications' data. If the list of applications is empty, all applications of
        the workspace are exported.
        """

        job = JobHandler().create_and_start_job(
            request.user,
            ExportApplicationsJobType.type,
            workspace_id=workspace_id,
            only_structure=data.get("only_structure"),
            application_ids=data.get("application_ids"),
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class ImportExportResourceUploadFileView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace for which file is uploaded.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="import_resource_upload_file",
        description=(
            "Uploads an exported workspace or a set of applications if the authorized user "
            "is in the workspace. The uploaded file must be a valid ZIP file containing the "
            "applications' data for future import."
        ),
        request=None,
        responses={
            202: ImportResourceSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_INVALID_FILE",
                    "ERROR_FILE_SIZE_TOO_LARGE",
                    "ERROR_RESOURCE_IS_INVALID",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            InvalidFileStreamError: ERROR_INVALID_FILE,
            FileSizeTooLargeError: ERROR_FILE_SIZE_TOO_LARGE,
            ImportExportResourceInvalidFile: ERROR_RESOURCE_IS_INVALID,
            ImportExportResourceUntrustedSignature: ERROR_UNTRUSTED_PUBLIC_KEY,
        }
    )
    def post(self, request, workspace_id: int) -> Response:
        handler = ImportExportHandler()
        handler.get_workspace_or_raise(user=request.user, workspace_id=workspace_id)

        if "file" not in request.FILES:
            raise InvalidFileStreamError("No file was provided.")

        file_data = request.FILES.get("file")

        resource = handler.create_resource_from_file(
            request.user, file_data.name, file_data
        )
        serializer = ImportResourceSerializer(resource)
        return Response(serializer.data)


class ImportExportResourceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Workspaces"],
        operation_id="import_export_resource",
        description=(
            "Delete a resource. This endpoint mark as ready for deletion "
            "the specified resource. This operation is not undoable. "
            "The user must be the owner of the resource to perform this action."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                ["RESOURCE_DOES_NOT_EXIST", "ERROR_GROUP_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ImportExportResourceDoesNotExist: ERROR_RESOURCE_DOES_NOT_EXIST,
            ImportExportResourceInBeingImported: ERROR_RESOURCE_IS_BEING_IMPORTED,
        }
    )
    def delete(self, request, workspace_id, resource_id: str) -> Response:
        handler = ImportExportHandler()
        handler.get_workspace_or_raise(user=request.user, workspace_id=workspace_id)

        handler.mark_resource_for_deletion(request.user, resource_id)
        return Response(status=204)


class AsyncImportApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workspace where the application will be imported.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Workspaces"],
        operation_id="import_workspace_applications_async",
        description=(
            "Import a set of applications included in a given resource if the "
            "authorized user is in the specified workspace. "
            "This endpoint requires a valid resource_id of the uploaded file."
        ),
        request=None,
        responses={
            202: ImportApplicationsJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                    "ERROR_RESOURCE_DOES_NOT_EXIST",
                    "ERROR_RESOURCE_IS_INVALID",
                    "ERROR_APPLICATION_IDS_NOT_FOUND",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
            ImportExportResourceDoesNotExist: ERROR_RESOURCE_DOES_NOT_EXIST,
            ImportExportResourceInvalidFile: ERROR_RESOURCE_IS_INVALID,
            ImportExportApplicationIdsNotFound: ERROR_APPLICATION_IDS_NOT_FOUND,
        }
    )
    @validate_body(
        ImportApplicationsJobType().request_serializer_class, return_validated=True
    )
    def post(self, request, data: Dict, workspace_id: int) -> Response:
        job = JobHandler().create_and_start_job(
            request.user,
            ImportApplicationsJobType.type,
            workspace_id=workspace_id,
            resource_id=data["resource_id"],
            application_ids=data.get("application_ids"),
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=HTTP_202_ACCEPTED)
