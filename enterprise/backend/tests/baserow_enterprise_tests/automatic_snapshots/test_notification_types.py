import pytest

from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.snapshots.exceptions import MaximumSnapshotsReached
from baserow.core.snapshots.models import RestoreSnapshotJob
from baserow.core.snapshots.quota_handler import SnapshotQuotaHandler
from baserow.core.snapshots.signals import before_snapshot_created
from baserow_enterprise.automatic_snapshots.handler import (
    NO_ROOM_FOR_SNAPSHOT_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
    AutomaticSnapshotScheduleHandler,
)
from baserow_enterprise.automatic_snapshots.notification_types import (
    AutomaticSnapshotFailedNotificationType,
)


@pytest.mark.django_db
def test_failure_notifies_only_active_workspace_admins(enterprise_data_fixture):
    """Failure notifications identify the affected application and its workspace."""

    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    other_admin = fixture.create_user()
    fixture.create_user_workspace(
        workspace=workspace, user=other_admin, permissions="ADMIN"
    )
    fixture.create_user_workspace(workspace=workspace, permissions="MEMBER")
    inactive = fixture.create_user(is_active=False)
    fixture.create_user_workspace(
        workspace=workspace, user=inactive, permissions="ADMIN"
    )
    deleting = fixture.create_user()
    deleting.profile.to_be_deleted = True
    deleting.profile.save()
    fixture.create_user_workspace(
        workspace=workspace, user=deleting, permissions="ADMIN"
    )
    fixture.create_workspace(user=fixture.create_user())
    application = fixture.create_database_application(workspace=workspace)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, interval="DAY"
    )

    recipients = AutomaticSnapshotFailedNotificationType.notify_admins(
        schedule, application, "Could not create snapshot."
    )

    assert {recipient.recipient_id for recipient in recipients} == {
        admin.id,
        other_admin.id,
    }
    notification = Notification.objects.get(type="automatic_snapshot_failed")
    assert notification.workspace_id == workspace.id
    assert notification.sender_id is None
    assert notification.data == {
        "workspace_id": workspace.id,
        "schedule_id": schedule.id,
        "application_id": application.id,
        "application_name": application.name,
        "error": "Could not create snapshot.",
    }


def _failed_notifications():
    return list(
        Notification.objects.filter(type="automatic_snapshot_failed")
        .order_by("id")
        .values_list("data__error", flat=True)
    )


@pytest.mark.django_db
def test_failures_notify_only_when_the_error_changes(
    enterprise_data_fixture, enable_enterprise, mocker
):
    """A failure repeating on every run notifies once, even after it was read."""

    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=2
    )
    other_application = fixture.create_database_application(
        workspace=workspace, max_snapshots=2
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(workspace, interval="DAY")
    mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.perform_create",
        side_effect=RuntimeError("failed"),
    )

    handler.create_automatic_snapshot(schedule.id, application.id)
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE]

    NotificationRecipient.objects.update(read=True)
    handler.create_automatic_snapshot(schedule.id, application.id)
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE]

    # Each application has its own last run.
    handler.create_automatic_snapshot(schedule.id, other_application.id)
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE] * 2

    # A different error notifies again.
    create_automatic = mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.create_automatic",
        side_effect=MaximumSnapshotsReached(),
    )
    handler.create_automatic_snapshot(schedule.id, application.id)
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE] * 2 + [
        NO_ROOM_FOR_SNAPSHOT_MESSAGE
    ]
    mocker.stop(create_automatic)


