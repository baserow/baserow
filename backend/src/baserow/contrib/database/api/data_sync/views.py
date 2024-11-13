from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body_custom_fields
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.database.api.tables.serializers import TableSerializer
from baserow.contrib.database.data_sync.actions import CreateDataSyncTableActionType
from baserow.contrib.database.data_sync.exceptions import (
    DataSyncDoesNotExist,
    PropertyNotFound,
    SyncError,
)
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.handler import DatabaseHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.utils import extract_allowed

from .errors import (
    ERROR_DATA_SYNC_DOES_NOT_EXIST,
    ERROR_PROPERTY_NOT_FOUND,
    ERROR_SYNC_ERROR,
)
from .serializers import (
    CreateDataSyncSerializer,
    ListDataSyncPropertiesRequestSerializer,
    ListDataSyncPropertySerializer,
)


class DataSyncsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="database_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a data sync table for the database related to the"
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="create_database_data_sync_table",
        description=(
            "Creates a new data sync table with the given data sync type. This will "
            "technically create a table, but it's synchronized with the provided data "
            "sync information. This means that some fields related to it will "
            "automatically be created and will be read-only."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            data_sync_type_registry, CreateDataSyncSerializer
        ),
        responses={
            200: TableSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_SYNC_ERROR",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body_custom_fields(
        data_sync_type_registry,
        base_serializer_class=CreateDataSyncSerializer,
        return_validated=True,
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            PropertyNotFound: ERROR_PROPERTY_NOT_FOUND,
            SyncError: ERROR_SYNC_ERROR,
        }
    )
    def post(
        self,
        request: Request,
        data,
        database_id: int,
    ):
        """Creates a new data sync table for the provided user."""

        database = DatabaseHandler().get_database(database_id)
        type_name = data.pop("type")
        data_sync = action_type_registry.get_by_type(CreateDataSyncTableActionType).do(
            request.user, database, type_name, **data
        )

        serializer = TableSerializer(data_sync.table)
        return Response(serializer.data)


class SyncDataSyncTableView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_sync_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Starts a job to sync the data sync table related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="sync_data_sync_table_async",
        description=(
            "Start a job to sync the data sync table with the provided `data_sync_id` "
            "parameter if the authorized user has access to the database's workspace."
        ),
        request=None,
        responses={
            202: SyncDataSyncTableJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_DATA_SYNC_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataSyncDoesNotExist: ERROR_DATA_SYNC_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request, data_sync_id):
        """Creates a job to sync the data sync table."""

        job = JobHandler().create_and_start_job(
            request.user, SyncDataSyncTableJobType.type, data_sync_id=data_sync_id
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class DataSyncPropertiesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Database tables"],
        operation_id="get_database_data_sync_properties",
        description=(
            "Lists all the properties of the provided data sync type given the request "
            "data. This can be used to choose which properties should be included when "
            "creating the data sync."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            data_sync_type_registry, ListDataSyncPropertiesRequestSerializer
        ),
        responses={
            200: ListDataSyncPropertySerializer(many=True),
            400: get_error_schema(
                [
                    "ERROR_SYNC_ERROR",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            SyncError: ERROR_SYNC_ERROR,
        }
    )
    @validate_body_custom_fields(
        data_sync_type_registry,
        base_serializer_class=ListDataSyncPropertiesRequestSerializer,
        return_validated=True,
    )
    def post(
        self,
        request: Request,
        data,
    ):
        """
        Lists the properties of the data sync related to the provided request data.
        """

        type_name = data.pop("type")

        data_sync_type = data_sync_type_registry.get(type_name)
        model_class = data_sync_type.model_class

        allowed_fields = [] + data_sync_type.allowed_fields
        values = extract_allowed(data, allowed_fields)
        values = data_sync_type.prepare_values(request.user, values)

        data_sync_instance = model_class(**values)
        data_sync_properties = data_sync_type.get_properties(data_sync_instance)

        serializer = ListDataSyncPropertySerializer(data_sync_properties, many=True)
        return Response(serializer.data)
