from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_NOT_IN_GROUP,
    ERROR_APPLICATION_TYPE_DOES_NOT_EXIST,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.api.utils import validate_data
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    OrderApplicationsActionType,
    UpdateApplicationActionType,
)
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationNotInWorkspace,
    ApplicationTypeDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Application
from baserow.core.operations import CreateApplicationsWorkspaceOperationType
from baserow.core.service import CoreService
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem

from .serializers import (
    OrderApplicationsSerializer,
    PolymorphicApplicationCreateSerializer,
    PolymorphicApplicationResponseSerializer,
    PolymorphicApplicationUpdateSerializer,
)


class AllApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Applications"],
        operation_id="list_all_applications",
        description=(
            "Lists all the applications that the user has access to. "
            "The properties that belong to the application can differ per type. An "
            "application always belongs to a single workspace. All the applications of the "
            "workspaces that the user has access to are going to be listed here."
        ),
        responses={
            200: PolymorphicApplicationResponseSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
        },
    )
    @map_exceptions({UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP})
    def get(self, request):
        """
        Responds with a list of serialized applications that belong to the user. If a
        workspace id is provided only the applications of that workspace are going to be
        returned.
        """

        workspaces = CoreService().list_workspaces(request.user).order_by("id")

        all_applications = []
        for workspace in workspaces:
            workspace_applications_qs = CoreService().list_applications_in_workspace(
                request.user, workspace
            )
            all_applications += list(workspace_applications_qs.order_by("order", "id"))

        data = [
            PolymorphicApplicationResponseSerializer(
                application, context={"request": request}
            ).data
            for application in all_applications
        ]

        return Response(data)


class ApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only applications that are in the workspace related "
                "to the provided value.",
            )
        ],
        tags=["Applications"],
        operation_id="workspace_list_applications",
        description=(
            "Lists all the applications of the workspace related to the provided "
            "`workspace_id` parameter if the authorized user is in that workspace. If the"
            "workspace is related to a template, then this endpoint will be publicly "
            "accessible. The properties that belong to the application can differ per "
            "type. An application always belongs to a single workspace."
        ),
        responses={
            200: PolymorphicApplicationResponseSerializer(many=True),
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
        Responds with a list of serialized applications that belong to the user. If a
        workspace id is provided only the applications of that workspace are going to be
        returned.
        """

        workspace = CoreService().get_workspace(request.user, workspace_id)
        applications = CoreService().list_applications_in_workspace(
            request.user, workspace
        )

        data = [
            PolymorphicApplicationResponseSerializer(
                application, context={"request": request}
            ).data
            for application in applications
        ]

        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an application for the workspace related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Applications"],
        operation_id="workspace_create_application",
        description=(
            "Creates a new application based on the provided type. The newly created "
            "application is going to be added to the workspace related to the provided "
            "`workspace_id` parameter. If the authorized user does not belong to the workspace "
            "an error will be returned."
        ),
        request=PolymorphicApplicationCreateSerializer,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ApplicationTypeDoesNotExist: ERROR_APPLICATION_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_body(PolymorphicApplicationCreateSerializer)
    def post(self, request, data, workspace_id):
        """Creates a new application for a user."""

        workspace = CoreHandler().get_workspace(workspace_id)

        CoreHandler().check_permissions(
            request.user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        application = action_type_registry.get_by_type(CreateApplicationActionType).do(
            request.user,
            workspace,
            application_type=data.pop("type"),
            **data,
        )

        return Response(
            PolymorphicApplicationResponseSerializer(
                application, context={"request": request}
            ).data
        )


class ApplicationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the application related to the provided value.",
            )
        ],
        tags=["Applications"],
        operation_id="workspace_get_application",
        description=(
            "Returns the requested application if the authorized user is in the "
            "application's workspace. The properties that belong to the application can "
            "differ per type."
        ),
        request=PolymorphicApplicationCreateSerializer,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
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
        """Selects a single application and responds with a serialized version."""

        application = CoreService().get_application(request.user, application_id)

        return Response(
            PolymorphicApplicationResponseSerializer(
                application, context={"request": request}
            ).data
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the application related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Applications"],
        operation_id="workspace_update_application",
        description=(
            "Updates the existing application related to the provided "
            "`application_id` param if the authorized user is in the application's "
            "workspace. It is not possible to change the type, but properties like the "
            "name can be changed."
        ),
        request=PolymorphicApplicationUpdateSerializer,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ApplicationTypeDoesNotExist: ERROR_APPLICATION_TYPE_DOES_NOT_EXIST,
        }
    )
    def patch(self, request, application_id):
        """Updates the application if the user belongs to the workspace."""

        application = (
            CoreHandler()
            .get_application(
                application_id,
                base_queryset=Application.objects.select_for_update(of=("self",)),
            )
            .specific
        )

        # We validate the data in the method here so that we can
        # pass the application instance directly into the serializer.
        # This ensures the `PolymorphicSerializer` can correctly determine
        # the type of the instance, otherwise PATCH requests would need to
        # include the `type` field in the request body.
        data = validate_data(
            PolymorphicApplicationUpdateSerializer,
            request.data,
            partial=True,
            return_validated=True,
            instance=application,
        )

        application = action_type_registry.get_by_type(UpdateApplicationActionType).do(
            request.user, application, **data
        )

        return Response(
            PolymorphicApplicationResponseSerializer(
                application, context={"request": request}
            ).data
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the application related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Applications"],
        operation_id="workspace_delete_application",
        description=(
            "Deletes an application if the authorized user is in the application's "
            "workspace. All the related children are also going to be deleted. For example "
            "in case of a database application all the underlying tables, fields, "
            "views and rows are going to be deleted."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM"]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    def delete(self, request, application_id):
        """Deletes an existing application if the user belongs to the workspace."""

        application = CoreHandler().get_application(
            application_id,
            base_queryset=Application.objects.select_for_update(of=("self",)),
        )

        action_type_registry.get_by_type(DeleteApplicationActionType).do(
            request.user, application
        )

        return Response(status=204)


class OrderApplicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the order of the applications in the workspace "
                "related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Applications"],
        operation_id="workspace_order_applications",
        description=(
            "Changes the order of the provided application ids to the matching "
            "position that the id has in the list. If the authorized user does not "
            "belong to the workspace it will be ignored. The order of the not provided "
            "tables will be set to `0`."
        ),
        request=OrderApplicationsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_APPLICATION_NOT_IN_GROUP"]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(OrderApplicationsSerializer)
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ApplicationNotInWorkspace: ERROR_APPLICATION_NOT_IN_GROUP,
        }
    )
    def post(self, request, data, workspace_id):
        """Updates to order of the applications in a table."""

        workspace = CoreHandler().get_workspace(workspace_id)
        action_type_registry.get_by_type(OrderApplicationsActionType).do(
            request.user, workspace, data["application_ids"]
        )
        return Response(status=204)


class AsyncDuplicateApplicationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the application to duplicate.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Applications"],
        operation_id="duplicate_application_async",
        description=(
            "Duplicate an application if the authorized user is in the application's "
            "workspace. All the related children are also going to be duplicated. For example "
            "in case of a database application all the underlying tables, fields, "
            "views and rows are going to be duplicated."
        ),
        request=None,
        responses={
            202: DuplicateApplicationJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_APPLICATION_NOT_IN_GROUP",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request: Request, application_id: int) -> Response:
        """
        Duplicates an existing application if the user belongs to the workspace.
        """

        job = JobHandler().create_and_start_job(
            request.user,
            DuplicateApplicationJobType.type,
            application_id=application_id,
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