@pytest.mark.django_db(transaction=True)
def test_a_failure_after_a_success_notifies_again(
    enterprise_data_fixture, enable_enterprise, mocker
):
    """Recovering clears the failure, so the next one is new and notifies."""

    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=2
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(
        workspace, application=application, interval="DAY"
    )
    perform_create = mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.perform_create",
        side_effect=RuntimeError("failed"),
    )

    handler.create_automatic_snapshot(schedule.id, application.id)
    mocker.stop(perform_create)
    handler.create_automatic_snapshot(schedule.id, application.id)
    assert schedule.last_runs.get(application=application).error == ""
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE]

    mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.perform_create",
        side_effect=RuntimeError("failed"),
    )
    handler.create_automatic_snapshot(schedule.id, application.id)
    assert _failed_notifications() == [UNEXPECTED_ERROR_MESSAGE] * 2
    assert NotificationRecipient.objects.filter(recipient=admin).count() == 2


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("failure_stage", ["create_automatic", "perform_create"])
def test_snapshot_failure_creates_sanitized_notification(
    enterprise_data_fixture, enable_enterprise, mocker, failure_stage
):
    """Both starting and exporting a snapshot notify admins without leaking internals."""

    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=1
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(
        workspace, application=application, interval="DAY"
    )
    mocker.patch(
        f"baserow.core.snapshots.handler.SnapshotHandler.{failure_stage}",
        side_effect=RuntimeError("secret database credentials"),
    )

    handler.create_automatic_snapshot(schedule.id, application.id)

    notification = Notification.objects.get(type="automatic_snapshot_failed")
    assert notification.data["error"] == UNEXPECTED_ERROR_MESSAGE
    assert notification.data["application_id"] == application.id
    assert (
        NotificationRecipient.objects.get(notification=notification).recipient_id
        == admin.id
    )


@pytest.mark.django_db
def test_skipped_snapshot_does_not_notify(enterprise_data_fixture, enable_enterprise):
    """An application configured to keep no snapshots skips without an alert."""

    fixture = enterprise_data_fixture
    workspace = fixture.create_workspace()
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=0
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(
        workspace, application=application, interval="DAY"
    )

    handler.create_automatic_snapshot(schedule.id, application.id)

    assert not Notification.objects.filter(type="automatic_snapshot_failed").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("allowance", [0, 1, -1])
def test_quota_failure_notification_reports_no_room(
    enterprise_data_fixture, enable_enterprise, settings, allowance
):
    """Workspace quota blocks use the same capacity warning as blocked rotation."""

    settings.BASEROW_MAX_SNAPSHOTS_PER_WORKSPACE = allowance
    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=2
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(
        workspace, application=application, interval="DAY"
    )

    def refuse_snapshot(sender, **kwargs):
        raise MaximumSnapshotsReached()

    # Plugins can stop creation after a workspace exceeds its allowance.
    before_snapshot_created.connect(refuse_snapshot)
    try:
        handler.create_automatic_snapshot(schedule.id, application.id)
    finally:
        before_snapshot_created.disconnect(refuse_snapshot)

    schedule.refresh_from_db()
    notification = Notification.objects.get(type="automatic_snapshot_failed")
    assert (
        schedule.last_runs.get(application=application).error
        == NO_ROOM_FOR_SNAPSHOT_MESSAGE
    )
    assert notification.data["error"] == NO_ROOM_FOR_SNAPSHOT_MESSAGE


@pytest.mark.django_db
@pytest.mark.parametrize("protected", [True, False])
def test_blocked_rotation_notifies_with_sufficient_workspace_allowance(
    enterprise_data_fixture, enable_enterprise, settings, protected
):
    """Protected or restoring snapshots block rotation and notify admins only once."""

    settings.BASEROW_MAX_SNAPSHOTS_PER_WORKSPACE = 50
    fixture = enterprise_data_fixture
    admin = fixture.create_user()
    workspace = fixture.create_workspace(user=admin)
    application = fixture.create_database_application(
        workspace=workspace, max_snapshots=1
    )
    snapshot = fixture.create_snapshot(
        snapshot_from_application=application, user=admin, protected=protected
    )
    if not protected:
        RestoreSnapshotJob.objects.create(user=admin, snapshot=snapshot)
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(
        workspace, application=application, interval="DAY"
    )
    assert SnapshotQuotaHandler().get_allowance_used(workspace) < 50

    handler.create_automatic_snapshot(schedule.id, application.id)
    handler.create_automatic_snapshot(schedule.id, application.id)

    schedule.refresh_from_db()
    notification = Notification.objects.get(type="automatic_snapshot_failed")
    assert notification.data["error"] == NO_ROOM_FOR_SNAPSHOT_MESSAGE
    assert (
        schedule.last_runs.get(application=application).error
        == NO_ROOM_FOR_SNAPSHOT_MESSAGE
    )
    assert (
        NotificationRecipient.objects.get(notification=notification).recipient_id
        == admin.id
    )
    snapshot.refresh_from_db()
    assert not snapshot.mark_for_deletion
