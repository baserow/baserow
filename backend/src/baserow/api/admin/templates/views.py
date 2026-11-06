from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import QuerySet

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
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
    ERROR_TEMPLATE_BLOCKED,
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
    TemplateBlocked: ERROR_TEMPLATE_BLOCKED,
    TemplateUpdated: ERROR_TEMPLATE_UPDATED,
    TemplateAlreadyApproved: ERROR_TEMPLATE_ALREADY_APPROVED,
    TemplateAlreadyRejected: ERROR_TEMPLATE_ALREADY_REJECTED,
    TemplateNotReviewable: ERROR_TEMPLATE_NOT_REVIEWABLE,
    TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
}


def serialize_admin_row(revision: Template) -> Dict[str, Any]:
    """
    Serializes the row of a template on the admin page after it was reviewed.

    :param revision: The reviewed revision, with its root.
    :return: The row in the tab of the template's state now.
    """

    handler = UserTemplateHandler()
    root = revision.get_root()
    state, _ = handler.get_template_state(root)
    row = (
        handler.list_templates_for_admin(state)
        .filter_by_root(id=root.id)
        .prefetch_related("categories")
        .get()
    )
    return AdminUserTemplateSerializer(row).data


class AdminUserTemplatesView(AdminListingView):
    serializer_class = AdminUserTemplateSerializer
    search_fields = []
    sort_field_mapping = {
        "name": "name",
        "author": "author_name",
        "updated_on": "template_updated_on",
    }

    def get_queryset(self, request: Request) -> QuerySet[Template]:
        """
        Returns the rows of the requested tab, see `list_templates_for_admin`.

        :param request: The request, with a valid `state` query parameter.
        :return: The rows of the tab of the state.
        """

        return (
            UserTemplateHandler()
            .list_templates_for_admin(request.GET["state"])
            .prefetch_related("categories")
        )

    def apply_sorts_or_default_sort(
        self, sorts: Optional[str], queryset: QuerySet[Template]
    ) -> QuerySet[Template]:
        """
        Sorts the rows, by last update unless asked otherwise.

        :param sorts: The sorts of the request, if any.
        :param queryset: The rows to sort.
        :return: The rows, by the sorts or by last update.
        """

        queryset = super().apply_sorts_or_default_sort(sorts or "-updated_on", queryset)
        # Templates that sort the same keep their order between pages.
        return queryset.order_by(*queryset.query.order_by, "-id")

    def apply_ids_filter(
        self, ids_param: Optional[str], queryset: QuerySet[Template]
    ) -> QuerySet[Template]:
        """
        Filters the rows by the ids of their templates, not of their revisions.

        :param ids_param: The ids of the templates, which are their roots.
        :param queryset: The rows to filter.
        :return: The rows of these templates.
        """

        if not ids_param:
            return queryset
        roots = super().apply_ids_filter(ids_param, Template.objects.all())
        return queryset.filter_by_root(id__in=roots.values("id"))

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_user_templates",
        description="Returns the user templates in review, public or rejected, if "
        "the requesting user is staff: the revision under review of a template in "
        "review or rejected, otherwise its public revision.",
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
                    required=True,
                    description="The state of the templates.",
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
    def get(self, request: Request, query_params: Dict[str, Any]) -> Response:
        """Responds with a page of the rows of the requested tab."""

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
    def get(self, request: Request) -> Response:
        """Responds with the number of rows of each tab."""

        return Response(UserTemplateHandler().count_templates_for_admin())


class AdminApproveUserTemplateView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_approve_user_template",
        description="Approves a user template in review or rejected, if the "
        "requesting user is staff: the revision they reviewed is listed for "
        "everybody on this instance in place of the one listed until then. It must "
        "still be the revision under review, have content, and not be edited since "
        "it was submitted, and the state they saw, and whether it was listed, must "
        "still be the template's.",
        parameters=[TEMPLATE_ID_PATH_PARAMETER],
        request=AdminApproveUserTemplateSerializer,
        responses=REVIEW_RESPONSES,
    )
    @map_exceptions(REVIEW_EXCEPTIONS)
    @validate_body(AdminApproveUserTemplateSerializer)
    # Built under the root's lock, so a deletion can't commit before the response.
    @transaction.atomic
    def post(
        self, request: Request, data: Dict[str, Any], template_id: str
    ) -> Response:
        """Approves the template and responds with its row in its tab now."""

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
        description="Rejects a user template in review, or a listed one, if the "
        "requesting user is staff. A listed template is taken out of the listing, "
        "unless only its edit is in review: then only the edit is rejected. The "
        "revision they reviewed must still be the template's row, and the state "
        "they saw, and whether it was listed, must still be the template's. Its "
        "author sees the reason, and its next submit goes to review.",
        parameters=[TEMPLATE_ID_PATH_PARAMETER],
        request=AdminRejectUserTemplateSerializer,
        responses=REVIEW_RESPONSES,
    )
    @map_exceptions(REVIEW_EXCEPTIONS)
    @validate_body(AdminRejectUserTemplateSerializer)
    # Built under the root's lock, so a deletion can't commit before the response.
    @transaction.atomic
    def post(
        self, request: Request, data: Dict[str, Any], template_id: str
    ) -> Response:
        """Rejects the template and responds with its row in its tab now."""

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
