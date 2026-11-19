from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import get_error_schema
from baserow.api.snapshots.errors import (
    ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT,
    ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED,
    ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS,
    ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE,
    ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED,
    ERROR_MAX_SNAPSHOTS_IS_ZERO,
    ERROR_MAXIMUM_SNAPSHOTS_REACHED,
    ERROR_SNAPSHOT_DOES_NOT_EXIST,
    ERROR_SNAPSHOT_IS_BEING_CREATED,
    ERROR_SNAPSHOT_IS_BEING_DELETED,
    ERROR_SNAPSHOT_IS_BEING_RESTORED,
    ERROR_SNAPSHOT_NAME_NOT_UNIQUE,
    ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.snapshots.actions import (
    DeleteSnapshotActionType,
    UpdateApplicationMaxSnapshotsActionType,
    UpdateSnapshotProtectionActionType,
    UpdateWorkspaceDefaultMaxSnapshotsActionType,
)
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    MaxSnapshotsAboveLimit,
    MaxSnapshotsBelowProtected,
    MaxSnapshotsChangeDeletesSnapshots,
    MaxSnapshotsExceedsAllowance,
    MaxSnapshotsFullOfProtected,
    MaxSnapshotsIsZero,
    SnapshotDoesNotExist,
    SnapshotIsBeingCreated,
    SnapshotIsBeingDeleted,
    SnapshotIsBeingRestored,
    SnapshotNameNotUnique,
)
from baserow.core.snapshots.handler import SnapshotHandler

from .serializers import (
    CreateSnapshotSerializer,
    SnapshotSerializer,
    SnapshotUsageSerializer,
    UpdateApplicationMaxSnapshotsSerializer,
    UpdateSnapshotSerializer,
    UpdateWorkspaceSnapshotSettingsSerializer,
    WorkspaceSnapshotSettingsSerializer,
)

MAX_SNAPSHOTS_CHANGE_EXCEPTIONS = {
    MaxSnapshotsAboveLimit: ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT,
    MaxSnapshotsBelowProtected: ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED,
    MaxSnapshotsChangeDeletesSnapshots: ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS,
    MaxSnapshotsExceedsAllowance: ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE,
}


class SnapshotsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Application ID for which to list snapshots.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="list_snapshots",
        description=("Lists snapshots that were created for a given application."),
        responses={
            200: SnapshotSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id):
        """
        Lists all snapshots created for a given application.
        """

        handler = SnapshotHandler()
        snapshots = handler.list(application_id, request.user)
        serializer = SnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Application ID for which to list snapshots.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="create_snapshot",
        description=(
            "Creates a new application snapshot. Snapshots represent a state of an "
            "application at a specific point in time and can be restored later, making "
            "it easy to create backups of entire applications. An application holds "
            "up to its max snapshots, which is 0 until an admin raises it. When it's "
            "at its max, the new snapshot replaces its oldest unprotected one. "
            "Snapshots are protected unless `protected` is false, and a protected "
            "snapshot is never replaced. With `raise_max_snapshots`, the max "
            "snapshots of the application is raised by one first when it has no room "
            "for another snapshot."
        ),
        request=CreateSnapshotSerializer,
        responses={
            202: JobSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_MAXIMUM_SNAPSHOTS_REACHED",
                    "ERROR_MAX_SNAPSHOTS_IS_ZERO",
                    "ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED",
                    "ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT",
                    "ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE",
                    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
                    "ERROR_SNAPSHOT_IS_BEING_CREATED",
                    "ERROR_SNAPSHOT_NAME_NOT_UNIQUE",
                    "ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaximumSnapshotsReached: ERROR_MAXIMUM_SNAPSHOTS_REACHED,
            MaxSnapshotsIsZero: ERROR_MAX_SNAPSHOTS_IS_ZERO,
            MaxSnapshotsFullOfProtected: ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED,
            MaxSnapshotsAboveLimit: ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT,
            MaxSnapshotsExceedsAllowance: ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE,
            ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
            SnapshotIsBeingCreated: ERROR_SNAPSHOT_IS_BEING_CREATED,
            SnapshotNameNotUnique: ERROR_SNAPSHOT_NAME_NOT_UNIQUE,
            MaxJobCountExceeded: ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED,
        }
    )
    @validate_body(CreateSnapshotSerializer)
    @transaction.atomic
    def post(self, request, application_id, data):
        """
        Creates a new application snapshot, after raising the max snapshots of the
        application when asked and needed.
        """

        handler = SnapshotHandler()
        if data["raise_max_snapshots"]:
            max_snapshots = handler.get_max_snapshots_to_make_room(
                application_id, request.user
            )
            if max_snapshots is not None:
                action_type_registry.get(
                    UpdateApplicationMaxSnapshotsActionType.type
                ).do(request.user, application_id, max_snapshots)
        snapshot_created = handler.start_create_job(
            application_id, request.user, data["name"], protected=data["protected"]
        )
        serializer = JobSerializer(snapshot_created["job"])
        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class RestoreSnapshotView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="snapshot_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Id of the snapshot to restore.",
            )
        ],
        tags=["Snapshots"],
        operation_id="restore_snapshot",
        description=(
            "Restores a snapshot. When an application snapshot is restored, "
            "a new application will be created in the same workspace that the original "
            "application was placed in with the name of the snapshot and data that were"
            " in the original application at the time the snapshot was taken. "
            "The original application that the snapshot was taken from is unaffected. "
            "Snapshots can be restored multiple times and a number suffix is added to "
            "the new application name in the case of a collision."
        ),
        request=None,
        responses={
            200: JobSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
                    "ERROR_SNAPSHOT_IS_BEING_RESTORED",
                    "ERROR_SNAPSHOT_IS_BEING_DELETED",
                    "ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_SNAPSHOT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            SnapshotDoesNotExist: ERROR_SNAPSHOT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
            SnapshotIsBeingRestored: ERROR_SNAPSHOT_IS_BEING_RESTORED,
            SnapshotIsBeingDeleted: ERROR_SNAPSHOT_IS_BEING_DELETED,
            MaxJobCountExceeded: ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED,
        }
    )
    @transaction.atomic
    def post(self, request, snapshot_id):
        """
        Restores a given application snapshot.
        """

        handler = SnapshotHandler()
        job = handler.start_restore_job(snapshot_id, request.user)
        serializer = JobSerializer(job)
        return Response(serializer.data)


class SnapshotView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="snapshot_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Id of the snapshot to delete.",
            )
        ],
        tags=["Snapshots"],
        operation_id="delete_snapshot",
        description=(
            "Deletes a snapshot. Deleting a snapshot doesn't affect the application "
            "that the snapshot is made from and doesn't affect any applications that "
            "were created by restoring it. Snapshot deletion is permanent and "
            "can't be undone."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
                    "ERROR_SNAPSHOT_IS_BEING_RESTORED",
                    "ERROR_SNAPSHOT_IS_BEING_DELETED",
                    "ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_SNAPSHOT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            SnapshotDoesNotExist: ERROR_SNAPSHOT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
            SnapshotIsBeingRestored: ERROR_SNAPSHOT_IS_BEING_RESTORED,
            SnapshotIsBeingDeleted: ERROR_SNAPSHOT_IS_BEING_DELETED,
            MaxJobCountExceeded: ERROR_SNAPSHOT_OPERATION_LIMIT_EXCEEDED,
        }
    )
    @transaction.atomic
    def delete(self, request, snapshot_id):
        """
        Deletes a given application snapshot.
        """

        action_type_registry.get(DeleteSnapshotActionType.type).do(
            request.user, snapshot_id
        )
        return Response(status=204)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="snapshot_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Id of the snapshot to update.",
            )
        ],
        tags=["Snapshots"],
        operation_id="update_snapshot",
        description=(
            "Protects or unprotects a snapshot. A protected snapshot is never deleted "
            "automatically to make room for a new one or when a max is lowered. It "
            "still expires."
        ),
        request=UpdateSnapshotSerializer,
        responses={
            200: SnapshotSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_SNAPSHOT_IS_BEING_CREATED",
                ]
            ),
            404: get_error_schema(["ERROR_SNAPSHOT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            SnapshotDoesNotExist: ERROR_SNAPSHOT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            SnapshotIsBeingCreated: ERROR_SNAPSHOT_IS_BEING_CREATED,
        }
    )
    @validate_body(UpdateSnapshotSerializer)
    @transaction.atomic
    def patch(self, request, snapshot_id, data):
        snapshot = action_type_registry.get(UpdateSnapshotProtectionActionType.type).do(
            request.user, snapshot_id, data["protected"]
        )
        return Response(SnapshotSerializer(snapshot).data)


