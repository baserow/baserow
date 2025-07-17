from unittest.mock import patch

from django.core.cache import cache
from django.db import connections

import pytest
import responses

from baserow.contrib.database.airtable.exceptions import AirtableShareIsNotABase
from baserow.contrib.database.airtable.models import AirtableImportJob
from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.models import Job
from baserow.core.jobs.tasks import run_async_job
from baserow.core.utils import ChildProgressBuilder


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@responses.activate
@patch(
    "baserow.contrib.database.airtable.handler"
    ".AirtableHandler.import_from_airtable_to_workspace"
)
@patch("baserow.core.signals.application_created.send")
@pytest.mark.timeout(10)
def test_run_import_from_airtable(
    send_mock, mock_import_from_airtable_to_workspace, data_fixture
):
    # Somehow needed to activate the second connection.
    connections["default-copy"]

    created_database = data_fixture.create_database_application()

    def update_progress_slow(*args, **kwargs):
        nonlocal created_database

        progress_builder = kwargs["progress_builder"]
        progress = ChildProgressBuilder.build(progress_builder, 100)
        progress.increment(100)

        return created_database

    mock_import_from_airtable_to_workspace.side_effect = update_progress_slow

    job = data_fixture.create_airtable_import_job()

    with pytest.raises(Job.DoesNotExist):
        run_async_job(0)

    run_async_job(job.id)

    mock_import_from_airtable_to_workspace.assert_called_once()
    args = mock_import_from_airtable_to_workspace.call_args
    assert args[0][0].id == job.workspace.id
    assert args[0][1] == job.airtable_share_id
    assert isinstance(args[1]["progress_builder"], ChildProgressBuilder)
    assert args[1]["progress_builder"].represents_progress == 100

    job = AirtableImportJob.objects.get(pk=job.id)
    assert job.progress_percentage == 100
    assert job.state == JOB_FINISHED
    assert job.database_id == created_database.id

    # The cache entry will be removed when job completes.
    assert cache.get(job_progress_key(job.id)) is None

    job_copy = AirtableImportJob.objects.using("default-copy").get(pk=job.id)
    assert job_copy.progress_percentage == 100
    assert job_copy.state == JOB_FINISHED
    assert job_copy.get_cached_progress_percentage() == 100
    assert job_copy.get_cached_state() == JOB_FINISHED
    assert job_copy.database_id == created_database.id

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["application"].id == job.database_id
    assert send_mock.call_args[1]["user"] is None


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch(
    "baserow.contrib.database.airtable.handler.AirtableHandler"
    ".import_from_airtable_to_workspace"
)
def test_run_import_shared_view(mock_import_from_airtable_to_workspace, data_fixture):
    def update_progress_slow(*args, **kwargs):
        raise AirtableShareIsNotABase("The `shared_id` is not a base.")

    mock_import_from_airtable_to_workspace.side_effect = update_progress_slow

    job = data_fixture.create_airtable_import_job()

    run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error == "The `shared_id` is not a base."
    assert (
        job.human_readable_error
        == "The shared link is not a base. It's probably a view and the Airtable "
        "import tool only supports shared bases."
    )
