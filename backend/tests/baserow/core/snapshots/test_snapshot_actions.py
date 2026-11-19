import contextlib
from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.snapshots.actions import (
    CreateSnapshotActionType,
    DeleteSnapshotActionType,
    RestoreSnapshotActionType,
)
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress


@pytest.mark.django_db
@patch(
    "baserow.core.snapshots.job_types.CreateSnapshotJobType.transaction_atomic_context",
    new=contextlib.nullcontext,
)
@patch("baserow.core.action.signals.action_done.send")
def test_create_snapshot_action_type(
    send_mock, data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)

    with django_capture_on_commit_callbacks(execute=True):
        result = SnapshotHandler().start_create_job(
            application.id, user, "test snapshot"
        )

    snapshot = result["snapshot"]
    job = result["job"]

    job.refresh_from_db()
    assert job.state == JOB_FINISHED

    assert send_mock.call_count == 1
    assert send_mock.call_args[1]["action_type"].type == CreateSnapshotActionType.type

    assert snapshot.name == "test snapshot"
    assert snapshot.snapshot_from_application_id == application.id
    assert snapshot.snapshot_to_application_id is None


@pytest.mark.django_db
@patch(
    "baserow.core.snapshots.job_types.RestoreSnapshotJobType.transaction_atomic_context",
    new=contextlib.nullcontext,
)
@patch("baserow.core.action.signals.action_done.send")
def test_restore_snapshot_action_type(
    send_mock, data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    from_application = data_fixture.create_database_application(workspace=workspace)
    to_application = data_fixture.create_database_application(
        workspace=workspace, name="test"
    )
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=from_application,
        snapshot_to_application=to_application,
        name="snapshot",
        created_by=user,
    )

    with django_capture_on_commit_callbacks(execute=True):
        job = SnapshotHandler().start_restore_job(snapshot.id, user)

    job.refresh_from_db()
    assert job.state == JOB_FINISHED

    assert send_mock.call_count == 1
    assert send_mock.call_args[1]["action_type"].type == RestoreSnapshotActionType.type

    assert snapshot.snapshot_to_application.name == "test"


@pytest.fixture
def snapshot_of_a_deleted_creator(data_fixture, use_tmp_media_root):
    creator, admin = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[creator, admin])
    application = data_fixture.create_database_application(workspace=workspace)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application, name="snapshot", created_by=creator
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    creator.delete()
    snapshot.refresh_from_db()
    return snapshot, admin


@pytest.mark.django_db
def test_restore_snapshot_checks_the_person_restoring(
    data_fixture, snapshot_of_a_deleted_creator
):
    snapshot, admin = snapshot_of_a_deleted_creator
    restore = action_type_registry.get_by_type(RestoreSnapshotActionType).do

    with pytest.raises(UserNotInWorkspace):
        restore(data_fixture.create_user(), snapshot, Progress(total=100))
    restored = restore(admin, snapshot, Progress(total=100))

    assert restored.workspace_id == snapshot.snapshot_from_application.workspace_id


@pytest.mark.django_db(transaction=True)
def test_delete_snapshot_action_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    from_application = data_fixture.create_database_application(workspace=workspace)
    to_application = data_fixture.create_database_application(
        workspace=workspace, name="test"
    )
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=from_application,
        snapshot_to_application=to_application,
        name="snapshot",
        created_by=user,
    )

    assert SnapshotHandler().list(from_application.id, user).count() == 1

    with transaction.atomic():
        action_type_registry.get(DeleteSnapshotActionType.type).do(user, snapshot.id)

    assert SnapshotHandler().list(from_application.id, user).count() == 0
