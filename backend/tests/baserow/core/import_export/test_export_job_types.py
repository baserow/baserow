import pytest

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import ExportApplicationsJob


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_no_exported_files_on_error(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_database_application(workspace=workspace)

    with pytest.raises(UserNotInWorkspace):
        job = JobHandler().create_and_start_job(
            user,
            ExportApplicationsJobType.type,
            workspace_id=workspace.id,
            application_ids=[],
            sync=True,
        )
        assert job.state == JOB_FAILED
        assert job.resource is None

    assert ExportApplicationsJob.objects.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_success_export(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    job = JobHandler().create_and_start_job(
        user,
        ExportApplicationsJobType.type,
        workspace_id=workspace.id,
        application_ids=[],
        sync=True,
    )
    assert job.state == JOB_FINISHED
    assert job.resource is not None
