import json
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction

from rest_framework import serializers

from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_NOT_IN_TABLE,
    ERROR_INVALID_BASEROW_FIELD_NAME,
    ERROR_MAX_FIELD_COUNT_EXCEEDED,
    ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED,
    ERROR_RESERVED_BASEROW_FIELD_NAME,
    ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD,
)
from baserow.contrib.database.api.tables.errors import (
    ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES,
    ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED,
    ERROR_INVALID_INITIAL_TABLE_DATA,
)
from baserow.contrib.database.db.atomic import read_committed_single_table_transaction
from baserow.contrib.database.fields.exceptions import (
    FieldNotInTable,
    InvalidBaserowFieldName,
    MaxFieldLimitExceeded,
    MaxFieldNameLengthExceeded,
    ReservedBaserowFieldNameException,
    SelectOptionDoesNotBelongToField,
)
from baserow.contrib.database.rows.actions import ImportRowsActionType
from baserow.contrib.database.rows.exceptions import ReportMaxErrorCountExceeded
from baserow.contrib.database.rows.types import FileImportDict
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.table.exceptions import (
    InitialTableDataDuplicateName,
    InitialTableDataLimitExceeded,
    InvalidInitialTableData,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.jobs.registries import JobType

from .models import FileImportJob
from .serializers import ReportSerializer

BATCH_SIZE = 1024


class FileImportJobType(JobType):
    type = "file_import"
    model_class = FileImportJob
    max_count = 1
    request_serializer_field_names = []
    request_serializer_field_overrides = {}

    job_exceptions_map = {
        ReportMaxErrorCountExceeded: "This file import has raised too many errors.",
        InvalidInitialTableData: ERROR_INVALID_INITIAL_TABLE_DATA[2],
        InitialTableDataLimitExceeded: ERROR_INITIAL_TABLE_DATA_LIMIT_EXCEEDED[2],
        MaxFieldLimitExceeded: ERROR_MAX_FIELD_COUNT_EXCEEDED,
        MaxFieldNameLengthExceeded: ERROR_MAX_FIELD_NAME_LENGTH_EXCEEDED[2],
        InitialTableDataDuplicateName: ERROR_INITIAL_TABLE_DATA_HAS_DUPLICATE_NAMES[2],
        ReservedBaserowFieldNameException: ERROR_RESERVED_BASEROW_FIELD_NAME[2],
        InvalidBaserowFieldName: ERROR_INVALID_BASEROW_FIELD_NAME[2],
        FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE[2],
        SelectOptionDoesNotBelongToField: ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD[
            2
        ],
    }

    serializer_field_names = [
        "database_id",
        "name",
        "table_id",
        "first_row_header",
        "report",
    ]

    serializer_field_overrides = {
        "database_id": serializers.IntegerField(
            required=True,
            help_text="Database id where the table will be created.",
        ),
        "table_id": serializers.IntegerField(
            required=False,
            help_text="Table id where the data will be imported.",
        ),
        "name": serializers.CharField(
            max_length=255, required=False, help_text="The name of the new table."
        ),
        "first_row_header": serializers.BooleanField(required=False, default=False),
        "report": ReportSerializer(help_text="Import error report."),
    }

    def prepare_values(self, values, user):
        """
        Filter data from the values dict. Data are going to be added later as a file.
        See `.after_job_creation()`.
        """

        filtered_dict = dict(**values)
        filtered_dict.pop("data")
        filtered_dict.pop("configuration", None)
        return filtered_dict

    def after_job_creation(self, job, values):
        """
        Save the data file for the newly created job.
        """

        data_file = ContentFile(
            json.dumps(
                {"data": values["data"], "configuration": values.get("configuration")},
                ensure_ascii=False,
            ).encode("utf8")
        )
        job.data_file.save(None, data_file)

    def before_delete(self, job):
        """
        Try to delete the data file of a job before deleting the job.
        """

        try:
            job.data_file.delete()
        except ValueError:
            # File doesn't exist, that's ok
            pass

    def on_error(self, job, error):
        if isinstance(error, ReportMaxErrorCountExceeded):
            job.data_file.delete(save=False)
            job.report = {"failing_rows": error.report}
            job.save(update_fields=("report", "data_file"))

    def transaction_atomic_context(self, job: FileImportJob):
        """
        Protects the table and the fields from modifications while import is in
        progress.
        """

        return read_committed_single_table_transaction(job.table_id)

    def cleanup_job(self, job: FileImportJob, error_report: dict[str, Any]):
        """
        Removes the data file to save space and save the error report.

        This will be executed when a job finished successfully.
        :param job: The job instance.
        :param error_report: The error report that should be saved.
        """

        job.data_file.delete(save=False)
        job.report = {"failing_rows": error_report}
        job.save(
            update_fields=(
                "report",
                "data_file",
                "updated_on",
            )
        )

    def run(self, job, progress):
        """
        Fills the provided table with the normalized data that needs to be created upon
        creation of the table.
        """

        with job.data_file.open("r") as fin:
            data: FileImportDict = json.load(fin)
        try:
            if job.table is None:
                new_table, error_report = action_type_registry.get_by_type(
                    CreateTableActionType
                ).do(
                    job.user,
                    job.database,
                    name=job.name,
                    data=data["data"],
                    first_row_header=job.first_row_header,
                    progress=progress,
                )

                job.table = new_table
                job.save(update_fields=("table",))
            else:
                _, error_report = action_type_registry.get_by_type(
                    ImportRowsActionType
                ).do(
                    job.user,
                    table=job.table,
                    data=data,
                    progress=progress,
                )
        # when a job handler fails, celery worker will not commit and `after_commit`
        # won't be called. That's why we need to catch this specific error and
        # perform a bit of cleanup on the job.
        except ReportMaxErrorCountExceeded as err:
            self.cleanup_job(job, err.report)
            raise
        except Exception:
            raise

        def after_commit():
            """
            Removes the data file to save space and save the error report.

            This will be executed when a job finished successfully.
            """

            self.cleanup_job(job, error_report)

        transaction.on_commit(after_commit)
