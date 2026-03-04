from collections import OrderedDict
from uuid import uuid4

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.utils.translation import gettext as _

import unicodecsv as csv
from loguru import logger
from rest_framework import serializers

from baserow.contrib.database.api.export.serializers import (
    SUPPORTED_CSV_COLUMN_SEPARATORS,
    SUPPORTED_EXPORT_CHARSETS,
    DisplayChoiceField,
    ExportedFileURLSerializerMixin,
)
from baserow.contrib.database.export.handler import (
    ExportHandler,
    _create_storage_dir_if_missing_and_open,
)
from baserow.core.jobs.registries import JobType
from baserow.core.storage import get_default_storage
from baserow.core.utils import ChildProgressBuilder, Progress
from baserow_enterprise.features import DATA_SCANNER
from baserow_premium.license.handler import LicenseHandler

from .models import DataScanResult, DataScanResultExportJob

DATA_SCAN_RESULT_CSV_COLUMN_NAMES = OrderedDict(
    {
        "scan_name": {
            "field": "scan_name",
            "descr": _("Scan Name"),
        },
        "workspace_name": {
            "field": "workspace_name",
            "descr": _("Workspace Name"),
        },
        "database_name": {
            "field": "database_name",
            "descr": _("Database Name"),
        },
        "table_name": {
            "field": "table_name",
            "descr": _("Table Name"),
        },
        "field_name": {
            "field": "field_name",
            "descr": _("Field Name"),
        },
        "row_id": {
            "field": "row_id",
            "descr": _("Row ID"),
        },
        "matched_value": {
            "field": "matched_value",
            "descr": _("Matched Value"),
        },
        "first_identified_on": {
            "field": "first_identified_on",
            "descr": _("First Identified On"),
        },
        "last_identified_on": {
            "field": "last_identified_on",
            "descr": _("Last Identified On"),
        },
    }
)


