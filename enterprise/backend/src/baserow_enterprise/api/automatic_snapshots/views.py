from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow_enterprise.api.errors import (
    ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_ALREADY_EXISTS,
    ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_DOES_NOT_EXIST,
    ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INTERVAL_TOO_SHORT,
    ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INVALID,
)
from baserow_enterprise.automatic_snapshots.actions import (
    CreateApplicationAutomaticSnapshotScheduleActionType,
    CreateWorkspaceAutomaticSnapshotScheduleActionType,
    DeleteApplicationAutomaticSnapshotScheduleActionType,
    DeleteWorkspaceAutomaticSnapshotScheduleActionType,
    UpdateApplicationAutomaticSnapshotScheduleActionType,
    UpdateWorkspaceAutomaticSnapshotScheduleActionType,
)
from baserow_enterprise.automatic_snapshots.exceptions import (
    AutomaticSnapshotScheduleAlreadyExists,
    AutomaticSnapshotScheduleDoesNotExist,
    AutomaticSnapshotScheduleIntervalTooShort,
    AutomaticSnapshotScheduleInvalid,
)
from baserow_enterprise.automatic_snapshots.service import (
    AutomaticSnapshotScheduleService,
)

from .serializers import (
    ApplicationAutomaticSnapshotOverviewSerializer,
    AutomaticSnapshotScheduleSerializer,
    BulkAutomaticSnapshotScheduleSerializer,
    CreateAutomaticSnapshotScheduleSerializer,
    UpdateAutomaticSnapshotScheduleSerializer,
    WorkspaceAutomaticSnapshotSchedulesSerializer,
)

SCHEDULE_EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
    WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
    AutomaticSnapshotScheduleDoesNotExist: (
        ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_DOES_NOT_EXIST
    ),
    AutomaticSnapshotScheduleAlreadyExists: (
        ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_ALREADY_EXISTS
    ),
    AutomaticSnapshotScheduleIntervalTooShort: (
        ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INTERVAL_TOO_SHORT
    ),
    AutomaticSnapshotScheduleInvalid: ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INVALID,
}

SCHEDULE_ERROR_SCHEMAS = {
    400: get_error_schema(
        [
            "ERROR_USER_NOT_IN_GROUP",
            "ERROR_REQUEST_BODY_VALIDATION",
            "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
            "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_ALREADY_EXISTS",
            "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INTERVAL_TOO_SHORT",
            "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INVALID",
        ]
    ),
    402: get_error_schema(["ERROR_FEATURE_NOT_AVAILABLE"]),
    404: get_error_schema(
        [
            "ERROR_APPLICATION_DOES_NOT_EXIST",
            "ERROR_GROUP_DOES_NOT_EXIST",
            "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_DOES_NOT_EXIST",
        ]
    ),
}

APPLICATION_ID_PARAMETER = OpenApiParameter(
    name="application_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the application.",
)
WORKSPACE_ID_PARAMETER = OpenApiParameter(
    name="workspace_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the workspace.",
)
ENTERPRISE_NOTE = "\n\nThis is an **enterprise** feature."


