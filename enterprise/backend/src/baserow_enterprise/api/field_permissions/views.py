from django.db import transaction
from django.db.models import Case, CharField, Count, F, IntegerField, Q, Value, When

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.fields.handler import FieldDoesNotExist, FieldHandler
from baserow.contrib.database.fields.operations import ReadFieldOperationType
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.api.errors import (
    ERROR_SUBJECT_DOES_NOT_EXIST,
    ERROR_SUBJECT_TYPE_UNSUPPORTED,
)
from baserow_enterprise.exceptions import SubjectNotExist, SubjectUnsupported
from baserow_enterprise.features import FIELD_LEVEL_PERMISSIONS
from baserow_enterprise.field_permissions.actions import (
    UpdateFieldPermissionsActionType,
)
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.operations import (
    ReadFieldPermissionsOperationType,
)
from baserow_enterprise.teams.models import Team
from baserow_enterprise.teams.subjects import TeamSubjectType
from baserow_premium.license.handler import LicenseHandler

from .serializers import (
    FieldPermissionSubjectOptionResponseSerializer,
    FieldPermissionSubjectOptionsRequestSerializer,
    UpdateFieldPermissionsRequestSerializer,
    UpdateFieldPermissionsResponseSerializer,
)


class FieldPermissionsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the field to update the permissions for.",
            ),
        ],
        tags=["Field permissions"],
        operation_id="update_field_permissions",
        description=(
            "Update permissions for writing field values and form visibility for a specific field. "
            "This endpoint is used to restrict the ability to modify field values to the roles defined. "
            "It also makes it possible to decide if the field can be exposed in forms or not."
            "\n\nThis is a **enterprise** feature."
        ),
        request=UpdateFieldPermissionsRequestSerializer,
        responses={
            200: UpdateFieldPermissionsResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_SUBJECT_TYPE_UNSUPPORTED",
                ]
            ),
            404: get_error_schema(
                ["ERROR_FIELD_DOES_NOT_EXIST", "ERROR_SUBJECT_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            SubjectNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            SubjectUnsupported: ERROR_SUBJECT_TYPE_UNSUPPORTED,
        }
    )
    @validate_body(UpdateFieldPermissionsRequestSerializer, return_validated=True)
    @transaction.atomic
    def patch(self, request: Request, field_id: int, data) -> Response:
        """
        Update permissions for writing field values and form visibility for a specific
        field.
        """

        action_type = action_type_registry.get_by_type(UpdateFieldPermissionsActionType)
        field = action_type.get_field_for_update(field_id)
        workspace = field.table.database.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(
            FIELD_LEVEL_PERMISSIONS, request.user, workspace
        )

        role = data["role"]
        allow_in_forms = data.get("allow_in_forms", False)
        subjects = data.get("subjects")
        updated_permissions = action_type.do(
            request.user, field, role, allow_in_forms, subjects
        )
        serializer = UpdateFieldPermissionsResponseSerializer(
            {
                "field_id": field.id,
                "role": updated_permissions.role,
                "allow_in_forms": updated_permissions.allow_in_forms,
                "can_write_values": updated_permissions.can_write_values,
                "subjects": updated_permissions.subjects,
            }
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the field to get the permissions for.",
            ),
        ],
        tags=["Field permissions"],
        operation_id="get_field_permissions",
        description=(
            "Retrieve the permissions for writing field values and form visibility of a specific field."
            "\n\nThis is a **enterprise** feature."
        ),
        responses={
            200: UpdateFieldPermissionsResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_FIELD_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, field_id) -> Response:
        """
        Retrieve the permissions for writing field values and form visibility of a
        specific field.
        """

        field = FieldHandler().get_field(field_id)

        workspace = field.table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ReadFieldOperationType.type,
            workspace=workspace,
            context=field,
        )

        LicenseHandler.raise_if_user_doesnt_have_feature(
            FIELD_LEVEL_PERMISSIONS, request.user, workspace
        )

        field_permissions = FieldPermissionsHandler.get_field_permissions(
            request.user, field
        )

        serializer = UpdateFieldPermissionsResponseSerializer(
            {
                "field_id": field.id,
                "role": field_permissions.role,
                "allow_in_forms": field_permissions.allow_in_forms,
                "subjects": field_permissions.subjects,
            }
        )
        return Response(serializer.data)


class FieldPermissionSubjectOptionsView(APIView):
    @extend_schema(
        parameters=[FieldPermissionSubjectOptionsRequestSerializer],
        tags=["Field permissions"],
        operation_id="list_field_permission_subject_options",
        description=(
            "Searches users and teams that can be selected for a field-specific "
            "permission. Results are paginated and exclude the requested subjects."
            "\n\nThis is an **enterprise** feature."
        ),
        responses={
            200: get_example_pagination_serializer_class(
                FieldPermissionSubjectOptionResponseSerializer
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_query_parameters(FieldPermissionSubjectOptionsRequestSerializer)
    def get(self, request, field_id, query_params) -> Response:
        field = FieldHandler().get_field(field_id)
        workspace = field.table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ReadFieldPermissionsOperationType.type,
            workspace=workspace,
            context=field,
        )
        LicenseHandler.raise_if_user_doesnt_have_feature(
            FIELD_LEVEL_PERMISSIONS, request.user, workspace
        )

        search = (query_params.get("search") or "").strip()
        users = WorkspaceUser.objects.filter(
            workspace=workspace,
            user__is_active=True,
            user__profile__to_be_deleted=False,
        ).exclude(user_id__in=query_params["exclude_user_ids"])
        teams = Team.objects.filter(workspace=workspace).exclude(
            id__in=query_params["exclude_team_ids"]
        )
        if search:
            users = users.filter(
                Q(user__first_name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
            )
            teams = teams.filter(name__icontains=search)

        user_options = users.annotate(
            subject_id=F("user_id"),
            subject_type=Value(UserSubjectType.type, output_field=CharField()),
            name=Case(
                When(user__first_name="", then=F("user__email")),
                default=F("user__first_name"),
                output_field=CharField(),
            ),
            email=F("user__email"),
            subject_count=Value(None, output_field=IntegerField()),
        ).values("subject_id", "subject_type", "name", "email", "subject_count")
        team_options = teams.annotate(
            subject_id=F("id"),
            subject_type=Value(TeamSubjectType.type, output_field=CharField()),
            email=Value(None, output_field=CharField()),
            subject_count=Count("subjects"),
        ).values("subject_id", "subject_type", "name", "email", "subject_count")
        options = user_options.union(team_options, all=True).order_by(
            "name", "subject_type", "subject_id"
        )

        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(options, request, view=self)
        serializer = FieldPermissionSubjectOptionResponseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
