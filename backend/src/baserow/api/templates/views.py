from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.templates.serializers import (
    TemplateCategoriesSerializer,
    TemplateSerializer,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import InstallTemplateActionType
from baserow.core.exceptions import (
    TemplateDoesNotExist,
    TemplateFileDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Template, TemplateCategory

from .errors import ERROR_TEMPLATE_DOES_NOT_EXIST, ERROR_TEMPLATE_FILE_DOES_NOT_EXIST


class TemplatesView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Templates"],
        operation_id="list_templates",
        description=(
            "Lists all the template categories and the related templates that are in "
            "that category. The template's `workspace_id` can be used for previewing "
            "purposes because that workspace contains the applications that are in the "
            "template. All the `get` and `list` endpoints related to that workspace are "
            "publicly accessible."
        ),
        responses={200: TemplateCategoriesSerializer(many=True)},
    )
    def get(self, request):
        """Responds with a list of all template categories and templates."""

        categories = TemplateCategory.objects.all().prefetch_related("templates")
        serializer = TemplateCategoriesSerializer(categories, many=True)
        return Response(serializer.data)


class TemplateView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(exclude=True)
    @map_exceptions(
        {
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
        }
    )
    def get(self, request, slug):
        """
        Responds with a more detailed serialized version of the template related to
        the provided template slug.
        """

        try:
            template = Template.objects.prefetch_related("categories").get(slug=slug)
        except Template.DoesNotExist as exc:
            raise TemplateDoesNotExist(
                f"The template with slug {slug} does not exist."
            ) from exc

        return Response(TemplateSerializer(template).data)


class InstallTemplateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Templates"],
        operation_id="install_template",
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id related to the workspace where the template "
                "applications must be installed into.",
            ),
            OpenApiParameter(
                name="template_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id related to the template that must be installed.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        description=(
            "(Deprecated) Installs the applications of the given template into "
            "the given workspace if the user has access to that workspace. The response "
            "contains those newly created applications."
        ),
        request=None,
        responses={
            200: PolymorphicApplicationResponseSerializer(many=True),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST"]
            ),
            404: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_TEMPLATE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
            TemplateFileDoesNotExist: ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request, workspace_id, template_id):
        """Install a template into a workspace."""

        handler = CoreHandler()
        workspace = handler.get_workspace(workspace_id)
        template = handler.get_template(template_id)
        installed_applications = action_type_registry.get_by_type(
            InstallTemplateActionType
        ).do(request.user, workspace, template)

        data = [
            PolymorphicApplicationResponseSerializer(application).data
            for application in installed_applications
        ]
        return Response(data)


class AsyncInstallTemplateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Templates"],
        operation_id="install_template_async",
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id related to the workspace where the template "
                "applications must be installed into.",
            ),
            OpenApiParameter(
                name="template_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id related to the template that must be installed.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        description=(
            "Start an async job to install the applications of the given template into "
            "the given workspace if the user has access to that workspace. The response "
            "contains those newly created applications."
        ),
        request=None,
        responses={
            202: InstallTemplateJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_TEMPLATE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
            TemplateFileDoesNotExist: ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request, workspace_id, template_id):
        """Start an async job to install a template into a workspace."""

        job = JobHandler().create_and_start_job(
            request.user,
            InstallTemplateJobType.type,
            workspace_id=workspace_id,
            template_id=template_id,
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
