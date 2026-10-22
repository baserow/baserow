from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import map_exceptions, validate_query_parameters
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.mixins import SearchableViewMixin
from baserow.api.pagination import LimitOffsetPagination
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.templates.serializers import (
    InstallTemplateQueryParamSerializer,
    ListTemplatesQueryParamSerializer,
    TemplateCategoriesSerializer,
    TemplateListItemSerializer,
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
from baserow.core.user_templates.actions import DeleteUserTemplateActionType
from baserow.core.user_templates.exceptions import (
    TemplateBlocked,
    TemplateHasNoContent,
)

from .errors import (
    ERROR_TEMPLATE_BLOCKED,
    ERROR_TEMPLATE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_HAS_NO_CONTENT,
)


class TemplatesView(APIView, SearchableViewMixin):
    permission_classes = (AllowAny,)
    search_fields = ["name", "description"]

    @extend_schema(
        tags=["Templates"],
        operation_id="list_templates",
        parameters=[
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                enum=["flat"],
                description="`flat` responds with a paginated list of templates. "
                "Otherwise, the response is the list of categories with their "
                "official templates, which is deprecated.",
            ),
            OpenApiParameter(
                name="type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                enum=Template.Type.values,
                description="Only templates of this type. Only with `view=flat`.",
            ),
            OpenApiParameter(
                name="owned",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description="Only templates owned by the authenticated user. Only "
                "with `view=flat`.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Only templates whose name or description contains "
                "this value. Only with `view=flat`.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="How many templates to return, at most 100. Only with "
                "`view=flat`.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The offset of the templates to return. Only with "
                "`view=flat`.",
            ),
        ],
        description=(
            "Lists the templates. The template's `workspace_id` can be used for "
            "previewing purposes because that workspace contains the applications "
            "that are in the template. All the `get` and `list` endpoints related to "
            "that workspace are accessible to whoever can list the template.\n\n"
            "The `view` query parameter selects the shape of the response:\n\n"
            "- `view=flat`: a paginated list of the official templates and the user "
            "templates the caller can open, most recently updated first, filtered "
            "with `type`, `owned` and `search`. A user template shows its latest "
            "revision. `state`, `reason`, `source_workspace_id`, "
            "`source_application_ids` and `install_count` are only set for the "
            "owner of a user template.\n"
            "- Any other or no `view` (deprecated): a list of the template "
            "categories, each with its official templates, ignoring the other query "
            "parameters. Categories holding only user templates are left out."
        ),
        responses={
            200: PolymorphicProxySerializer(
                component_name="TemplatesListResponse",
                serializers=[
                    get_example_pagination_serializer_class(
                        TemplateListItemSerializer,
                        serializer_name="TemplatePagination",
                    ),
                    TemplateCategoriesSerializer(many=True),
                ],
                resource_type_field_name=None,
                many=False,
            ),
            400: get_error_schema(["ERROR_QUERY_PARAMETER_VALIDATION"]),
        },
    )
    def get(self, request):
        """
        Responds with a page of templates, or with the template categories and their
        official templates. The deprecated categories ignore the query parameters, as
        they always did.
        """

        if request.GET.get("view") == "flat":
            return self._get_flat(request)

        # Hide the categories holding only user templates. Empty ones stay listed.
        official_templates = Template.objects.official()
        categories = TemplateCategory.objects.filter(
            Exists(official_templates.filter(categories=OuterRef("pk")))
            | ~Exists(Template.objects.filter(categories=OuterRef("pk")))
        ).prefetch_related(Prefetch("templates", queryset=official_templates))
        serializer = TemplateCategoriesSerializer(categories, many=True)
        return Response(serializer.data)

    @validate_query_parameters(ListTemplatesQueryParamSerializer)
    def _get_flat(self, request, query_params):
        templates = CoreHandler().list_templates(
            request.user,
            template_type=query_params.get("type"),
            owned=query_params["owned"],
        )
        templates = self.apply_search(query_params.get("search"), templates)

        paginator = LimitOffsetPagination()
        paginator.default_limit = 20
        paginator.max_limit = 100
        page = paginator.paginate_queryset(templates, request, self)
        return paginator.get_paginated_response(
            TemplateListItemSerializer(
                page, many=True, context={"request": request}
            ).data
        )


class TemplateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

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

        # A user template shows its public revision, the same for everyone, else
        # the latest revision the user can open, which only its owner can. Install
        # picks the same revision.
        revisions = Template.objects.openable(request.user).filter_by_root(slug=slug)
        template = (
            revisions.public_revisions().first() or revisions.latest_revisions().first()
        )
        if template is None:
            raise TemplateDoesNotExist(f"The template with slug {slug} does not exist.")

        return Response(TemplateSerializer(template).data)

    @extend_schema(
        tags=["Templates"],
        operation_id="delete_template",
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The slug of the template to delete.",
            ),
        ],
        description=(
            "Deletes a user template. Its owner can delete it in any state, and an "
            "instance admin can delete any user template. It's gone for everybody "
            "right away, and its revisions and content are removed later. The "
            "applications installed from it are kept. This can't be undone."
        ),
        request=None,
        responses={
            204: None,
            401: None,
            404: get_error_schema(["ERROR_TEMPLATE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, slug):
        """Deletes a user template owned by the user, or any one by an admin."""

        # Only the root of a template has a slug.
        template_id = (
            Template.objects.filter(slug=slug, root__isnull=True)
            .values_list("id", flat=True)
            .first()
        )
        if template_id is None:
            raise TemplateDoesNotExist(f"The template with slug {slug} does not exist.")

        action_type_registry.get_by_type(DeleteUserTemplateActionType).do(
            request.user, template_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


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
            OpenApiParameter(
                name="latest",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description="Installs the latest revision of a user template, "
                "which only its owner may. Ignored for official templates.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        description=(
            "Start an async job to install the applications of the given template into "
            "the given workspace if the user has access to that workspace. The response "
            "contains those newly created applications.\n\n"
            "A user template can be installed by its owner, unless it's blocked, "
            "and by anyone signed in while it's public. Everyone installs its "
            "public revision, and its owner the latest revision while it isn't "
            "public, or with `latest`. The `template_id` is the id of the "
            "template, not of one of its revisions."
        ),
        request=None,
        responses={
            202: InstallTemplateJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                    "ERROR_TEMPLATE_BLOCKED",
                    "ERROR_TEMPLATE_HAS_NO_CONTENT",
                    "ERROR_QUERY_PARAMETER_VALIDATION",
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
            TemplateBlocked: ERROR_TEMPLATE_BLOCKED,
            TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
        }
    )
    @validate_query_parameters(InstallTemplateQueryParamSerializer)
    @transaction.atomic
    def post(self, request, workspace_id, template_id, query_params):
        """Start an async job to install a template into a workspace."""

        job = JobHandler().create_and_start_job(
            request.user,
            InstallTemplateJobType.type,
            workspace_id=workspace_id,
            template_id=template_id,
            latest=query_params["latest"],
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
