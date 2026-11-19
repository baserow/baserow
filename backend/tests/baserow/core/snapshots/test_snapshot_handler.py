from datetime import datetime, timedelta, timezone

from django.db import OperationalError, transaction
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import (
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED
from baserow.core.models import Application, Snapshot
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    MaxSnapshotsAboveLimit,
    MaxSnapshotsBelowProtected,
    MaxSnapshotsChangeDeletesSnapshots,
    MaxSnapshotsExceedsAllowance,
    MaxSnapshotsFullOfProtected,
    MaxSnapshotsIsZero,
    SnapshotDoesNotExist,
    SnapshotIsBeingCreated,
)
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.snapshots.models import CreateSnapshotJob, RestoreSnapshotJob
from baserow.core.snapshots.quota_handler import SnapshotQuotaHandler
from baserow.core.snapshots.signals import before_snapshot_created
from baserow.core.snapshots.tasks import delete_application_snapshot
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress
from baserow.test_utils.fixtures import Fixtures


@pytest.mark.django_db
def test_perform_create(data_fixture: Fixtures):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)
    table = data_fixture.create_database_table(user=user, database=application)
    field = data_fixture.create_text_field(user=user, table=table)
    model = table.get_model()
    row_1 = model.objects.create(**{f"field_{field.id}": "Row 1"})
    row_1 = model.objects.create(**{f"field_{field.id}": "Row 2"})
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application,
        name="snapshot",
        created_by=user,
    )
    progress = Progress(total=100)

    SnapshotHandler().perform_create(snapshot, progress)

    snapshot.refresh_from_db()
    snapshotted_table = Table.objects.get(database=snapshot.snapshot_to_application)
    model = snapshotted_table.get_model()
    assert model.objects.count() == 2
    assert progress.progress == 100


@pytest.mark.django_db
def test_perform_create_preserves_last_modified_by(data_fixture: Fixtures):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)
    table = data_fixture.create_database_table(user=user, database=application)
    field = data_fixture.create_text_field(user=user, table=table)
    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{field.id}": "Row 1", "last_modified_by": user}
    )
    row_1 = model.objects.create(
        **{f"field_{field.id}": "Row 2", "last_modified_by": None}
    )
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application,
        name="snapshot",
        created_by=user,
    )
    progress = Progress(total=100)

    SnapshotHandler().perform_create(snapshot, progress)

    snapshot.refresh_from_db()
    snapshotted_table = Table.objects.get(database=snapshot.snapshot_to_application)
    model = snapshotted_table.get_model()
    assert model.objects.count() == 2
    assert model.objects.all()[0].last_modified_by == user
    assert model.objects.all()[1].last_modified_by is None


@pytest.mark.django_db
def test_perform_create_export_serialized_raises_operationalerror(
    data_fixture,
    bypass_check_permissions,
    application_type_serialized_raising_operationalerror,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = CoreHandler().create_application(
        user=user,
        workspace=workspace,
        type_name=DatabaseApplicationType.type,
        name="Database",
    )
    snapshot = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=database,
        created_by=user,
        name="Snapshot1",
    )

    with application_type_serialized_raising_operationalerror(
        raise_transaction_exception=True
    ):
        with pytest.raises(DatabaseSnapshotMaxLocksExceededException):
            SnapshotHandler().perform_create(snapshot, Progress(total=100))

    with application_type_serialized_raising_operationalerror(
        raise_transaction_exception=False
    ):
        with pytest.raises(OperationalError):
            SnapshotHandler().perform_create(snapshot, Progress(total=100))


@pytest.mark.django_db
def test_perform_restore(data_fixture: Fixtures):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)
    application_snapshot = data_fixture.create_database_application(
        workspace=None, order=2
    )
    table = data_fixture.create_database_table(user=user, database=application_snapshot)
    field = data_fixture.create_text_field(user=user, table=table)
    model = table.get_model()
    row_1 = model.objects.create(**{f"field_{field.id}": "Row 1"})
    row_1 = model.objects.create(**{f"field_{field.id}": "Row 2"})
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application,
        snapshot_to_application=application_snapshot,
        name="snapshot",
        created_by=user,
    )
    progress = Progress(total=100)

    restored = SnapshotHandler().perform_restore(snapshot, progress)
    restored_table = Table.objects.get(database=restored)
    model = restored_table.get_model()
    assert restored.name == snapshot.name
    assert model.objects.count() == 2
    assert progress.progress == 100


