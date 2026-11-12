import pytest

from baserow.contrib.database.table.models import DuplicateTableJob, Table
from baserow.core.action.models import Action
from baserow.core.action.signals import action_done
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionException
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import WorkspaceUser


@pytest.mark.django_db(transaction=True)
def test_queued_identity_job_duplicates_table_as_the_retained_identity(
    data_fixture, mocker
):
    table = data_fixture.create_database_table()
    field = data_fixture.create_text_field(table=table, primary=True, name="Name")
    table.get_model().objects.create(**{field.db_column: "Queued row"})
    identity = data_fixture.create_identity(workspace=table.database.workspace)
    job = DuplicateTableJob.objects.create(user=identity, original_table=table)
    send_action = mocker.spy(action_done, "send")

    with local_cache.context():
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert job.user_id == identity.id
    duplicate = job.duplicated_table
    assert duplicate.id != table.id
    assert duplicate.database_id == table.database_id
    duplicate_field = duplicate.field_set.get(name="Name")
    assert list(
        duplicate.get_model().objects.values_list(duplicate_field.db_column, flat=True)
    ) == ["Queued row"]
    duplicate_actions = [
        call.kwargs
        for call in send_action.call_args_list
        if call.kwargs["action_type"].type == "duplicate_table"
    ]
    assert len(duplicate_actions) == 1
    assert duplicate_actions[0]["user"] == identity
    assert not Action.objects.filter(user=identity).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("revocation", ["trash", "disable", "membership", "role"])
def test_queued_identity_job_rechecks_current_authority(data_fixture, revocation):
    table = data_fixture.create_database_table()
    identity = data_fixture.create_identity(workspace=table.database.workspace)
    job = DuplicateTableJob.objects.create(user=identity, original_table=table)
    if revocation == "trash":
        identity.profile.trashed = True
        identity.profile.save(update_fields=["trashed"])
    elif revocation == "disable":
        identity.is_active = False
        identity.save(update_fields=["is_active"])
    elif revocation == "membership":
        WorkspaceUser.objects_and_identities.filter(user=identity).delete()
    else:
        WorkspaceUser.objects_and_identities.filter(user=identity).update(
            permissions="NO_ACCESS"
        )

    with local_cache.context(), pytest.raises(PermissionException):
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.failed
    assert job.duplicated_table_id is None
    assert Table.objects.count() == 1
