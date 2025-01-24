from django.db import transaction

from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.api.data_sync.errors import ERROR_DATA_SYNC_DOES_NOT_EXIST
from baserow.contrib.database.data_sync.exceptions import DataSyncDoesNotExist
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.data_sync.operations import (
    GetIncludingPublicValuesOperationType,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow_enterprise.data_sync.actions import (
    UpdatePeriodicDataSyncIntervalActionType,
)
from baserow_enterprise.data_sync.models import DATA_SYNC_INTERVAL_MANUAL

from ...features import DATA_SYNC
from .serializers import PeriodicDataSyncIntervalSerializer


class PeriodicDataSyncIntervalView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_sync_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The data sync where to fetch the periodic settings for.",
            ),
        ],
        tags=["Database tables"],
        operation_id="get_periodic_data_sync_interval",
        description=(
            "Responds with the periodic data sync interval data, if the user has the "
            "right permissions."
            "\nThis is an **enterprise** feature."
        ),
        responses={
            200: PeriodicDataSyncIntervalSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_DATA_SYNC_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DataSyncDoesNotExist: ERROR_DATA_SYNC_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, data_sync_id):
        """Responds with the periodic data sync interval."""

        data_sync = DataSyncHandler().get_data_sync(
            data_sync_id,
            base_queryset=DataSync.objects.select_related(
                "periodic_interval", "table__database__workspace"
            ),
        )

        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, data_sync.table.database.workspace
        )

        CoreHandler().check_permissions(
            request.user,
            GetIncludingPublicValuesOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )

        if not hasattr(data_sync, "periodic_interval"):
            periodic_interval = {
                "interval": DATA_SYNC_INTERVAL_MANUAL,
                "when": None,
                "automatically_deactivated": False,
            }
        else:
            periodic_interval = data_sync.periodic_interval

        serializer = PeriodicDataSyncIntervalSerializer(periodic_interval)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_sync_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the data sync related to the provided value.",
            ),
        ],
        tags=["Database tables"],
        operation_id="update_periodic_data_sync_interval",
        description=(
            "Updates the periodic data sync interval, if the user has "
            "the right permissions."
            "\nThis is an **enterprise** feature."
        ),
        request=PeriodicDataSyncIntervalSerializer,
        responses={
            200: PeriodicDataSyncIntervalSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_DATA_SYNC_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataSyncDoesNotExist: ERROR_DATA_SYNC_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(PeriodicDataSyncIntervalSerializer, return_validated=True)
    def patch(self, request, data_sync_id, data):
        """Updates the periodic data sync interval."""

        data_sync = DataSyncHandler().get_data_sync(
            data_sync_id,
            base_queryset=DataSync.objects.select_for_update(
                of=("self",)
            ).select_related("table__database__workspace"),
        )

        periodic_interval = action_type_registry.get_by_type(
            UpdatePeriodicDataSyncIntervalActionType
        ).do(user=request.user, data_sync=data_sync, **data)

        serializer = PeriodicDataSyncIntervalSerializer(periodic_interval)
        return Response(serializer.data)
