import pytest

from baserow.contrib.builder.models import Builder
from baserow.core.models import Snapshot
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_can_create_a_snapshot_for_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user)

    snapshot = SnapshotHandler().start_create_job(
        builder.id, performed_by=user, name="test"
    )["snapshot"]

    assert snapshot is not None
    assert snapshot.name == "test"
    assert Snapshot.objects.count() == 1


@pytest.mark.django_db
def test_can_delete_a_snapshot_for_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user)

    snapshot = SnapshotHandler().start_create_job(
        builder.id, performed_by=user, name="test"
    )["snapshot"]

    SnapshotHandler().delete(snapshot.id, user)

    snapshot.refresh_from_db()
    assert snapshot.mark_for_deletion is True


@pytest.mark.django_db
def test_can_restore_a_snapshot_for_builder_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user)

    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=builder,
        snapshot_to_application=builder,
        user=user,
    )

    snapshot_restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    assert snapshot_restored is not None
    assert Builder.objects.count() == 2


@pytest.mark.django_db
def test_can_restore_a_snapshot_with_integration(data_fixture):
    """Ensure that the integration is correctly restored."""

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user)
    data_fixture.create_local_baserow_integration(user=user, application=builder)

    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=builder,
        snapshot_to_application=builder,
        user=user,
    )
    snapshot_restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    assert snapshot_restored.integrations.all()[0].specific.authorized_user == user