@pytest.mark.django_db(transaction=True)
def test_delete_expired_snapshots(data_fixture: Fixtures, settings):
    exp_days = 1
    settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS = exp_days
    now = datetime.now(tz=timezone.utc)
    time_before_expiration = now - timedelta(days=exp_days) - timedelta(seconds=10)
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)

    with freeze_time(now):
        recent_snapshot = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application,
            created_by=user,
            name="recent_snapshot",
        )

    with freeze_time(time_before_expiration):
        expired_snapshot_1 = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application,
            created_by=user,
            name="expired_snapshot_1",
        )
        expired_snapshot_2 = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application,
            created_by=user,
            name="expired_snapshot_2",
        )

    assert Snapshot.objects.count() == 3

    with freeze_time(now), transaction.atomic():
        SnapshotHandler().delete_expired()

    assert Snapshot.objects.count() == 1


@pytest.mark.django_db
def test_skip_schedule_deletion_when_snapshot_not_created_yet(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)
    snapshot = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application,
        snapshot_to_application=None,
        created_by=user,
        name="snapshot",
    )

    # passes when there is no exception
    SnapshotHandler()._schedule_deletion(snapshot)

    assert snapshot.mark_for_deletion is True


def _set_max_snapshots(application, max_snapshots):
    application.max_snapshots = max_snapshots
    application.save(update_fields=["max_snapshots"])


def _set_default_max_snapshots(workspace, max_snapshots):
    workspace.default_max_snapshots = max_snapshots
    workspace.save(update_fields=["default_max_snapshots"])


def _create_snapshots(data_fixture, application, user, *protected_flags):
    """
    Creates one restorable snapshot of the application per flag, a day apart and
    oldest first.
    """

    snapshots = []
    for day, protected in enumerate(protected_flags, start=1):
        with freeze_time(f"2026-01-{day:02d}"):
            snapshots.append(
                data_fixture.create_snapshot(
                    snapshot_from_application=application,
                    user=user,
                    protected=protected,
                )
            )
    return snapshots


