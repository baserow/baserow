from django.db import transaction
from django.db.models import Prefetch

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.admin.views import APIListingView
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import WorkspaceDoesNotExist
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Workspace
from baserow_enterprise.api.admin.data_scanner.errors import (
    ERROR_DATA_SCAN_ALREADY_RUNNING,
    ERROR_DATA_SCAN_DOES_NOT_EXIST,
    ERROR_DATA_SCAN_RESULT_DOES_NOT_EXIST,
)
from baserow_enterprise.api.admin.data_scanner.serializers import (
    DataScanCreateSerializer,
    DataScanResultExportJobRequestSerializer,
    DataScanResultExportJobResponseSerializer,
    DataScanResultSerializer,
    DataScanSerializer,
    DataScanUpdateSerializer,
    WorkspaceStructureDatabaseSerializer,
)
from baserow_enterprise.data_scanner.actions import (
    CreateDataScanActionType,
    DeleteDataScanActionType,
    UpdateDataScanActionType,
)
from baserow_enterprise.data_scanner.constants import SCANNABLE_FIELD_CONTENT_TYPES
from baserow_enterprise.data_scanner.exceptions import (
    DataScanDoesNotExist,
    DataScanIsAlreadyRunning,
    DataScanResultDoesNotExist,
)
from baserow_enterprise.data_scanner.handler import DataScannerHandler
from baserow_enterprise.data_scanner.job_types import DataScanResultExportJobType
from baserow_enterprise.data_scanner.models import DataScanResult
from baserow_enterprise.features import DATA_SCANNER
from baserow_premium.license.handler import LicenseHandler


class DataScanListView(APIListingView):
    permission_classes = (IsAdminUser,)
    serializer_class = DataScanSerializer
    search_fields = ["name"]
    sort_field_mapping = {
        "name": "name",
        "scan_type": "scan_type",
        "frequency": "frequency",
        "created_on": "created_on",
    }
    default_order_by = "created_on"

    def get_queryset(self, request):
        return DataScannerHandler.list_scans(request.user)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_list_scans",
        description=(
            "Lists all data scans configured for this Baserow instance. Data scans "
            "allow administrators to search the entire instance for sensitive data "
            "matching a pattern, a list of uploaded values, or values from another "
            "Baserow table. **Enterprise feature.**"
        ),
        **APIListingView.get_extend_schema_parameters(
            "data scans",
            DataScanSerializer,
            ["name"],
            sort_field_mapping,
        ),
    )
    def get(self, request):
        return super().get(request)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_create_scan",
        description=(
            "Creates a new data scan. A data scan searches the Baserow instance "
            "for sensitive data matching a pattern (e.g. credit card numbers), a "
            "list of uploaded values, or values sourced from another Baserow table. "
            "**Enterprise feature.**"
        ),
        request=DataScanCreateSerializer,
        responses={200: DataScanSerializer},
    )
    @transaction.atomic
    @validate_body(DataScanCreateSerializer)
    def post(self, request, data):
        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            DATA_SCANNER, request.user
        )
        scan = action_type_registry.get_by_type(CreateDataScanActionType).do(
            user=request.user,
            name=data["name"],
            scan_type=data["scan_type"],
            pattern=data.get("pattern"),
            frequency=data.get("frequency", "manual"),
            scan_all_workspaces=data.get("scan_all_workspaces", True),
            workspace_ids=data.get("workspace_ids", []),
            list_items=data.get("list_items", []),
            source_table_id=data.get("source_table_id"),
            source_field_id=data.get("source_field_id"),
            whole_words=data.get("whole_words", True),
        )
        return Response(DataScanSerializer(scan).data)


