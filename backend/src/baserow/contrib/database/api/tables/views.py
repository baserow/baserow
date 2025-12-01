from django.conf import settings
from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.contrib.database.api.fields.errors import (
    ERROR_INVALID_BASEROW_FIELD_NAME,
    ERROR_MAX_FIELD_COUNT_EXCEEDED,
    ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED,
    ERROR_RESERVED_BASEROW_FIELD_NAME,
)
from baserow.contrib.database.api.tokens.authentications import TokenAuthentication
from baserow.contrib.database.fields.exceptions import (
    InvalidBaserowFieldName,
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    ReservedBaserowFieldNameException,
)
from baserow.contrib.database.file_import.job_types import FileImportJobType
from baserow.contrib.database.handler import DatabaseHandler
from baserow.contrib.database.operations import (
    CreateTableDatabaseTableOperationType,
    ListTablesDatabaseTableOperationType,
)
from baserow.contrib.database.table.actions import (
    CreateTableActionType,
    DeleteTableActionType,
    OrderTableActionType,
    UpdateTableActionType,
)
from baserow.contrib.database.table.exceptions import (
    InitialSyncTableDataLimitExceeded,
    InitialTableDataDuplicateName,
    InitialTableDataLimitExceeded,
    InvalidInitialTableData,
    TableDoesNotExist,
    TableNotInDatabase,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.job_types import DuplicateTableJobType
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ImportRowsDatabaseTableOperationType,
    ReadDatabaseTableOperationType,
)
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem

from .errors import (
    ERROR_INITIAL_SYNC_TABLE_DATA_LIMIT_EXCEEDED,
    ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES,
    ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED,
    ERROR_INVALID_INITIAL_TABLE_DATA,
    ERROR_TABLE_DOES_NOT_EXIST,
    ERROR_TABLE_NOT_IN_DATABASE,
)
from .serializers import (
    OrderTablesSerializer,
    TableCreateSerializer,
    TableImportSerializer,
    TableSerializer,
    TableUpdateSerializer,
    TableWithoutDataSyncSerializer,
)