@pytest.mark.django_db
def test_create_automatic_snapshot_has_no_user(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    data_fixture.create_database_table(user=user, database=application)

    snapshot = SnapshotHandler().create_automatic(application, "Automatic")
    SnapshotHandler().perform_create(snapshot, Progress(total=100))

    snapshot.refresh_from_db()
    assert snapshot.created_automatically is True
    assert snapshot.protected is False
    assert snapshot.created_by is None
    assert snapshot.snapshot_to_application is not None
    assert Table.objects.filter(database=snapshot.snapshot_to_application).exists()


@pytest.mark.django_db
def test_manual_snapshots_are_protected(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)

    snapshot = SnapshotHandler().create(application.id, user, "Manual")

    assert snapshot.protected is True
    assert snapshot.created_automatically is False


@pytest.mark.django_db
def test_create_snapshot_of_an_application_that_keeps_none(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    # The workspace default max snapshots starts at 0.
    with pytest.raises(MaxSnapshotsIsZero):
        SnapshotHandler().create(application.id, user, "Manual")
    with pytest.raises(MaxSnapshotsIsZero):
        SnapshotHandler().create_automatic(application, "Automatic")

    _set_default_max_snapshots(workspace, 1)
    application.refresh_from_db()
    assert SnapshotHandler().create(application.id, user, "Manual")


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=0)
def test_create_snapshot_when_snapshots_are_disabled(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)

    with pytest.raises(MaximumSnapshotsReached):
        SnapshotHandler().create(application.id, user, "Manual")
    with pytest.raises(MaximumSnapshotsReached):
        SnapshotHandler().create_automatic(application, "Automatic")


@pytest.mark.django_db
def test_create_snapshot_can_be_stopped_by_a_signal_receiver(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    received = []

    def stop(sender, workspace, application, **kwargs):
        received.append((workspace.id, application.id))
        raise MaximumSnapshotsReached()

    before_snapshot_created.connect(stop)
    try:
        with pytest.raises(MaximumSnapshotsReached):
            SnapshotHandler().create(application.id, user, "Manual")
        with pytest.raises(MaximumSnapshotsReached):
            SnapshotHandler().create_automatic(application, "Automatic")
    finally:
        before_snapshot_created.disconnect(stop)

    assert received == [(workspace.id, application.id)] * 2


@pytest.mark.django_db
def test_create_snapshot_at_its_max_snapshots_replaces_the_oldest_unprotected_one(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    protected, oldest_unprotected, newest_unprotected = _create_snapshots(
        data_fixture, application, user, True, False, False
    )

    handler = SnapshotHandler()
    assert handler.get_snapshot_to_replace(application) == oldest_unprotected
    assert handler.create_automatic(application, "Automatic")


@pytest.mark.django_db
def test_create_snapshot_below_its_max_snapshots_replaces_nothing(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    _create_snapshots(data_fixture, application, user, False, False)

    assert SnapshotHandler().get_snapshot_to_replace(application) is None


@pytest.mark.django_db
def test_create_snapshot_at_its_max_snapshots_full_of_protected_ones(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 2)
    _create_snapshots(data_fixture, application, user, True, True)

    with pytest.raises(MaxSnapshotsFullOfProtected):
        SnapshotHandler().create(application.id, user, "Manual")
    with pytest.raises(MaxSnapshotsFullOfProtected):
        SnapshotHandler().create_automatic(application, "Automatic")


@pytest.mark.django_db
def test_create_snapshot_when_the_only_unprotected_one_is_being_restored(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 2)
    _, unprotected = _create_snapshots(data_fixture, application, user, True, False)
    RestoreSnapshotJob.objects.create(user=user, snapshot=unprotected)

    with pytest.raises(MaxSnapshotsFullOfProtected):
        SnapshotHandler().create_automatic(application, "Automatic")


@pytest.mark.django_db
def test_rotate_snapshots_keeps_protected_ones(data_fixture: Fixtures, mocker):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 2)
    protected, oldest, middle, newest = _create_snapshots(
        data_fixture, application, user, True, False, False, False
    )

    with transaction.atomic():
        deleted = SnapshotHandler().rotate_snapshots(application)

    assert deleted == 2
    remaining = set(
        Snapshot.objects.restorable()
        .filter(snapshot_from_application=application)
        .values_list("id", flat=True)
    )
    assert remaining == {protected.id, newest.id}


@pytest.mark.django_db
def test_rotate_snapshots_keeps_the_ones_being_restored(data_fixture: Fixtures, mocker):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    oldest, newest = _create_snapshots(data_fixture, application, user, False, False)
    RestoreSnapshotJob.objects.create(user=user, snapshot=oldest)

    handler = SnapshotHandler()
    assert not handler.get_snapshots_to_rotate(application).exists()
    with transaction.atomic():
        handler.rotate_snapshots(application)

    oldest.refresh_from_db()
    newest.refresh_from_db()
    assert oldest.mark_for_deletion is False
    assert newest.mark_for_deletion is False


@pytest.mark.django_db
def test_rotate_after_create(data_fixture: Fixtures, mocker):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_default_max_snapshots(workspace, 1)
    oldest, newest = _create_snapshots(data_fixture, application, user, False, False)

    SnapshotHandler().rotate_after_create(application.id)

    oldest.refresh_from_db()
    newest.refresh_from_db()
    assert oldest.mark_for_deletion is True
    assert newest.mark_for_deletion is False


@pytest.mark.django_db
def test_perform_restore_checks_the_restoring_user(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    data_fixture.create_database_table(user=user, database=application)
    snapshot = SnapshotHandler().create_automatic(application, "Automatic")
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()

    restored = SnapshotHandler().perform_restore(
        snapshot, Progress(total=100), restored_by=user
    )

    assert restored.workspace_id == workspace.id
    assert restored.name == "Automatic"


@pytest.mark.django_db
def test_snapshots_being_created_count_towards_the_max_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    # Created, but not copied yet.
    SnapshotHandler().create_automatic(application, "Automatic")

    assert SnapshotHandler().count(workspace) == 1
    with pytest.raises(SnapshotIsBeingCreated):
        SnapshotHandler().create_automatic(application, "Automatic")


@pytest.mark.django_db
@override_settings(BASEROW_JOB_SOFT_TIME_LIMIT=60)
def test_interrupted_snapshots_stop_counting(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    with freeze_time("2026-01-01 10:00"):
        SnapshotHandler().create_automatic(application, "Interrupted")

    with freeze_time("2026-01-01 10:05"):
        assert SnapshotHandler().count(workspace) == 0
        snapshot = SnapshotHandler().create_automatic(application, "Automatic")

    assert snapshot.name == "Automatic"


@pytest.mark.django_db
def test_allowance_used_is_the_sum_of_the_effective_max_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 3)
    data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_application(workspace=workspace)
    own_max_snapshots = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(own_max_snapshots, 10)
    no_max_snapshots = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(no_max_snapshots, 0)
    trashed = data_fixture.create_database_application(workspace=workspace)
    trashed.trashed = True
    trashed.save()
    # Another workspace doesn't count.
    data_fixture.create_database_application(user=user)

    handler = SnapshotQuotaHandler()
    assert handler.get_allowance_used(workspace) == 3 + 3 + 10 + 0
    assert (
        handler.get_allowance_used(workspace, default_max_snapshots=1) == 1 + 1 + 10 + 0
    )


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=5)
def test_is_over_allowance(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    _set_max_snapshots(application, 5)
    assert SnapshotQuotaHandler().is_over_allowance(workspace) is False
    _set_max_snapshots(application, 6)
    assert SnapshotQuotaHandler().is_over_allowance(workspace) is True

    with override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=-1):
        assert SnapshotQuotaHandler().is_over_allowance(workspace) is False


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=10)
def test_update_application_max_snapshots_within_the_allowance(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 2)
    application = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_application(workspace=workspace)

    application, updated = SnapshotQuotaHandler().update_application_max_snapshots(
        application.id, user, 8
    )

    assert application.max_snapshots == 8
    assert updated.original_max_snapshots is None
    assert updated.new_max_snapshots == 8
    assert updated.deleted_count == 0
    assert SnapshotQuotaHandler().get_allowance_used(workspace) == 10

    with pytest.raises(MaxSnapshotsExceedsAllowance):
        SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 9)


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=4)
def test_update_application_max_snapshots_while_over_the_allowance(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    first = data_fixture.create_database_application(workspace=workspace)
    second = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(first, 3)
    _set_max_snapshots(second, 3)

    # Lowering a max is allowed, even if the workspace stays over.
    SnapshotQuotaHandler().update_application_max_snapshots(first.id, user, 2)
    # Raising one isn't.
    with pytest.raises(MaxSnapshotsExceedsAllowance):
        SnapshotQuotaHandler().update_application_max_snapshots(first.id, user, 3)


@pytest.mark.django_db
@override_settings(
    BASEROW_MAX_SNAPSHOTS_PER_GROUP=4, BASEROW_MAX_SNAPSHOTS_PER_APPLICATION=5
)
def test_a_plugin_can_let_max_snapshots_go_over_the_allowance(
    data_fixture: Fixtures, mocker
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 4)
    plugin = mocker.Mock()
    plugin.get_snapshot_allowance.return_value = None
    plugin.allows_max_snapshots_over_allowance.return_value = True
    mocker.patch(
        "baserow.core.snapshots.quota_handler.plugin_registry.get_all",
        return_value=[plugin],
    )
    max_snapshots_updated = mocker.patch(
        "baserow.core.snapshots.quota_handler.max_snapshots_updated.send"
    )

    SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 5)
    SnapshotQuotaHandler().update_workspace_default_max_snapshots(workspace.id, user, 2)
    data_fixture.create_database_application(workspace=workspace)
    workspace.refresh_from_db()

    assert SnapshotQuotaHandler().get_allowance_used(workspace) == 7
    assert SnapshotQuotaHandler().is_over_allowance(workspace)
    assert SnapshotQuotaHandler()._get_allowance_values(workspace)[
        "can_exceed_allowance"
    ]
    assert max_snapshots_updated.call_count == 2
    # The max snapshots limit still applies.
    with pytest.raises(MaxSnapshotsAboveLimit):
        SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 6)