class SnapshotUsageView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Application ID whose workspace snapshot usage to get.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="get_snapshot_usage",
        description=(
            "Returns how many snapshots the workspace of the application has, its "
            "snapshot limit, and after how many days snapshots are deleted."
        ),
        responses={
            200: SnapshotUsageSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, application_id):
        usage = SnapshotHandler().get_usage(application_id, request.user)
        return Response(SnapshotUsageSerializer(usage).data)


class ApplicationMaxSnapshotsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Application ID whose max snapshots to change.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="update_application_max_snapshots",
        description=(
            "Changes how many snapshots an application keeps. Each keep reserves part "
            "of the workspace's snapshot allowance, so raising one is only allowed if "
            "enough of it is left. Lowering one deletes the oldest unprotected "
            "snapshots beyond it, which `delete_snapshots` must confirm."
        ),
        request=UpdateApplicationMaxSnapshotsSerializer,
        responses={
            200: SnapshotUsageSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT",
                    "ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED",
                    "ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS",
                    "ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            **MAX_SNAPSHOTS_CHANGE_EXCEPTIONS,
        }
    )
    @validate_body(UpdateApplicationMaxSnapshotsSerializer)
    @transaction.atomic
    def patch(self, request, application_id, data):
        action_type_registry.get(UpdateApplicationMaxSnapshotsActionType.type).do(
            request.user,
            application_id,
            data["max_snapshots"],
            delete_snapshots=data["delete_snapshots"],
        )
        usage = SnapshotHandler().get_usage(application_id, request.user)
        return Response(SnapshotUsageSerializer(usage).data)


class WorkspaceSnapshotSettingsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Workspace ID whose snapshot settings to get.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="get_workspace_snapshot_settings",
        description=(
            "Returns the snapshot allowance of the workspace, how much of it its "
            "applications reserve, its default max snapshots, and the max snapshots "
            "and snapshots of every application the user can see."
        ),
        responses={
            200: WorkspaceSnapshotSettingsSerializer,
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
        settings = SnapshotHandler().get_workspace_settings(workspace_id, request.user)
        return Response(WorkspaceSnapshotSettingsSerializer(settings).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Workspace ID whose snapshot settings to change.",
                required=True,
            )
        ],
        tags=["Snapshots"],
        operation_id="update_workspace_snapshot_settings",
        description=(
            "Changes the default max snapshots of the workspace: the max snapshots of "
            "its applications that don't have their own. The same rules as for an "
            "application's max snapshots apply to every application that follows it."
        ),
        request=UpdateWorkspaceSnapshotSettingsSerializer,
        responses={
            200: WorkspaceSnapshotSettingsSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_SNAPSHOTS_ABOVE_LIMIT",
                    "ERROR_MAX_SNAPSHOTS_BELOW_PROTECTED",
                    "ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS",
                    "ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            **MAX_SNAPSHOTS_CHANGE_EXCEPTIONS,
        }
    )
    @validate_body(UpdateWorkspaceSnapshotSettingsSerializer)
    @transaction.atomic
    def patch(self, request, workspace_id, data):
        action_type_registry.get(UpdateWorkspaceDefaultMaxSnapshotsActionType.type).do(
            request.user,
            workspace_id,
            data["default_max_snapshots"],
            delete_snapshots=data["delete_snapshots"],
        )
        settings = SnapshotHandler().get_workspace_settings(workspace_id, request.user)
        return Response(WorkspaceSnapshotSettingsSerializer(settings).data)
