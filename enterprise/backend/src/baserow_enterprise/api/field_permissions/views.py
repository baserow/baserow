from urllib.request import Request

from django.db import transaction

from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.fields.handler import FieldDoesNotExist, FieldHandler
from baserow.contrib.database.fields.operations import ReadFieldOperationType
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow_enterprise.features import FIELD_LEVEL_PERMISSIONS
from baserow_enterprise.field_permissions.actions import (
    UpdateFieldPermissionsActionType,
)
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler

from .serializers import (
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
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
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
        updated_permissions = action_type.do(request.user, field, role, allow_in_forms)
        serializer = UpdateFieldPermissionsResponseSerializer(
            {
                "field_id": field.id,
                "role": updated_permissions.role,
                "allow_in_forms": updated_permissions.allow_in_forms,
                "can_write_values": updated_permissions.can_write_values,
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

        serializer = UpdateFieldPermissionsResponseSerializer(field_permissions)
        return Response(serializer.data)