@pytest.mark.django_db
def test_get_max_snapshots_to_make_room(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    handler = SnapshotQuotaHandler()

    assert handler.get_max_snapshots_to_make_room(application.id, user) == 1

    _set_default_max_snapshots(workspace, 2)
    assert handler.get_max_snapshots_to_make_room(application.id, user) is None

    data_fixture.create_snapshot(user=user, snapshot_from_application=application)
    unprotected = data_fixture.create_snapshot(
        user=user, snapshot_from_application=application, protected=False
    )
    assert handler.get_max_snapshots_to_make_room(application.id, user) is None

    unprotected.protected = True
    unprotected.save()
    assert handler.get_max_snapshots_to_make_room(application.id, user) == 3


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=-1)
def test_update_application_max_snapshots_without_an_allowance_limit(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    application, _ = SnapshotQuotaHandler().update_application_max_snapshots(
        application.id, user, 1000
    )

    assert application.max_snapshots == 1000


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_APPLICATION=3)
def test_update_max_snapshots_above_the_maximum(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 3)
    with pytest.raises(MaxSnapshotsAboveLimit):
        SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 4)
    with pytest.raises(MaxSnapshotsAboveLimit):
        SnapshotQuotaHandler().update_workspace_default_max_snapshots(
            workspace.id, user, 4
        )

    # A max saved before the maximum was lowered can still be lowered.
    _set_max_snapshots(application, 6)
    application, _ = SnapshotQuotaHandler().update_application_max_snapshots(
        application.id, user, 5
    )
    assert application.max_snapshots == 5