class AllTablesView(APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Database tables"],
        operation_id="list_all_token_tables",
        description=(
            "This endpoint only works in combination with the token authentication. It "
            "lists all the tables that the token has either create, read, update or "
            "delete access to."
        ),
        responses={
            200: TableWithoutDataSyncSerializer(many=True),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request):
        """Lists all the tables that token has access to."""

        token = TokenHandler().get_token_from_request(request)
        permissions = token.tokenpermission_set.all()
        tables_queryset = Table.objects.filter(
            database__workspace_id=token.workspace_id
        )

        if permissions.filter(database__isnull=True, table__isnull=True).exists():
            accessible_tables = tables_queryset
        else:
            accessible_tables = Table.objects.none()

            database_ids = permissions.filter(
                database__isnull=False, table__isnull=True
            ).values_list("database_id", flat=True)

            if database_ids:
                accessible_tables = accessible_tables | tables_queryset.filter(
                    database_id__in=database_ids
                )

            table_ids = permissions.filter(table__isnull=False).values_list(
                "table_id", flat=True
            )

            if table_ids:
                accessible_tables = accessible_tables | tables_queryset.filter(
                    id__in=table_ids
                )

        tables = CoreHandler().filter_queryset(
            request.user,
            ListTablesDatabaseTableOperationType.type,
            accessible_tables,
            workspace=token.workspace,
        )

        serializer = TableWithoutDataSyncSerializer(tables, many=True)
        return Response(serializer.data)


class TablesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="database_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only tables that are related to the provided "
                "value.",
            )
        ],
        tags=["Database tables"],
        operation_id="list_database_tables",
        description=(
            "Lists all the tables that are in the database related to the "
            "`database_id` parameter if the user has access to the database's workspace. "
            "A table is exactly as the name suggests. It can hold multiple fields, "
            "each having their own type and multiple rows. They can be added via the "
            "**create_database_table_field** and **create_database_table_row** "
            "endpoints."
        ),
        responses={
            200: TableSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, database_id):
        """Lists all the tables of a database."""

        database = DatabaseHandler().get_database(database_id)

        CoreHandler().check_permissions(
            request.user,
            ListTablesDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        tables = (
            Table.objects.filter(database=database)
            .select_related("data_sync")
            .prefetch_related("import_jobs")
            .prefetch_related("data_sync__synced_properties")
        )

        tables = CoreHandler().filter_queryset(
            request.user,
            ListTablesDatabaseTableOperationType.type,
            tables,
            workspace=database.workspace,
        )

        serializer = TableSerializer(tables, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="database_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a table for the database related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="create_database_table",
        description=(
            "Creates synchronously a new table for the database related to the "
            "provided `database_id` parameter if the authorized user has access to the "
            "database's workspace.\n\n"
            "As an alternative you can use the `create_async_database_table` for "
            "better performances and importing bigger files."
        ),
        request=TableCreateSerializer,
        responses={
            200: TableSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_INITIAL_TABLE_DATA",
                    "ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED",
                    "ERROR_RESERVED_BASEROW_FIELD_NAME",
                    "ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES",
                    "ERROR_INVALID_BASEROW_FIELD_NAME",
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
            InvalidInitialTableData: ERROR_INVALID_INITIAL_TABLE_DATA,
            InitialTableDataLimitExceeded: ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED,
            InitialSyncTableDataLimitExceeded: ERROR_INITIAL_SYNC_TABLE_DATA_LIMIT_EXCEEDED,
            MaxFieldLimitExceeded: ERROR_MAX_FIELD_COUNT_EXCEEDED,
            MaxFieldNameLengthExceeded: ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED,
            InitialTableDataDuplicateName: ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES,
            ReservedBaserowFieldNameException: ERROR_RESERVED_BASEROW_FIELD_NAME,
            InvalidBaserowFieldName: ERROR_INVALID_BASEROW_FIELD_NAME,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(TableCreateSerializer)
    def post(self, request, data, database_id):
        """Creates a new table in a database."""

        database = DatabaseHandler().get_database(database_id)

        CoreHandler().check_permissions(
            request.user,
            CreateTableDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        limit = settings.BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT
        if limit and len(data) > limit:
            raise InitialSyncTableDataLimitExceeded(
                f"It is not possible to import more than "
                f"{settings.BASEROW_INITIAL_CREATE_SYNC_TABLE_DATA_LIMIT} rows "
                "when creating a table synchronously. Use Asynchronous "
                "alternative instead."
            )

        table, _ = action_type_registry.get_by_type(CreateTableActionType).do(
            request.user,
            database,
            name=data["name"],
            data=data["data"],
            first_row_header=data["first_row_header"],
        )

        serializer = TableSerializer(table)
        return Response(serializer.data)


class AsyncCreateTableView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="database_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a table for the database related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="create_database_table_async",
        description=(
            "Creates a job that creates a new table for the database related to the "
            "provided `database_id` parameter if the authorized user has access to the "
            "database's workspace. This endpoint is asynchronous and return "
            "the created job to track the progress of the task."
        ),
        request=TableCreateSerializer,
        responses={
            202: FileImportJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
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
    @validate_body(TableCreateSerializer)
    def post(self, request, data, database_id):
        """Creates a job to create a new table in a database."""

        database = DatabaseHandler().get_database(database_id)

        CoreHandler().check_permissions(
            request.user,
            CreateTableDatabaseTableOperationType.type,
            workspace=database.workspace,
            context=database,
        )

        file_import_job = JobHandler().create_and_start_job(
            request.user,
            "file_import",
            database=database,
            name=data["name"],
            data=data["data"],
            first_row_header=data["first_row_header"],
            sync=True if data["data"] is None else False,
        )

        serializer = job_type_registry.get_serializer(file_import_job, JobSerializer)
        return Response(serializer.data)


class TableView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the table related to the provided value.",
            )
        ],
        tags=["Database tables"],
        operation_id="get_database_table",
        description=(
            "Returns the requested table if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            200: TableSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, table_id):
        """Responds with a serialized table instance."""

        table = TableHandler().get_table(table_id)

        CoreHandler().check_permissions(
            request.user,
            ReadDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        serializer = TableSerializer(table)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the table related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="update_database_table",
        description=(
            "Updates the existing table if the authorized user has access to the "
            "related database's workspace."
        ),
        request=TableUpdateSerializer,
        responses={
            200: TableSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(TableUpdateSerializer)
    def patch(self, request, data, table_id):
        """Updates the values a table instance."""

        table = action_type_registry.get_by_type(UpdateTableActionType).do(
            request.user,
            TableHandler().get_table(table_id),
            name=data["name"],
        )

        serializer = TableSerializer(table)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the table related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="delete_database_table",
        description=(
            "Deletes the existing table if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM"]
            ),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    def delete(self, request, table_id):
        """Deletes an existing table."""

        action_type_registry.get_by_type(DeleteTableActionType).do(
            request.user,
            TableHandler().get_table(
                table_id,
            ),
        )

        return Response(status=204)


class AsyncTableImportView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Import data into the table related to the provided value.",
            )
        ],
        tags=["Database tables"],
        operation_id="import_data_database_table_async",
        description=(
            "Import data in the specified table if the authorized user has access to "
            "the related database's workspace. This endpoint is asynchronous and return "
            "the created job to track the progress of the task."
        ),
        request=TableImportSerializer,
        responses={
            202: FileImportJobType().response_serializer_class,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(TableImportSerializer)
    def post(self, request, data, table_id):
        """Import data into an existing table"""

        table_handler = TableHandler()
        table = table_handler.get_table(table_id)

        CoreHandler().check_permissions(
            request.user,
            ImportRowsDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )
        configuration = data.get("configuration")
        data = data["data"]
        file_import_job = JobHandler().create_and_start_job(
            request.user,
            "file_import",
            data=data,
            table=table,
            configuration=configuration,
        )

        serializer = job_type_registry.get_serializer(file_import_job, JobSerializer)
        return Response(serializer.data)


class OrderTablesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="database_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the order of the tables in the database related "
                "to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="order_database_tables",
        description=(
            "Changes the order of the provided table ids to the matching position that "
            "the id has in the list. If the authorized user does not belong to the "
            "workspace it will be ignored. The order of the not provided tables will be "
            "set to `0`."
        ),
        request=OrderTablesSerializer,
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_TABLE_NOT_IN_DATABASE"]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(OrderTablesSerializer)
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableNotInDatabase: ERROR_TABLE_NOT_IN_DATABASE,
        }
    )
    def post(self, request, data, database_id):
        """Updates to order of the tables in a table."""

        database = DatabaseHandler().get_database(database_id)

        action_type_registry.get_by_type(OrderTableActionType).do(
            request.user, database, data["table_ids"]
        )

        return Response(status=204)


class AsyncDuplicateTableView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table to duplicate.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database tables"],
        operation_id="duplicate_database_table_async",
        description=(
            "Start a job to duplicate the table with the provided `table_id` parameter "
            "if the authorized user has access to the database's workspace."
        ),
        request=None,
        responses={
            202: DuplicateTableJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request, table_id):
        """Creates a job to duplicate a table in a database."""

        job = JobHandler().create_and_start_job(
            request.user, DuplicateTableJobType.type, table_id=table_id
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