class DataScanDetailView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_get_scan",
        description=(
            "Returns a single data scan configuration. **Enterprise feature.**"
        ),
        responses={
            200: DataScanSerializer,
            404: get_error_schema(["ERROR_DATA_SCAN_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({DataScanDoesNotExist: ERROR_DATA_SCAN_DOES_NOT_EXIST})
    def get(self, request, scan_id):
        scan = DataScannerHandler.get_scan(user=request.user, scan_id=scan_id)
        return Response(DataScanSerializer(scan).data)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_update_scan",
        description=(
            "Updates a data scan configuration. When the scan type, pattern, or "
            "list items change, stale results are automatically cleaned up. "
            "**Enterprise feature.**"
        ),
        request=DataScanUpdateSerializer,
        responses={
            200: DataScanSerializer,
            404: get_error_schema(["ERROR_DATA_SCAN_DOES_NOT_EXIST"]),
            409: get_error_schema(["ERROR_DATA_SCAN_ALREADY_RUNNING"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataScanDoesNotExist: ERROR_DATA_SCAN_DOES_NOT_EXIST,
            DataScanIsAlreadyRunning: ERROR_DATA_SCAN_ALREADY_RUNNING,
        }
    )
    @validate_body(DataScanUpdateSerializer)
    def patch(self, request, scan_id, data):
        scan = action_type_registry.get_by_type(UpdateDataScanActionType).do(
            user=request.user,
            scan_id=scan_id,
            **data,
        )
        return Response(DataScanSerializer(scan).data)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_delete_scan",
        description=(
            "Deletes a data scan and all of its results. **Enterprise feature.**"
        ),
        responses={
            204: None,
            404: get_error_schema(["ERROR_DATA_SCAN_DOES_NOT_EXIST"]),
            409: get_error_schema(["ERROR_DATA_SCAN_ALREADY_RUNNING"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataScanDoesNotExist: ERROR_DATA_SCAN_DOES_NOT_EXIST,
            DataScanIsAlreadyRunning: ERROR_DATA_SCAN_ALREADY_RUNNING,
        }
    )
    def delete(self, request, scan_id):
        action_type_registry.get_by_type(DeleteDataScanActionType).do(
            user=request.user, scan_id=scan_id
        )
        return Response(status=HTTP_204_NO_CONTENT)


class DataScanTriggerView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_trigger_scan",
        description=(
            "Triggers an immediate run of the given data scan. The scan executes "
            "asynchronously and searches the configured workspaces for matches. "
            "**Enterprise feature.**"
        ),
        responses={
            202: DataScanSerializer,
            404: get_error_schema(["ERROR_DATA_SCAN_DOES_NOT_EXIST"]),
            409: get_error_schema(["ERROR_DATA_SCAN_ALREADY_RUNNING"]),
        },
    )
    @map_exceptions(
        {
            DataScanDoesNotExist: ERROR_DATA_SCAN_DOES_NOT_EXIST,
            DataScanIsAlreadyRunning: ERROR_DATA_SCAN_ALREADY_RUNNING,
        }
    )
    def post(self, request, scan_id):
        scan = DataScannerHandler.trigger_scan(user=request.user, scan_id=scan_id)
        return Response(DataScanSerializer(scan).data, status=HTTP_202_ACCEPTED)


class DataScanResultListView(APIListingView):
    permission_classes = (IsAdminUser,)
    serializer_class = DataScanResultSerializer
    search_fields = ["matched_value"]
    filters_field_mapping = {
        "scan_id": "scan_id",
    }
    sort_field_mapping = {
        "first_identified_on": "first_identified_on",
        "last_identified_on": "last_identified_on",
    }
    default_order_by = "-first_identified_on"

    def get_queryset(self, request):
        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            DATA_SCANNER, request.user
        )
        return DataScanResult.objects.select_related(
            "scan", "table__database", "field__table__database__workspace"
        ).all()

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_list_results",
        description=(
            "Lists all data scan results across all scans. Results represent "
            "individual matches found in database fields during scan execution. "
            "Can be filtered by scan_id and searched by matched value. "
            "**Enterprise feature.**"
        ),
        **APIListingView.get_extend_schema_parameters(
            "data scan results",
            DataScanResultSerializer,
            ["matched_value"],
            sort_field_mapping,
        ),
    )
    def get(self, request):
        return super().get(request)


class DataScanWorkspaceStructureView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_workspace_structure",
        description=(
            "Returns the database/table/field structure of a workspace for use "
            "in data scan configuration. Only text-compatible fields are included. "
            "**Enterprise feature.**"
        ),
        responses={
            200: WorkspaceStructureDatabaseSerializer(many=True),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST})
    def get(self, request, workspace_id):
        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            DATA_SCANNER, request.user
        )

        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            raise WorkspaceDoesNotExist()

        databases = (
            Database.objects.filter(workspace=workspace)
            .prefetch_related(
                Prefetch(
                    "table_set",
                    queryset=Table.objects.prefetch_related(
                        Prefetch(
                            "field_set",
                            queryset=Field.objects.filter(
                                content_type__model__in=SCANNABLE_FIELD_CONTENT_TYPES,
                            ).select_related("content_type"),
                        )
                    ),
                )
            )
            .order_by("order", "id")
        )

        serializer = WorkspaceStructureDatabaseSerializer(databases, many=True)
        return Response(serializer.data)


class DataScanResultExportView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_export_results",
        description=(
            "Creates a job to export data scan results to CSV. The exported file "
            "includes scan name, workspace, database, table, field, row ID, matched "
            "value, and timestamps for each result. **Enterprise feature.**"
        ),
        request=DataScanResultExportJobRequestSerializer,
        responses={
            202: DataScanResultExportJobResponseSerializer,
            400: get_error_schema(["ERROR_MAX_JOB_COUNT_EXCEEDED"]),
        },
    )
    @transaction.atomic
    @map_exceptions({MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED})
    @validate_body(DataScanResultExportJobRequestSerializer, return_validated=True)
    def post(self, request, data):
        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            DATA_SCANNER, request.user
        )
        job = JobHandler().create_and_start_job(
            request.user, DataScanResultExportJobType.type, **data
        )
        serializer = job_type_registry.get_serializer(
            job, JobSerializer, context={"request": request}
        )
        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class DataScanResultDeleteView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin data scanner"],
        operation_id="admin_data_scanner_delete_result",
        description=(
            "Deletes (resolves) a single data scan result, marking it as reviewed. "
            "**Enterprise feature.**"
        ),
        responses={
            204: None,
            404: get_error_schema(["ERROR_DATA_SCAN_RESULT_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions({DataScanResultDoesNotExist: ERROR_DATA_SCAN_RESULT_DOES_NOT_EXIST})
    def delete(self, request, result_id):
        DataScannerHandler.delete_result(user=request.user, result_id=result_id)
        return Response(status=HTTP_204_NO_CONTENT)