@pytest.mark.django_db
def test_update_application_max_snapshots_below_the_protected_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    _create_snapshots(data_fixture, application, user, True, True, False)

    with pytest.raises(MaxSnapshotsBelowProtected):
        SnapshotQuotaHandler().update_application_max_snapshots(
            application.id, user, 1, delete_snapshots=True
        )


@pytest.mark.django_db
def test_lower_application_max_snapshots_deletes_the_oldest_unprotected_snapshots(
    data_fixture: Fixtures, mocker
):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 4)
    protected, oldest, middle, newest = _create_snapshots(
        data_fixture, application, user, True, False, False, False
    )

    with pytest.raises(MaxSnapshotsChangeDeletesSnapshots) as exc:
        SnapshotQuotaHandler().update_application_max_snapshots(application.id, user, 2)
    assert exc.value.count == 2
    application.refresh_from_db()
    assert application.max_snapshots == 4

    _, updated = SnapshotQuotaHandler().update_application_max_snapshots(
        application.id, user, 2, delete_snapshots=True
    )

    assert updated.deleted_count == 2
    remaining = set(
        Snapshot.objects.restorable()
        .filter(snapshot_from_application=application)
        .values_list("id", flat=True)
    )
    assert remaining == {protected.id, newest.id}


@pytest.mark.django_db
def test_update_application_max_snapshots_back_to_the_workspace_default(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 2)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 5)

    application, updated = SnapshotQuotaHandler().update_application_max_snapshots(
        application.id, user, None
    )

    assert application.max_snapshots is None
    assert updated.original_max_snapshots == 5
    assert SnapshotQuotaHandler().get_effective_max_snapshots(application) == 2


@pytest.mark.django_db
def test_update_application_max_snapshots_outside_the_workspace(data_fixture: Fixtures):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    with pytest.raises(UserNotInWorkspace):
        SnapshotQuotaHandler().update_application_max_snapshots(
            application.id, other_user, 1
        )


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=10)
def test_update_workspace_default_max_snapshots(data_fixture: Fixtures, mocker):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    follower = data_fixture.create_database_application(workspace=workspace)
    own_max_snapshots = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(own_max_snapshots, 4)

    workspace, updated = SnapshotQuotaHandler().update_workspace_default_max_snapshots(
        workspace.id, user, 3
    )
    assert workspace.default_max_snapshots == 3
    assert updated.original_max_snapshots == 0
    assert SnapshotQuotaHandler().get_allowance_used(workspace) == 7

    with pytest.raises(MaxSnapshotsExceedsAllowance):
        SnapshotQuotaHandler().update_workspace_default_max_snapshots(
            workspace.id, user, 7
        )

    # Lowering it only deletes snapshots of the applications that follow it.
    oldest, newest = _create_snapshots(data_fixture, follower, user, False, False)
    own = _create_snapshots(data_fixture, own_max_snapshots, user, False, False)
    with pytest.raises(MaxSnapshotsChangeDeletesSnapshots):
        SnapshotQuotaHandler().update_workspace_default_max_snapshots(
            workspace.id, user, 1
        )
    _, updated = SnapshotQuotaHandler().update_workspace_default_max_snapshots(
        workspace.id, user, 1, delete_snapshots=True
    )

    assert updated.deleted_count == 1
    oldest.refresh_from_db()
    assert oldest.mark_for_deletion is True
    assert not Snapshot.objects.filter(
        id__in=[snapshot.id for snapshot in own], mark_for_deletion=True
    ).exists()


