import pytest

from baserow.contrib.database.file_import.job_types import FileImportJobType
from baserow.contrib.database.file_import.models import FileImportJob
from baserow.core.jobs.constants import JOB_FINISHED, JOB_PENDING, JOB_STARTED
from baserow.core.jobs.exceptions import MaxJobCountExceeded


@pytest.fixture
def job_type():
    return FileImportJobType()


@pytest.mark.django_db
def test_can_schedule_when_no_running_jobs(data_fixture, job_type):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    job = FileImportJob(user=user, database=database, table=table)
    job_type.can_schedule_or_raise(job)


@pytest.mark.django_db
def test_cannot_schedule_two_imports_for_same_table(
    data_fixture, job_type, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    with patch_filefield_storage():
        data_fixture.create_file_import_job(
            user=user, database=database, table=table, state=JOB_PENDING
        )

    new_job = FileImportJob(user=user, database=database, table=table)
    with pytest.raises(MaxJobCountExceeded):
        job_type.can_schedule_or_raise(new_job)


@pytest.mark.django_db
def test_can_schedule_imports_for_different_tables(
    data_fixture, job_type, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a = data_fixture.create_database_table(database=database)
    table_b = data_fixture.create_database_table(database=database)

    with patch_filefield_storage():
        data_fixture.create_file_import_job(
            user=user, database=database, table=table_a, state=JOB_STARTED
        )

    new_job = FileImportJob(user=user, database=database, table=table_b)
    job_type.can_schedule_or_raise(new_job)


@pytest.mark.django_db
def test_cannot_schedule_two_new_table_imports_for_same_database(
    data_fixture, job_type, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    with patch_filefield_storage():
        data_fixture.create_file_import_job(
            user=user, database=database, table=None, state=JOB_PENDING
        )

    new_job = FileImportJob(user=user, database=database, table=None)
    with pytest.raises(MaxJobCountExceeded):
        job_type.can_schedule_or_raise(new_job)


@pytest.mark.django_db
def test_can_schedule_new_table_import_when_existing_table_import_running(
    data_fixture, job_type, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    with patch_filefield_storage():
        data_fixture.create_file_import_job(
            user=user, database=database, table=table, state=JOB_STARTED
        )

    new_job = FileImportJob(user=user, database=database, table=None)
    job_type.can_schedule_or_raise(new_job)


@pytest.mark.django_db
def test_finished_jobs_do_not_block_new_imports(
    data_fixture, job_type, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)

    with patch_filefield_storage():
        data_fixture.create_file_import_job(
            user=user, database=database, table=table, state=JOB_FINISHED
        )

    new_job = FileImportJob(user=user, database=database, table=table)
    job_type.can_schedule_or_raise(new_job)
