from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
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
    DownloadTemplateSerializer,
    InstallTemplateQueryParamSerializer,
    ListTemplatesQueryParamSerializer,
    TemplateArchiveSerializer,
    TemplateCategoriesSerializer,
    TemplateCategorySerializer,
    TemplateListItemSerializer,
    UpdateTemplateSerializer,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import InstallTemplateActionType
from baserow.core.context import get_private_link_token
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
from baserow.core.user_templates.actions import (
    DeleteUserTemplateActionType,
    RotateUserTemplatePrivateLinkActionType,
    UpdateUserTemplatePrivateLinkActionType,
    UpdateUserTemplateVisibilityActionType,
)
from baserow.core.user_templates.archive import (
    has_valid_archive,
    template_archive_file_name,
    template_archive_url,
)
from baserow.core.user_templates.exceptions import (
    TemplateBlocked,
    TemplateHasNoContent,
    TemplateUpdated,
    UserTemplatePublicListingConsentRequired,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.job_types import DownloadUserTemplateJobType
from baserow.core.user_templates.models import DownloadUserTemplateJob

from .errors import (
    ERROR_PUBLIC_LISTING_CONSENT_REQUIRED,
    ERROR_TEMPLATE_BLOCKED,
    ERROR_TEMPLATE_BLOCKED_UPDATE,
    ERROR_TEMPLATE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_HAS_NO_CONTENT,
    ERROR_TEMPLATE_PRIVATE_LINK_BLOCKED,
    ERROR_TEMPLATE_UPDATED,
)


def get_template_id(slug: str) -> int:
    """
    Returns the id of the template with the slug, which only its root has.

    :raises TemplateDoesNotExist: If no template has the slug.
    """

    template_id = (
        Template.objects.filter(slug=slug, root__isnull=True)
        .values_list("id", flat=True)
        .first()
    )
    if template_id is None:
        raise TemplateDoesNotExist(f"The template with slug {slug} does not exist.")
    return template_id


TEMPLATE_PRIVATE_LINK_SCHEMA_PARAMETER = OpenApiParameter(
    name=settings.TEMPLATE_PRIVATE_LINK_TOKEN_HEADER,
    location=OpenApiParameter.HEADER,
    type=OpenApiTypes.STR,
    required=False,
    description="The token of the private link of a user template, which gives "
    "access to it while it's private.",
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
                enum=["flat", "public_categories"],
                description="`flat` responds with a paginated list of templates, "
                "`public_categories` with the categories of the public user "
                "templates, without the official ones. Otherwise, the response is "
                "the list of categories with their official templates, which is "
                "deprecated.",
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
                name="listed",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description="Only the templates everybody can open, each as "
                "everybody sees it: the official templates, unless `type=user`, and "
                "the public revision of the public user templates. The "
                "authenticated user's own come first, then the most recently listed. "
                "Only with `view=flat`.",
            ),
            OpenApiParameter(
                name="category",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Only templates in the category with this id. Only with "
                "`view=flat`.",
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
            "templates the caller can open, most recently changed first, filtered "
            "with `type`, `owned`, `listed`, `category` and `search`. A user "
            "template shows the latest revision the caller can open, or its public "
            "revision with `listed=true`. `state`, `reason`, `source_workspace_id`, "
            "`source_application_ids` and `install_count` are only set for the "
            "owner of a user template.\n"
            "- `view=public_categories`: the categories holding at least one public "
            "user template, ignoring the other query parameters. Official "
            "templates aren't taken into account.\n"
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
                    TemplateCategorySerializer(many=True),
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

        view = request.GET.get("view")
        if view == "flat":
            return self._get_flat(request)
        if view == "public_categories":
            return self._get_public_categories(request)

        # Hide the categories holding only user templates. Empty ones stay listed.
        official_templates = Template.objects.official()
        categories = TemplateCategory.objects.filter(
            Exists(official_templates.filter(categories=OuterRef("pk")))
            | ~Exists(Template.objects.filter(categories=OuterRef("pk")))
        ).prefetch_related(Prefetch("templates", queryset=official_templates))
        serializer = TemplateCategoriesSerializer(categories, many=True)
        return Response(serializer.data)

    def _get_public_categories(self, request):
        categories = CoreHandler().list_public_template_categories(request.user)
        return Response(TemplateCategorySerializer(categories, many=True).data)

    @validate_query_parameters(ListTemplatesQueryParamSerializer, return_validated=True)
    def _get_flat(self, request, query_params):
        templates = CoreHandler().list_templates(
            request.user,
            template_type=query_params.get("type"),
            owned=query_params["owned"],
            listed=query_params["listed"],
            category_id=query_params.get("category"),
        )
        templates = self.apply_search(query_params.get("search"), templates)

        paginator = LimitOffsetPagination()
        paginator.default_limit = 20
        paginator.max_limit = 100
        page = paginator.paginate_queryset(templates, request, self)
        return paginator.get_paginated_response(
            TemplateListItemSerializer(
                page,
                many=True,
                context={"request": request, "listed": query_params["listed"]},
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
        Responds with the template of the slug: its public revision, or the latest
        revision for its owner or when it has no public one.
        """

        revisions = Template.objects.openable(
            request.user,
            private_link_token=get_private_link_token(),
            allow_instance_admin=True,
        ).filter_by_root(slug=slug)
        template = revisions.public_revisions().first()
        if template is None or (
            request.user.is_authenticated
            and template.get_root().owner_id == request.user.id
        ):
            template = revisions.latest_revisions().with_template_state().first()
        if template is None:
            raise TemplateDoesNotExist(f"The template with slug {slug} does not exist.")

        return Response(
            TemplateListItemSerializer(
                template,
                context={"request": request, "shows_state_to_staff": True},
            ).data
        )

    @extend_schema(
        tags=["Templates"],
        operation_id="update_template",
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The slug of the template to update.",
            ),
        ],
        description=(
            "Updates a user template owned by the user. With `visibility` "
            "`public`, its latest revision goes to review, and once an instance "
            "admin approves it, it's listed, with the name of its author, for "
            "everybody on this instance, who can open it. Signed-in users can "
            "install it. It's listed right away only when approval isn't required "
            "and no admin rejected the template since it was last approved. The "
            "author must agree to that with `public_listing_consent`. The `state` "
            "of the response tells whether it's listed or in review. With "
            "`visibility` `private`, it isn't listed anymore, its revision in "
            "review or rejected is withdrawn, and only its owner and anyone with "
            "its private link can open and install it. Nothing changes when a "
            "template whose latest revision is listed or in review is made "
            "public, or when a template that isn't listed and has nothing in "
            "review or rejected is made private. With "
            "`private_link`, instead of `visibility`, the private link of the "
            "template is created or turned off, and its token is in "
            "`private_link_token`. Anyone with the link can preview the "
            "template, also signed out, and install or download it once signed "
            "in. Turning the link off stops it from working, and a public "
            "template stays public. Asking for the link it has changes nothing. "
            "The visibility and the private link of a blocked template can't be "
            "changed."
        ),
        request=UpdateTemplateSerializer,
        responses={
            200: TemplateListItemSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_PUBLIC_LISTING_CONSENT_REQUIRED",
                    "ERROR_TEMPLATE_HAS_NO_CONTENT",
                    "ERROR_TEMPLATE_BLOCKED",
                ]
            ),
            401: None,
            404: get_error_schema(["ERROR_TEMPLATE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
            UserTemplatePublicListingConsentRequired: (
                ERROR_PUBLIC_LISTING_CONSENT_REQUIRED
            ),
            TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
            TemplateBlocked: ERROR_TEMPLATE_BLOCKED_UPDATE,
        }
    )
    @validate_body(UpdateTemplateSerializer)
    def patch(self, request: Request, data: Dict[str, Any], slug: str) -> Response:
        """
        Makes a user template owned by the user public or private, or changes its
        private link.
        """

        if "private_link" in data:
            revision = action_type_registry.get_by_type(
                UpdateUserTemplatePrivateLinkActionType
            ).do(request.user, get_template_id(slug), data["private_link"])
        else:
            revision = action_type_registry.get_by_type(
                UpdateUserTemplateVisibilityActionType
            ).do(
                request.user,
                get_template_id(slug),
                data["visibility"] == "public",
                public_listing_consent=data["public_listing_consent"],
            )
        revision = (
            Template.objects.select_related("root")
            .with_template_state()
            .get(id=revision.id)
        )
        return Response(
            TemplateListItemSerializer(revision, context={"request": request}).data
        )

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

        action_type_registry.get_by_type(DeleteUserTemplateActionType).do(
            request.user, get_template_id(slug)
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
                "also while it's public. Only its owner may ask for it. Ignored "
                "for official templates.",
            ),
            OpenApiParameter(
                name="revision_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The `revision_id` of the user template that was "
                "shown. If another revision would be installed, because the "
                "template was updated since, nothing is installed. Ignored for "
                "official templates.",
            ),
            TEMPLATE_PRIVATE_LINK_SCHEMA_PARAMETER,
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        description=(
            "Start an async job to install the applications of the given template into "
            "the given workspace if the user has access to that workspace. The response "
            "contains those newly created applications.\n\n"
            "A user template can be installed by its owner, by the instance "
            "admins, by anyone signed in while it's public, and by anyone signed "
            "in with the token of its private link. Only the instance admins can "
            "install a blocked one. While it's public, everyone installs its "
            "public revision, and its owner the latest revision with `latest`. "
            "While it isn't public, everyone who can install it installs the "
            "latest revision. The `template_id` is the id of the template, not of "
            "one of its revisions."
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
                    "ERROR_TEMPLATE_UPDATED",
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
            TemplateUpdated: ERROR_TEMPLATE_UPDATED,
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
            revision_id=query_params.get("revision_id"),
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class RotateTemplatePrivateLinkTokenView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Templates"],
        operation_id="rotate_template_private_link_token",
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The slug of the template whose private link is "
                "regenerated.",
            ),
        ],
        description=(
            "Replaces the token of the private link of a user template owned by "
            "the user, which takes the access away from everybody who has the old "
            "link. The new token is in `private_link_token`. A template without a "
            "private link keeps having none. The private link of a blocked "
            "template can't be changed."
        ),
        request=None,
        responses={
            200: TemplateListItemSerializer,
            400: get_error_schema(["ERROR_TEMPLATE_BLOCKED"]),
            401: None,
            404: get_error_schema(["ERROR_TEMPLATE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
            TemplateBlocked: ERROR_TEMPLATE_PRIVATE_LINK_BLOCKED,
        }
    )
    def post(self, request: Request, slug: str) -> Response:
        """Regenerates the private link of a user template owned by the user."""

        revision = action_type_registry.get_by_type(
            RotateUserTemplatePrivateLinkActionType
        ).do(request.user, get_template_id(slug))
        return Response(
            TemplateListItemSerializer(revision, context={"request": request}).data
        )


class DownloadUserTemplateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Templates"],
        operation_id="download_template",
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The slug of the user template to download.",
            ),
            TEMPLATE_PRIVATE_LINK_SCHEMA_PARAMETER,
        ],
        description=(
            "Responds with the URL of the archive of a user template, which imports "
            "like a workspace export. The archive is built on the first download: "
            "while there is none, a job that builds it is started instead, or the "
            "one of the user that builds it already is responded with. Once the "
            "job is finished, the archive is asked for again.\n\n"
            "A user template can be downloaded by whoever can install it. Its "
            "owner and the instance admins may download any revision of it. Anyone "
            "else downloads the public revision, or the latest one of a template "
            "that isn't public with the token of its private link in the "
            "`Baserow-Template-Authorization` header: when "
            "another revision than the one shown is that one since, "
            "`ERROR_TEMPLATE_UPDATED` is responded with."
        ),
        request=DownloadTemplateSerializer,
        responses={
            200: TemplateArchiveSerializer,
            202: DownloadUserTemplateJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_TEMPLATE_BLOCKED",
                    "ERROR_TEMPLATE_HAS_NO_CONTENT",
                    "ERROR_TEMPLATE_UPDATED",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_TEMPLATE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
            TemplateBlocked: ERROR_TEMPLATE_BLOCKED,
            TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
            TemplateUpdated: ERROR_TEMPLATE_UPDATED,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(DownloadTemplateSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request: Request, slug: str, data: Dict[str, Any]) -> Response:
        """
        Responds with the archive of a user template, or the job building it.

        :param request: The request of the user who downloads the template.
        :param slug: The slug of the template.
        :param data: The validated body, with the `revision_id` the user was shown.
        :return: The URL of the archive, or the job that builds it.
        """

        revision = UserTemplateHandler().get_downloadable_revision(
            request.user,
            slug,
            data["revision_id"],
            private_link_token=get_private_link_token(),
        )
        if has_valid_archive(revision):
            archive = {
                "url": template_archive_url(revision),
                "file_name": template_archive_file_name(revision),
            }
            return Response(TemplateArchiveSerializer(archive).data)

        # A repeated click gets the build that runs already.
        job = (
            DownloadUserTemplateJob.objects.filter(user=request.user, revision=revision)
            .is_pending_or_running()
            .select_related("revision__root")
            .first()
        )
        if job is None:
            job = JobHandler().create_and_start_job(
                request.user,
                DownloadUserTemplateJobType.type,
                slug=slug,
                revision_id=revision.id,
            )
        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
