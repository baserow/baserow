from datetime import datetime, timedelta, timezone

from django.db import OperationalError, transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.models import Snapshot
from baserow.core.snapshots.handler import SnapshotHandler
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
        **{f"field_{field.id}": "Row 1", "last_modified_by": user.profile.subject}
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
    assert model.objects.all()[0].last_modified_by == user.profile.subject
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