@pytest.mark.django_db
def test_update_workspace_default_max_snapshots_below_the_protected_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 2)
    follower = data_fixture.create_database_application(workspace=workspace)
    _create_snapshots(data_fixture, follower, user, True, True)

    with pytest.raises(MaxSnapshotsBelowProtected):
        SnapshotQuotaHandler().update_workspace_default_max_snapshots(
            workspace.id, user, 1, delete_snapshots=True
        )


@pytest.mark.django_db
def test_update_workspace_default_max_snapshots_needs_a_workspace_admin(
    data_fixture: Fixtures,
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        SnapshotQuotaHandler().update_workspace_default_max_snapshots(
            workspace.id, member, 1
        )


@pytest.mark.django_db
def test_update_protected(data_fixture: Fixtures):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    (snapshot,) = _create_snapshots(data_fixture, application, user, True)

    snapshot = SnapshotHandler().update_protected(snapshot.id, user, False)
    assert snapshot.protected is False
    snapshot.refresh_from_db()
    assert snapshot.protected is False

    with pytest.raises(UserNotInWorkspace):
        SnapshotHandler().update_protected(snapshot.id, other_user, True)


@pytest.mark.django_db
def test_get_workspace_settings(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 2)
    first = data_fixture.create_database_application(workspace=workspace, order=1)
    second = data_fixture.create_database_application(workspace=workspace, order=2)
    _set_max_snapshots(second, 3)
    _create_snapshots(data_fixture, first, user, True, False)

    settings = SnapshotQuotaHandler().get_workspace_settings(workspace.id, user)

    assert settings["used"] == 5
    assert settings["default_max_snapshots"] == 2
    assert settings["snapshot_count"] == 2
    assert settings["applications"] == [
        {
            "id": first.id,
            "max_snapshots": None,
            "snapshot_count": 2,
            "protected_count": 1,
        },
        {
            "id": second.id,
            "max_snapshots": 3,
            "snapshot_count": 0,
            "protected_count": 0,
        },
    ]


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=50)
def test_a_plugin_can_set_the_allowance_of_a_workspace(data_fixture: Fixtures, mocker):
    workspace = data_fixture.create_workspace()
    other_workspace = data_fixture.create_workspace()
    plugin = mocker.Mock()
    plugin.get_snapshot_allowance.side_effect = lambda w: (
        5 if w.id == workspace.id else None
    )
    mocker.patch(
        "baserow.core.snapshots.quota_handler.plugin_registry.get_all",
        return_value=[plugin],
    )

    assert SnapshotQuotaHandler().get_allowance(workspace) == 5
    assert SnapshotQuotaHandler().get_allowance(other_workspace) == 50