class ApplicationAutomaticSnapshotScheduleView(APIView):
    @extend_schema(
        parameters=[APPLICATION_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="get_application_automatic_snapshot_schedule",
        description="Returns which automatic snapshot schedule the application "
        "follows: its own schedule, if it has one, and the workspace default."
        + ENTERPRISE_NOTE,
        responses={
            200: ApplicationAutomaticSnapshotOverviewSerializer,
            **SCHEDULE_ERROR_SCHEMAS,
        },
    )
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    def get(self, request: Request, application_id: int) -> Response:
        service = AutomaticSnapshotScheduleService()
        application = service.get_application(application_id)
        overview = service.get_application_overview(request.user, application)
        serializer = ApplicationAutomaticSnapshotOverviewSerializer(
            {
                **overview,
                "min_interval_minutes": (
                    settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES
                ),
            }
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[APPLICATION_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="create_application_automatic_snapshot_schedule",
        description="Gives the application an automatic snapshot schedule of its own. "
        "A disabled schedule opts the application out of the workspace default."
        + ENTERPRISE_NOTE,
        request=CreateAutomaticSnapshotScheduleSerializer,
        responses={200: AutomaticSnapshotScheduleSerializer, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    @validate_body(CreateAutomaticSnapshotScheduleSerializer, return_validated=True)
    def post(self, request: Request, application_id: int, data) -> Response:
        application = AutomaticSnapshotScheduleService().get_application(application_id)
        schedule = action_type_registry.get_by_type(
            CreateApplicationAutomaticSnapshotScheduleActionType
        ).do(request.user, application, data)
        return Response(AutomaticSnapshotScheduleSerializer(schedule).data)

    @extend_schema(
        parameters=[APPLICATION_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="update_application_automatic_snapshot_schedule",
        description="Updates the automatic snapshot schedule of the application."
        + ENTERPRISE_NOTE,
        request=UpdateAutomaticSnapshotScheduleSerializer,
        responses={200: AutomaticSnapshotScheduleSerializer, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    @validate_body(UpdateAutomaticSnapshotScheduleSerializer, return_validated=True)
    def patch(self, request: Request, application_id: int, data) -> Response:
        application = AutomaticSnapshotScheduleService().get_application(application_id)
        updated = action_type_registry.get_by_type(
            UpdateApplicationAutomaticSnapshotScheduleActionType
        ).do(request.user, application, data)
        return Response(AutomaticSnapshotScheduleSerializer(updated.schedule).data)

    @extend_schema(
        parameters=[APPLICATION_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="delete_application_automatic_snapshot_schedule",
        description="Deletes the automatic snapshot schedule of the application, so "
        "it follows the workspace default again. Its automatic snapshots are kept."
        + ENTERPRISE_NOTE,
        responses={204: None, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    def delete(self, request: Request, application_id: int) -> Response:
        application = AutomaticSnapshotScheduleService().get_application(application_id)
        action_type_registry.get_by_type(
            DeleteApplicationAutomaticSnapshotScheduleActionType
        ).do(request.user, application)
        return Response(status=HTTP_204_NO_CONTENT)


class WorkspaceAutomaticSnapshotSchedulesView(APIView):
    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="get_workspace_automatic_snapshot_schedules",
        description="Returns the workspace default automatic snapshot schedule, the "
        "schedules of the applications that have one of their own, and how many "
        "snapshots the workspace uses. An application without a schedule of its own "
        "follows the workspace default." + ENTERPRISE_NOTE,
        responses={
            200: WorkspaceAutomaticSnapshotSchedulesSerializer,
            **SCHEDULE_ERROR_SCHEMAS,
        },
    )
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    def get(self, request: Request, workspace_id: int) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        service = AutomaticSnapshotScheduleService()
        schedules = list(service.get_workspace_schedules(request.user, workspace))

        serializer = WorkspaceAutomaticSnapshotSchedulesSerializer(
            {
                "workspace_default": next(
                    (s for s in schedules if s.is_workspace_default), None
                ),
                "application_schedules": [
                    s for s in schedules if not s.is_workspace_default
                ],
                "min_interval_minutes": (
                    settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES
                ),
            }
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="create_workspace_automatic_snapshot_schedule",
        description="Creates the workspace default automatic snapshot schedule. It "
        "covers every application without a schedule of its own." + ENTERPRISE_NOTE,
        request=CreateAutomaticSnapshotScheduleSerializer,
        responses={200: AutomaticSnapshotScheduleSerializer, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    @validate_body(CreateAutomaticSnapshotScheduleSerializer, return_validated=True)
    def post(self, request: Request, workspace_id: int, data) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        schedule = action_type_registry.get_by_type(
            CreateWorkspaceAutomaticSnapshotScheduleActionType
        ).do(request.user, workspace, data)
        return Response(AutomaticSnapshotScheduleSerializer(schedule).data)

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="update_workspace_automatic_snapshot_schedule",
        description="Updates the workspace default automatic snapshot schedule."
        + ENTERPRISE_NOTE,
        request=UpdateAutomaticSnapshotScheduleSerializer,
        responses={200: AutomaticSnapshotScheduleSerializer, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    @validate_body(UpdateAutomaticSnapshotScheduleSerializer, return_validated=True)
    def patch(self, request: Request, workspace_id: int, data) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        updated = action_type_registry.get_by_type(
            UpdateWorkspaceAutomaticSnapshotScheduleActionType
        ).do(request.user, workspace, data)
        return Response(AutomaticSnapshotScheduleSerializer(updated.schedule).data)

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="delete_workspace_automatic_snapshot_schedule",
        description="Deletes the workspace default automatic snapshot schedule. The "
        "automatic snapshots it created are kept." + ENTERPRISE_NOTE,
        responses={204: None, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    def delete(self, request: Request, workspace_id: int) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        action_type_registry.get_by_type(
            DeleteWorkspaceAutomaticSnapshotScheduleActionType
        ).do(request.user, workspace)
        return Response(status=HTTP_204_NO_CONTENT)


class BulkWorkspaceAutomaticSnapshotSchedulesView(APIView):
    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Automatic snapshots"],
        operation_id="bulk_workspace_automatic_snapshot_schedules",
        description="Gives each selected application its own copy of a schedule, "
        "replacing any schedule it already has, or deletes their own schedules so "
        "they follow the workspace default. Every application is checked "
        "separately, and nothing changes if one of them can't be." + ENTERPRISE_NOTE,
        request=BulkAutomaticSnapshotScheduleSerializer,
        responses={204: None, **SCHEDULE_ERROR_SCHEMAS},
    )
    @transaction.atomic
    @map_exceptions(SCHEDULE_EXCEPTIONS)
    @validate_body(BulkAutomaticSnapshotScheduleSerializer, return_validated=True)
    def post(self, request: Request, workspace_id: int, data) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        applications = AutomaticSnapshotScheduleService().get_applications_for_update(
            request.user, workspace, data["application_ids"]
        )

        schedule_ids = set(
            AutomaticSnapshotScheduleService()
            .handler.list_workspace_schedules(workspace)
            .filter(application__in=applications)
            .values_list("application_id", flat=True)
        )

        # Applying a schedule turns it on, also for an application that was off.
        values = {"enabled": True, **data.get("schedule", {})}
        for application in applications:
            has_schedule = application.id in schedule_ids
            if data["action"] == "reset":
                if has_schedule:
                    action_type_registry.get_by_type(
                        DeleteApplicationAutomaticSnapshotScheduleActionType
                    ).do(request.user, application)
            elif has_schedule:
                action_type_registry.get_by_type(
                    UpdateApplicationAutomaticSnapshotScheduleActionType
                ).do(request.user, application, values)
            else:
                action_type_registry.get_by_type(
                    CreateApplicationAutomaticSnapshotScheduleActionType
                ).do(request.user, application, values)

        return Response(status=HTTP_204_NO_CONTENT)
