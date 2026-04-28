from django.db import models

from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job


# If you ever change the return value of this function please duplicate the old
# version into migration database.0080 and change that migration to use the duplicate
# to ensure this old migration doesn't logically change.
def file_import_directory_path(instance, filename):
    return f"user_{instance.user.id}/file_import/job__{instance.id}.json"


# If you ever change the return value of this function please duplicate the old version
# into migration database.0080_auto_20220702_1612 and change that migration to use the
# duplicate to ensure this old migration doesn't logically change
def default_report():
    return {"failing_rows": {}}


class FileImportJob(JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job):
    database = models.ForeignKey(
        Database,
        on_delete=models.SET_NULL,
        null=True,
        related_name="table_import_jobs",
        help_text="The database where we want to create the table",
    )
    name = models.CharField(
        max_length=255, default="", help_text="The name of the created table."
    )
    table = models.ForeignKey(
        Table,
        on_delete=models.SET_NULL,
        null=True,
        related_name="import_jobs",
        help_text="If provided the job will be a data import only job. "
        "Otherwise it will be the created table.",
    )
    data_file = models.FileField(
        upload_to=file_import_directory_path,
        null=True,
        help_text="The data file to import.",
    )
    first_row_header = models.BooleanField(
        default=False, help_text="Is the first row of the provided data the header?"
    )
    importer_type = models.TextField(
        blank=True,
        null=True,  # ZDM: remove null=True in a future migration
        help_text="The frontend importer identifier used to parse the file.",
    )
    original_file_name = models.TextField(
        blank=True,
        null=True,  # ZDM: remove null=True in a future migration
        help_text="The original name of the uploaded file.",
    )
    report = models.JSONField(
        default=default_report,
        help_text="The import error report.",
    )