@pytest.mark.django_db
def test_update_application_max_snapshots_needs_a_workspace_admin(
    data_fixture: Fixtures,
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    application = data_fixture.create_database_application(workspace=workspace)

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        SnapshotQuotaHandler().update_application_max_snapshots(
            application.id, member, 1
        )


@pytest.mark.django_db
def test_rotate_snapshots_skips_snapshots_protected_since_they_were_picked(
    data_fixture: Fixtures, mocker
):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    oldest, newest = _create_snapshots(data_fixture, application, user, False, False)
    handler = SnapshotHandler()
    real_pick = handler._get_snapshot_ids_to_rotate

    def protect_after_picking(*args, **kwargs):
        # The oldest is picked, then protected before it's locked.
        ids = real_pick(*args, **kwargs)
        Snapshot.objects.filter(id=oldest.id).update(protected=True)
        return ids

    mocker.patch.object(
        handler, "_get_snapshot_ids_to_rotate", side_effect=protect_after_picking
    )
    with transaction.atomic():
        assert handler.rotate_snapshots(application, 1) == 0

    oldest.refresh_from_db()
    assert oldest.protected is True
    assert oldest.mark_for_deletion is False


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=10)
def test_update_application_max_snapshots_reads_the_max_snapshots_again_after_locking(
    data_fixture: Fixtures, mocker
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    first = data_fixture.create_database_application(workspace=workspace)
    second = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(first, 5)
    _set_max_snapshots(second, 5)
    handler = SnapshotHandler()
    real_lock = handler._lock_workspace

    def change_max_snapshots_while_waiting(workspace):
        # Another request lowers the max snapshots to 0 while this one waits for the
        # lock.
        Application.objects.filter(id=first.id).update(max_snapshots=0)
        return real_lock(workspace)

    mocker.patch.object(
        SnapshotHandler,
        "_lock_workspace",
        side_effect=change_max_snapshots_while_waiting,
    )

    # Going from 0 to 10 would reserve 15 of 10.
    with pytest.raises(MaxSnapshotsExceedsAllowance):
        SnapshotQuotaHandler().update_application_max_snapshots(first.id, user, 10)


@pytest.mark.django_db
def test_default_max_snapshots_change_queries_dont_grow_with_applications(
    data_fixture: Fixtures, mocker
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")

    def count_queries(application_count):
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)
        _set_default_max_snapshots(workspace, 3)
        for _ in range(application_count):
            application = data_fixture.create_database_application(workspace=workspace)
            _create_snapshots(data_fixture, application, user, False, False, False)
        with CaptureQueriesContext(connection) as captured:
            SnapshotQuotaHandler().update_workspace_default_max_snapshots(
                workspace.id, user, 1, delete_snapshots=True
            )
        assert Snapshot.objects.filter(
            snapshot_from_application__workspace=workspace, mark_for_deletion=True
        ).count() == (application_count * 2)
        return len(captured.captured_queries)

    # The first change also fetches things that are cached afterwards.
    count_queries(1)
    assert count_queries(20) == count_queries(2)


@pytest.mark.django_db
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_GROUP=0)
def test_create_automatic_snapshot_skips_max_snapshots_zero_before_the_allowance(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    # Snapshots are turned off, but an application that keeps none is skipped
    # quietly rather than reporting it.
    with pytest.raises(MaxSnapshotsIsZero):
        SnapshotHandler().create_automatic(application, "Automatic")


@pytest.mark.django_db
def test_a_duplicated_application_follows_the_workspace_default_max_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    _set_default_max_snapshots(workspace, 2)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 4)

    duplicate = CoreHandler().duplicate_application(user, application)

    duplicate = Application.objects.select_related("workspace").get(id=duplicate.id)
    assert duplicate.max_snapshots is None
    assert SnapshotQuotaHandler().get_effective_max_snapshots(duplicate) == 2


@pytest.mark.django_db
def test_a_restored_application_follows_the_workspace_default_max_snapshots(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    data_fixture.create_database_table(user=user, database=application)
    snapshot = SnapshotHandler().create_automatic(application, "Automatic")
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()

    restored = SnapshotHandler().perform_restore(
        snapshot, Progress(total=100), restored_by=user
    )

    assert Application.objects.get(id=restored.id).max_snapshots is None


@pytest.mark.django_db
def test_a_plugin_can_block_snapshot_creation(data_fixture: Fixtures, mocker):
    workspace = data_fixture.create_workspace()
    plugin = mocker.Mock()
    plugin.is_snapshot_creation_blocked.return_value = True
    plugin.get_snapshot_allowance.return_value = None
    mocker.patch(
        "baserow.core.snapshots.quota_handler.plugin_registry.get_all",
        return_value=[plugin],
    )

    assert SnapshotQuotaHandler().is_snapshot_creation_blocked(workspace) is True
    assert SnapshotQuotaHandler()._get_allowance_values(workspace)["blocked"] is True


@pytest.mark.django_db
def test_get_workspace_settings_needs_a_workspace_admin(data_fixture: Fixtures):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])

    with pytest.raises(UserInvalidWorkspacePermissionsError):
        SnapshotQuotaHandler().get_workspace_settings(workspace.id, member)


