from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.admin.views import AdminListingView
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.schemas import get_error_schema
from baserow.api.templates.errors import (
    ERROR_TEMPLATE_ALREADY_APPROVED,
    ERROR_TEMPLATE_ALREADY_REJECTED,
    ERROR_TEMPLATE_BLOCKED_REVIEW,
    ERROR_TEMPLATE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_HAS_NO_CONTENT,
    ERROR_TEMPLATE_NOT_REVIEWABLE,
    ERROR_TEMPLATE_UPDATED,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    ApproveUserTemplateAdminActionType,
    RejectUserTemplateAdminActionType,
)
from baserow.core.user_templates.constants import USER_TEMPLATE_ADMIN_STATES
from baserow.core.user_templates.exceptions import (
    TemplateAlreadyApproved,
    TemplateAlreadyRejected,
    TemplateBlocked,
    TemplateHasNoContent,
    TemplateNotReviewable,
    TemplateUpdated,
)
from baserow.core.user_templates.handler import UserTemplateHandler

from .serializers import (
    AdminApproveUserTemplateSerializer,
    AdminRejectUserTemplateSerializer,
    AdminUserTemplateCountsSerializer,
    AdminUserTemplateSerializer,
    AdminUserTemplatesQueryParamsSerializer,
)

TEMPLATE_ID_PATH_PARAMETER = OpenApiParameter(
    name="template_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the template.",
)
REVIEW_RESPONSES = {
    200: AdminUserTemplateSerializer,
    400: get_error_schema(
        [
            "ERROR_REQUEST_BODY_VALIDATION",
            "ERROR_TEMPLATE_BLOCKED",
            "ERROR_TEMPLATE_UPDATED",
            "ERROR_TEMPLATE_ALREADY_APPROVED",
            "ERROR_TEMPLATE_ALREADY_REJECTED",
            "ERROR_TEMPLATE_NOT_REVIEWABLE",
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ]
    ),
    401: None,
    404: get_error_schema(["ERROR_TEMPLATE_DOES_NOT_EXIST"]),
}
REVIEW_EXCEPTIONS = {
    TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
    TemplateBlocked: ERROR_TEMPLATE_BLOCKED_REVIEW,
    TemplateUpdated: ERROR_TEMPLATE_UPDATED,
    TemplateAlreadyApproved: ERROR_TEMPLATE_ALREADY_APPROVED,
    TemplateAlreadyRejected: ERROR_TEMPLATE_ALREADY_REJECTED,
    TemplateNotReviewable: ERROR_TEMPLATE_NOT_REVIEWABLE,
    TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
}


def serialize_admin_row(revision: Template) -> dict:
    """The row of the template of the revision in the admin templates list."""

    row = (
        UserTemplateHandler()
        .list_templates_for_admin()
        .filter_by_root(id=revision.get_root().id)
        .get()
    )
    return AdminUserTemplateSerializer(row).data


class AdminUserTemplatesView(AdminListingView):
    serializer_class = AdminUserTemplateSerializer
    search_fields = []
    filters_field_mapping = {"state": "admin_state"}
    sort_field_mapping = {
        "name": "name",
        "author": "author_first_name",
        "updated_on": "template_updated_on",
    }

    def get_queryset(self, request):
        return (
            UserTemplateHandler()
            .list_templates_for_admin()
            .filter(admin_state__in=USER_TEMPLATE_ADMIN_STATES)
        )

    def apply_sorts_or_default_sort(self, sorts, queryset):
        queryset = super().apply_sorts_or_default_sort(sorts or "-updated_on", queryset)
        # Templates that sort the same keep their order between pages.
        return queryset.order_by(*queryset.query.order_by, "-id")

    def apply_ids_filter(self, ids_param, queryset):
        if not ids_param:
            return queryset
        # The ids are of the templates, which are the roots of the listed revisions.
        roots = super().apply_ids_filter(ids_param, Template.objects.all())
        return queryset.filter_by_root(id__in=roots.values("id"))

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_user_templates",
        description="Returns the latest revision of every user template in review, "
        "public or rejected with its state, if the requesting user is staff.",
        **AdminListingView.get_extend_schema_parameters(
            "templates",
            serializer_class,
            search_fields,
            sort_field_mapping,
            extra_parameters=[
                OpenApiParameter(
                    name="state",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.STR,
                    enum=list(USER_TEMPLATE_ADMIN_STATES),
                    description="Only the templates in this state.",
                ),
            ],
            extra_responses={
                400: get_error_schema(
                    [
                        "ERROR_PAGE_SIZE_LIMIT",
                        "ERROR_INVALID_SORT_DIRECTION",
                        "ERROR_INVALID_SORT_ATTRIBUTE",
                        "ERROR_QUERY_PARAMETER_VALIDATION",
                    ]
                ),
            },
        ),
    )
    @map_exceptions()
    @validate_query_parameters(AdminUserTemplatesQueryParamsSerializer)
    def get(self, request, query_params):
        return super().get(request)


class AdminUserTemplateCountsView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_count_user_templates",
        description="Returns how many user templates are in review, public and "
        "rejected, if the requesting user is staff.",
        responses={200: AdminUserTemplateCountsSerializer, 401: None},
    )
    def get(self, request):
        return Response(UserTemplateHandler().count_templates_for_admin())


class AdminApproveUserTemplateView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_approve_user_template",
        description="Approves a user template in review or rejected, if the "
        "requesting user is staff: the revision they reviewed, which must still be "
        "the latest one, is listed for everybody on this instance in place of the "
        "one listed until then. The state they saw, and whether it was listed, "
        "must still be the template's.",
        parameters=[TEMPLATE_ID_PATH_PARAMETER],
        request=AdminApproveUserTemplateSerializer,
        responses=REVIEW_RESPONSES,
    )
    @map_exceptions(REVIEW_EXCEPTIONS)
    @validate_body(AdminApproveUserTemplateSerializer)
    def post(self, request, data, template_id):
        revision = action_type_registry.get_by_type(
            ApproveUserTemplateAdminActionType
        ).do(
            request.user,
            int(template_id),
            data["revision_id"],
            data["state"],
            data["listed"],
        )
        return Response(serialize_admin_row(revision))


class AdminRejectUserTemplateView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_reject_user_template",
        description="Rejects a user template in review, or a listed one, which "
        "takes it out of the listing, if the requesting user is staff. A listed "
        "template whose edit is in review stays listed: only the edit is rejected. "
        "The revision they reviewed must still be the latest one, and the state they "
        "saw, and whether it was listed, must still be the template's. Its author "
        "sees the reason, and making it public again sends it to review.",
        parameters=[TEMPLATE_ID_PATH_PARAMETER],
        request=AdminRejectUserTemplateSerializer,
        responses=REVIEW_RESPONSES,
    )
    @map_exceptions(REVIEW_EXCEPTIONS)
    @validate_body(AdminRejectUserTemplateSerializer)
    def post(self, request, data, template_id):
        revision = action_type_registry.get_by_type(
            RejectUserTemplateAdminActionType
        ).do(
            request.user,
            int(template_id),
            data["revision_id"],
            data["reason"],
            data["state"],
            data["listed"],
        )
        return Response(serialize_admin_row(revision))
