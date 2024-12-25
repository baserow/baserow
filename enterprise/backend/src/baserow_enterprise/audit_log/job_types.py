from collections import OrderedDict
from typing import Dict
from uuid import uuid4

from django.core.paginator import Paginator
from django.utils.functional import lazy
from django.utils.translation import gettext as _
from django.utils.translation import override as translation_override

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
from baserow.core.action.registries import action_type_registry
from baserow.core.jobs.registries import JobType
from baserow.core.storage import get_default_storage
from baserow.core.utils import ChildProgressBuilder

from .models import AuditLogEntry, AuditLogExportJob
from .utils import check_for_license_and_permissions_or_raise

AUDIT_LOG_CSV_COLUMN_NAMES = OrderedDict(
    {
        "user_email": {
            "field": "user_email",
            "descr": _("User Email"),
        },
        "user_id": {
            "field": "user_id",
            "descr": _("User ID"),
        },
        "workspace_name": {
            "field": "workspace_name",
            "descr": _("Group Name"),
        },
        "workspace_id": {
            "field": "workspace_id",
            "descr": _("Group ID"),
        },
        "type": {
            "field": "type",
            "descr": _("Action Type"),
        },
        "description": {
            "field": "description",
            "descr": _("Description"),
        },
        "timestamp": {
            "field": "action_timestamp",
            "descr": _("Timestamp"),
        },
        "ip_address": {
            "field": "ip_address",
            "descr": _("IP Address"),
        },
    }
)


class CommaSeparatedCsvColumnsField(serializers.CharField):
    def validate_values(self, value):
        items = value.split(",")

        if len(set(items)) != len(items):
            raise serializers.ValidationError("Duplicate items are not allowed.")

        if len(items) > 0:
            for item in items:
                if item not in AUDIT_LOG_CSV_COLUMN_NAMES.keys():
                    raise serializers.ValidationError(f"{item} is not a valid choice.")

        if len(items) == len(self.child.choices):
            raise serializers.ValidationError("At least one column must be included.")

        return value


class AuditLogExportJobType(JobType):
    type = "audit_log_export"
    model_class = AuditLogExportJob
    max_count = 1

    serializer_mixins = [ExportedFileURLSerializerMixin]
    request_serializer_field_names = [
        "csv_column_separator",
        "csv_first_row_header",
        "export_charset",
        "filter_user_id",
        "filter_workspace_id",
        "filter_action_type",
        "filter_from_timestamp",
        "filter_to_timestamp",
        "exclude_columns",
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
        # For ease of use we expect the JSON to contain human typeable forms of each
        # different separator instead of the unicode character itself. By using the
        # DisplayChoiceField we can then map this to the actual separator character by
        # having those be the second value of each choice tuple.
        "csv_column_separator": DisplayChoiceField(
            choices=SUPPORTED_CSV_COLUMN_SEPARATORS,
            default=",",
            help_text="The value used to separate columns in the resulting csv file.",
        ),
        "csv_first_row_header": serializers.BooleanField(
            default=True,
            help_text="Whether or not to generate a header row at the top of the csv file.",
        ),
        "filter_user_id": serializers.IntegerField(
            min_value=0,
            required=False,
            help_text="Optional: The user to filter the audit log by.",
        ),
        "filter_workspace_id": serializers.IntegerField(
            min_value=0,
            required=False,
            help_text="Optional: The workspace to filter the audit log by.",
        ),
        "filter_action_type": serializers.ChoiceField(
            choices=lazy(action_type_registry.get_types, list)(),
            required=False,
            default=None,
            help_text="Optional: The action type to filter the audit log by.",
        ),
        "filter_from_timestamp": serializers.DateTimeField(
            required=False,
            help_text="Optional: The start date to filter the audit log by.",
        ),
        "filter_to_timestamp": serializers.DateTimeField(
            required=False,
            help_text="Optional: The end date to filter the audit log by.",
        ),
        "exclude_columns": CommaSeparatedCsvColumnsField(
            required=False,
            help_text=(
                "Optional: A comma separated list of column names to exclude from the export. "
                f"Available options are `{', '.join(AUDIT_LOG_CSV_COLUMN_NAMES.keys())}`."
            ),
        ),
    }
    request_serializer_field_overrides = {
        **base_serializer_field_overrides,
    }
    serializer_field_overrides = {
        # Map to the python encoding aliases at the same time by using a
        # DisplayChoiceField
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

    def before_delete(self, job):
        """
        Try to delete the data file of a job before deleting the job.
        """

        if not job.exported_file_name:
            return

        storage = get_default_storage()
        storage_location = ExportHandler.export_file_path(job.exported_file_name)
        print("before delete ===", storage)
        try:
            storage.delete(storage_location)
        except FileNotFoundError:
            logger.error(
                "Could not delete file %s for 'audit_log_export' job %s",
                storage_location,
                job.id,
            )

    def write_audit_log_rows(self, job, file, queryset, progress):
        # add BOM to support utf-8 CSVs in MS Excel (for Windows only)
        if job.export_charset == "utf-8":
            file.write(b"\xef\xbb\xbf")

        exclude_columns = job.exclude_columns.split(",") if job.exclude_columns else []
        field_header_mapping = {
            k: v["descr"]
            for (k, v) in AUDIT_LOG_CSV_COLUMN_NAMES.items()
            if k not in exclude_columns
        }

        writer = csv.writer(
            file,
            field_header_mapping.values(),
            encoding=job.export_charset,
            delimiter=job.csv_column_separator,
        )

        if job.csv_first_row_header:
            writer.writerow(field_header_mapping.values())

        fields = [
            v["field"]
            for (k, v) in AUDIT_LOG_CSV_COLUMN_NAMES.items()
            if k not in exclude_columns
        ]
        paginator = Paginator(queryset.all(), 2000)
        export_progress = ChildProgressBuilder.build(
            progress.create_child_builder(represents_progress=progress.total),
            paginator.num_pages,
        )

        for page in paginator.page_range:
            rows = [
                [getattr(row, field) for field in fields]
                for row in paginator.page(page).object_list
            ]
            writer.writerows(rows)
            export_progress.increment()

    def get_filtered_queryset(self, job):
        queryset = AuditLogEntry.objects.order_by("-action_timestamp")
        filters_field_mapping: Dict[str, str] = {
            "filter_user_id": "user_id",
            "filter_workspace_id": "workspace_id",
            "filter_action_type": "action_type",
            "filter_from_timestamp": "action_timestamp__gte",
            "filter_to_timestamp": "action_timestamp__lte",
        }

        for field, qs_filter in filters_field_mapping.items():
            if (value := getattr(job, field)) is not None:
                queryset = queryset.filter(**{qs_filter: value})

        return queryset

    def run(self, job, progress):
        """
        Export the filtered audit log entries to a CSV file.

        :param job: The job that is currently being executed.
        :progress: The progress object that can be used to update the progress bar.
        """

        check_for_license_and_permissions_or_raise(job.user, job.filter_workspace_id)

        queryset = self.get_filtered_queryset(job)

        filename = f"{uuid4()}.csv"
        storage_location = ExportHandler.export_file_path(filename)
        with _create_storage_dir_if_missing_and_open(storage_location) as file:
            with translation_override(job.user.profile.language):
                self.write_audit_log_rows(job, file, queryset, progress)

        job.exported_file_name = filename
        job.save()