@pytest.mark.django_db
@pytest.mark.parametrize("state", [JOB_FAILED, JOB_CANCELLED])
def test_a_failed_or_cancelled_snapshot_creation_doesnt_block_the_next_one(
    data_fixture: Fixtures, state
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 5)
    handler = SnapshotHandler()
    snapshot = handler.create(application.id, user, "First")
    CreateSnapshotJob.objects.create(user=user, snapshot=snapshot, state=state)

    assert handler.is_snapshot_being_created(application) is False
    assert handler.count(workspace) == 0
    handler.create(application.id, user, "Second")


@pytest.mark.django_db
def test_lowering_max_snapshots_counts_the_snapshot_being_created_as_protected(
    data_fixture: Fixtures, mocker
):
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    _create_snapshots(data_fixture, application, user, True, True, False)
    handler = SnapshotHandler()
    # It replaces the unprotected snapshot once it's ready.
    handler.create(application.id, user, "Manual")

    with pytest.raises(MaxSnapshotsBelowProtected):
        SnapshotQuotaHandler().update_application_max_snapshots(
            application.id, user, 2, delete_snapshots=True
        )


@pytest.mark.django_db
def test_protecting_the_snapshot_a_snapshot_being_created_replaces_is_refused(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 3)
    _, _, unprotected = _create_snapshots(
        data_fixture, application, user, True, True, False
    )
    handler = SnapshotHandler()
    handler.create(application.id, user, "Manual")

    with pytest.raises(SnapshotIsBeingCreated):
        handler.update_protected(unprotected.id, user, True)

    unprotected.refresh_from_db()
    assert unprotected.protected is False


@pytest.mark.django_db
def test_protecting_a_snapshot_while_another_is_being_created_with_room(
    data_fixture: Fixtures,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 4)
    _, _, unprotected = _create_snapshots(
        data_fixture, application, user, True, True, False
    )
    handler = SnapshotHandler()
    handler.create(application.id, user, "Manual")

    assert handler.update_protected(unprotected.id, user, True).protected is True


@pytest.mark.django_db
def test_create_reads_the_max_snapshots_again_after_locking(
    data_fixture: Fixtures, mocker
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)
    handler = SnapshotHandler()
    real_lock = handler._lock_workspace

    def lower_max_snapshots_while_waiting(workspace):
        # Another request lowers the max snapshots to 0 while this one waits for the
        # lock.
        Application.objects.filter(id=application.id).update(max_snapshots=0)
        return real_lock(workspace)

    mocker.patch.object(
        handler, "_lock_workspace", side_effect=lower_max_snapshots_while_waiting
    )

    with pytest.raises(MaxSnapshotsIsZero):
        handler.create(application.id, user, "Manual")


@pytest.mark.django_db
def test_create_an_unprotected_snapshot(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    _set_max_snapshots(application, 1)

    snapshot = SnapshotHandler().create(application.id, user, "Manual", False)

    assert snapshot.protected is False


@pytest.mark.django_db
def test_update_protected_of_a_trashed_application(data_fixture: Fixtures):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    (snapshot,) = _create_snapshots(data_fixture, application, user, True)
    TrashHandler.trash(user, workspace, application, application)

    with pytest.raises(SnapshotDoesNotExist):
        SnapshotHandler().update_protected(snapshot.id, user, False)

    snapshot.refresh_from_db()
    assert snapshot.protected is True


@pytest.mark.django_db
def test_rotated_snapshots_are_only_deleted_once_committed(
    data_fixture: Fixtures, mocker, django_capture_on_commit_callbacks
):
    delete_mock = mocker.patch(
        "baserow.core.snapshots.handler.delete_application_snapshot"
    )
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    oldest, _ = _create_snapshots(data_fixture, application, user, False, False)

    with django_capture_on_commit_callbacks() as callbacks:
        assert SnapshotHandler().rotate_snapshots(application, 1) == 1
        delete_mock.delay.assert_not_called()

    for callback in callbacks:
        callback()
    delete_mock.delay.assert_called_once_with(oldest.snapshot_to_application_id)


@pytest.mark.django_db
def test_delete_application_snapshot_of_a_deleted_application():
    delete_application_snapshot(0)