class DataScanResultExportJobType(JobType):
    type = "data_scan_result_export"
    model_class = DataScanResultExportJob
    max_count = 1

    serializer_mixins = [ExportedFileURLSerializerMixin]
    request_serializer_field_names = [
        "csv_column_separator",
        "csv_first_row_header",
        "export_charset",
        "filter_scan_id",
    ]

    serializer_field_names = [
        *request_serializer_field_names,
        "created_on",
        "exported_file_name",
        "url",
    ]
    base_serializer_field_overrides = {
        "export_charset": DisplayChoiceField(
            choices=SUPPORTED_EXPORT_CHARSETS,
            default="utf-8",
            help_text="The character set to use when creating the export file.",
        ),
        "csv_column_separator": DisplayChoiceField(
            choices=SUPPORTED_CSV_COLUMN_SEPARATORS,
            default=",",
            help_text="The value used to separate columns in the resulting csv file.",
        ),
        "csv_first_row_header": serializers.BooleanField(
            default=True,
            help_text="Whether or not to generate a header row at the top of the csv file.",
        ),
        "filter_scan_id": serializers.IntegerField(
            min_value=0,
            required=False,
            help_text="Optional: Filter results by scan ID.",
        ),
    }
    request_serializer_field_overrides = {
        **base_serializer_field_overrides,
    }
    serializer_field_overrides = {
        **base_serializer_field_overrides,
        "created_on": serializers.DateTimeField(
            read_only=True,
            help_text="The date and time when the export job was created.",
        ),
        "exported_file_name": serializers.CharField(
            read_only=True,
            help_text="The name of the file that was created by the export job.",
        ),
        "url": serializers.SerializerMethodField(
            help_text="The URL to download the exported file.",
        ),
    }

    def before_delete(self, job: DataScanResultExportJob) -> None:
        """
        Deletes the exported CSV file from storage before the job row is
        removed.

        :param job: The export job about to be deleted.
        """

        if not job.exported_file_name:
            return

        storage = get_default_storage()
        storage_location = ExportHandler.export_file_path(job.exported_file_name)
        try:
            storage.delete(storage_location)
        except FileNotFoundError:
            logger.error(
                "Could not delete file %s for 'data_scan_result_export' job %s",
                storage_location,
                job.id,
            )

    @staticmethod
    def _safe_attr(obj, *attrs, default="") -> str:
        """
        Traverses a chain of attributes, returning `default` if any link
        raises AttributeError.
        """

        try:
            for attr in attrs:
                obj = getattr(obj, attr)
            return obj
        except AttributeError:
            return default

    def _get_row_data(self, result: DataScanResult) -> dict:
        """
        Extracts a dict of field values from a DataScanResult, with
        AttributeError protection for nullable nested relations.

        :param result: A DataScanResult instance.
        :return: A dict keyed by CSV column name with string/int/datetime values.
        """

        return {
            "scan_name": self._safe_attr(result, "scan", "name"),
            "workspace_name": self._safe_attr(
                result, "field", "table", "database", "workspace", "name"
            ),
            "database_name": self._safe_attr(
                result, "field", "table", "database", "name"
            ),
            "table_name": self._safe_attr(result, "field", "table", "name"),
            "field_name": self._safe_attr(result, "field", "name"),
            "row_id": result.row_id,
            "matched_value": result.matched_value,
            "first_identified_on": result.first_identified_on,
            "last_identified_on": result.last_identified_on,
        }

    def write_rows(
        self,
        job: DataScanResultExportJob,
        file,
        queryset: QuerySet,
        progress,
    ) -> None:
        """
        Writes all result rows from the queryset to the CSV file.

        :param job: The export job with CSV formatting options.
        :param file: A writable binary file handle.
        :param queryset: The queryset of DataScanResult rows to export.
        :param progress: Progress tracker for reporting export advancement.
        """

        # add BOM to support utf-8 CSVs in MS Excel (for Windows only)
        if job.export_charset == "utf-8":
            file.write(b"\xef\xbb\xbf")

        field_header_mapping = {
            k: v["descr"] for (k, v) in DATA_SCAN_RESULT_CSV_COLUMN_NAMES.items()
        }

        writer = csv.writer(
            file,
            field_header_mapping.values(),
            encoding=job.export_charset,
            delimiter=job.csv_column_separator,
        )

        if job.csv_first_row_header:
            writer.writerow(field_header_mapping.values())

        fields = [v["field"] for v in DATA_SCAN_RESULT_CSV_COLUMN_NAMES.values()]
        paginator = Paginator(queryset.all(), 2000)
        export_progress = ChildProgressBuilder.build(
            progress.create_child_builder(represents_progress=progress.total),
            paginator.num_pages,
        )

        for page in paginator.page_range:
            rows = []
            for result in paginator.page(page).object_list:
                row_data = self._get_row_data(result)
                rows.append([row_data[field] for field in fields])
            writer.writerows(rows)
            export_progress.increment()

    def get_filtered_queryset(self, job: DataScanResultExportJob) -> QuerySet:
        """
        Returns the queryset of DataScanResult rows to export, applying
        any filters configured on the job.

        :param job: The export job whose filters should be applied.
        :return: A filtered and ordered queryset of DataScanResult instances.
        """

        queryset = DataScanResult.objects.select_related(
            "scan", "table__database", "field__table__database__workspace"
        ).order_by("-first_identified_on")

        if job.filter_scan_id is not None:
            queryset = queryset.filter(scan_id=job.filter_scan_id)

        return queryset

    def run(self, job: DataScanResultExportJob, progress: Progress) -> None:
        """
        Export the filtered data scan results to a CSV file.

        :param job: The job that is currently being executed.
        :param progress: The progress object that can be used to update the
            progress bar.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            DATA_SCANNER, job.user
        )

        queryset = self.get_filtered_queryset(job)

        filename = f"data_scan_results_{uuid4().hex[:8]}.csv"
        storage_location = ExportHandler.export_file_path(filename)
        with _create_storage_dir_if_missing_and_open(storage_location) as file:
            self.write_rows(job, file, queryset, progress)

        job.exported_file_name = filename
        job.save()
