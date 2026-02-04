import pytest
from celery.exceptions import Ignore

from baserow.contrib.database.export.tasks import run_export_job


@pytest.mark.django_db
def test_run_export_job_skips_nonexisting_jobs():
    non_existing_job_id = 999
    with pytest.raises(Ignore):
        run_export_job(non_existing_job_id)
