from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.api.utils import DiscriminatorMappingSerializer, validate_data
from baserow.contrib.database.api.export.errors import (
    ERROR_EXPORT_JOB_DOES_NOT_EXIST,
    ERROR_TABLE_ONLY_EXPORT_UNSUPPORTED,
)
from baserow.contrib.database.api.export.serializers import (
    BaseExporterOptionsSerializer,
    ExportJobSerializer,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FILTER_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
)
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.api.views.errors import (
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
    ERROR_VIEW_NOT_IN_TABLE,
)
from baserow.contrib.database.export.exceptions import (
    ExportJobDoesNotExistException,
    TableOnlyExportUnsupported,
)
from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.export.models import ExportJob
from baserow.contrib.database.export.registries import table_exporter_registry
from baserow.contrib.database.fields.exceptions import (
    FilterFieldNotFound,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.exceptions import (
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
    ViewNotInTable,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import UserNotInWorkspace

User = get_user_model()

# A placeholder serializer only used to generate correct api documentation.
CreateExportJobSerializer = DiscriminatorMappingSerializer(
    "Export",
    lazy(table_exporter_registry.get_option_serializer_map, dict)(),
    type_field_name="exporter_type",
)


def _validate_options(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Looks up the exporter_type from the data, selects the correct export
    options serializer based on the exporter_type and finally validates the data using
    that serializer.

    :param data: A dict of data to serialize using an exporter options serializer.
    :return: validated export options data
    """

    option_serializers = table_exporter_registry.get_option_serializer_map()
    validated_exporter_type = validate_data(BaseExporterOptionsSerializer, data)
    serializer = option_serializers[validated_exporter_type["exporter_type"]]
    return validate_data(serializer, data)


class ExportTableView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table id to create and start an export job for",
            )
        ],
        tags=["Database table export"],
        operation_id="export_table",
        description=(
            "Creates and starts a new export job for a table given some exporter "
            "options. Returns an error if the requesting user does not have permissions"
            "to view the table."
        ),
        request=CreateExportJobSerializer,
        responses={
            200: ExportJobSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_TABLE_ONLY_EXPORT_UNSUPPORTED",
                    "ERROR_VIEW_UNSUPPORTED_FOR_EXPORT_TYPE",
                    "ERROR_VIEW_NOT_IN_TABLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                ]
            ),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_VIEW_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            TableOnlyExportUnsupported: ERROR_TABLE_ONLY_EXPORT_UNSUPPORTED,
            ViewNotInTable: ERROR_VIEW_NOT_IN_TABLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
        }
    )
    def post(self, request, table_id):
        """
        Starts a new export job for the provided table, view, export type and options.
        """

        table = TableHandler().get_table(table_id)

        option_data = _validate_options(request.data)

        view_id = option_data.pop("view_id", None)
        view = (
            ViewHandler().get_view_as_user(request.user, view_id) if view_id else None
        )

        job = ExportHandler.create_and_start_new_job(
            request.user, table, view, option_data
        )
        return Response(ExportJobSerializer(job).data)


class ExportJobView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="job_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The job id to lookup information about.",
            )
        ],
        tags=["Database table export"],
        operation_id="get_export_job",
        description=(
            "Returns information such as export progress and state or the url of the "
            "exported file for the specified export job, only if the requesting user "
            "has access."
        ),
        request=None,
        responses={
            200: ExportJobSerializer,
            404: get_error_schema(["ERROR_EXPORT_JOB_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ExportJobDoesNotExistException: ERROR_EXPORT_JOB_DOES_NOT_EXIST,
        }
    )
    def get(self, request, job_id):
        """
        Retrieves the specified export job.
        """

        try:
            job = ExportJob.objects.get(id=job_id, user_id=request.user.id)
        except ExportJob.DoesNotExist:
            raise ExportJobDoesNotExistException()

        return Response(ExportJobSerializer(job).data)
