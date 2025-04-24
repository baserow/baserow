from dataclasses import dataclass

from django.db import models

from baserow.contrib.database.models import Database
from baserow.core.jobs.mixins import JobWithUserIpAddress
from baserow.core.jobs.models import Job
from baserow.core.models import Workspace


@dataclass
class DownloadFile:
    url: str
    row_id: str
    column_id: str
    attachment_id: str
    type: str


class AirtableImportJob(JobWithUserIpAddress, Job):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace where the Airtable base must be imported into.",
    )
    airtable_share_id = models.CharField(
        max_length=200,
        help_text="Public ID of the shared Airtable base that must be imported.",
    )
    database = models.ForeignKey(
        Database,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The imported Baserow database.",
    )
    skip_files = models.BooleanField(
        default=False,
        db_default=False,
        help_text="If true, then the files are not downloaded and imported.",
    )
    session = models.CharField(
        null=True,
        help_text="Optionally provide a session object that's used as authentication.",
    )
    session_signature = models.CharField(
        null=True, help_text="The matching session signature if a session is provided."
    )
