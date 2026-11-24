from datetime import datetime, timedelta, timezone

from django.db import transaction
from django.db.models import QuerySet
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time

from baserow.core.models import Snapshot
from baserow.core.notifications.models import Notification
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress
from baserow_enterprise.automatic_snapshots.exceptions import (
    AutomaticSnapshotScheduleAlreadyExists,
    AutomaticSnapshotScheduleIntervalTooShort,
    AutomaticSnapshotScheduleInvalid,
)
from baserow_enterprise.automatic_snapshots.handler import (
    NO_ROOM_FOR_SNAPSHOT_MESSAGE,
    REPLACED_RIGHT_AWAY_MESSAGE,
    UNEXPECTED_ERROR_MESSAGE,
    AutomaticSnapshotScheduleHandler,
)
from baserow_enterprise.automatic_snapshots.models import (
    AUTOMATIC_SNAPSHOT_PAUSED_LICENSE,
    AutomaticSnapshotSchedule,
)

DAILY = {"interval": "DAY", "hour": 2, "minute": 0}


def set_max_snapshots(application, max_snapshots):
    application.max_snapshots = max_snapshots
    application.save(update_fields=["max_snapshots"])


def set_default_max_snapshots(workspace, max_snapshots):
    workspace.default_max_snapshots = max_snapshots
    workspace.save(update_fields=["default_max_snapshots"])


@pytest.fixture
def delay_mock(mocker):
    return mocker.patch(
        "baserow_enterprise.automatic_snapshots.tasks.create_automatic_snapshot.delay"
    )


@pytest.fixture
def no_snapshot_deletion(mocker):
    # Deleting the copy of a rotated snapshot runs in its own task.
    mocker.patch("baserow.core.snapshots.handler.delete_application_snapshot")


@pytest.mark.django_db
@freeze_time("2026-11-04 10:00")
def test_create_schedule_calculates_the_next_run(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )

    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )

    assert schedule.next_run_at == datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)
    assert schedule.is_workspace_default is False


@pytest.mark.django_db
def test_create_schedule_only_once_per_application(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    handler.create_schedule(workspace, application=application, **DAILY)
    handler.create_schedule(workspace, **DAILY)

    with pytest.raises(AutomaticSnapshotScheduleAlreadyExists):
        handler.create_schedule(workspace, application=application, **DAILY)
    with pytest.raises(AutomaticSnapshotScheduleAlreadyExists):
        handler.create_schedule(workspace, **DAILY)


@pytest.mark.django_db
def test_create_schedule_respects_the_minimum_interval(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()
    handler = AutomaticSnapshotScheduleHandler()

    with pytest.raises(AutomaticSnapshotScheduleIntervalTooShort):
        handler.create_schedule(workspace, interval="MINUTE", minute=30)

    schedule = handler.create_schedule(workspace, interval="HOUR", minute=15)
    assert schedule.interval == "HOUR"


@pytest.mark.django_db
@override_settings(BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=5)
def test_self_hosters_can_lower_the_minimum_interval(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()

    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, interval="MINUTE", minute=5
    )

    assert schedule.minute == 5


@pytest.mark.django_db
@override_settings(BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=1440)
def test_hourly_is_refused_when_the_minimum_is_a_day(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()

    with pytest.raises(AutomaticSnapshotScheduleIntervalTooShort):
        AutomaticSnapshotScheduleHandler().create_schedule(
            workspace, interval="HOUR", minute=0
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [
        {"timezone": "Mars/Olympus"},
        {"hour": 24},
        {"day_of_week": 7},
        {"day_of_month": 0},
        {"minute": 60},
    ],
)
def test_create_schedule_validates_the_values(enterprise_data_fixture, values):
    workspace = enterprise_data_fixture.create_workspace()

    with pytest.raises(AutomaticSnapshotScheduleInvalid):
        AutomaticSnapshotScheduleHandler().create_schedule(
            workspace, **{**DAILY, **values}
        )


@pytest.mark.django_db
def test_workspace_default_covers_applications_without_their_own_schedule(
    enterprise_data_fixture,
):
    workspace = enterprise_data_fixture.create_workspace()
    follows_default = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    own_schedule = enterprise_data_fixture.create_builder_application(
        workspace=workspace
    )
    turned_off = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    trashed = enterprise_data_fixture.create_database_application(workspace=workspace)
    TrashHandler.trash(None, workspace, trashed, trashed)
    handler = AutomaticSnapshotScheduleHandler()
    default = handler.create_schedule(workspace, **DAILY)
    own = handler.create_schedule(workspace, application=own_schedule, **DAILY)
    handler.create_schedule(workspace, application=turned_off, enabled=False, **DAILY)

    def covered_ids(schedule):
        return [app.id for app in handler.get_covered_applications(schedule)]

    assert covered_ids(default) == [follows_default.id]
    assert covered_ids(own) == [own_schedule.id]

    # An application created later is covered by the workspace default too.
    added_later = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    assert covered_ids(default) == [follows_default.id, added_later.id]


@pytest.mark.django_db
def test_run_due_schedules_queues_every_covered_application(
    enterprise_data_fixture,
    enable_enterprise,
    delay_mock,
    django_capture_on_commit_callbacks,
):
    workspace = enterprise_data_fixture.create_workspace()
    set_default_max_snapshots(workspace, 1)
    first = enterprise_data_fixture.create_database_application(workspace=workspace)
    second = enterprise_data_fixture.create_database_application(workspace=workspace)
    with freeze_time("2026-11-04 01:00"):
        schedule = AutomaticSnapshotScheduleHandler().create_schedule(
            workspace, **DAILY
        )

    with (
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        AutomaticSnapshotScheduleHandler().run_due_schedules()

    # The first application is queued with the rest of the run, which its task
    # queues one after another.
    delay_mock.assert_called_once_with(schedule.id, first.id, [second.id])
    schedule.refresh_from_db()
    assert schedule.next_run_at == datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)
    # Queuing a run does not create a completed application result.
    assert not schedule.last_runs.exists()
    assert schedule.paused_reason is None


@pytest.mark.django_db
def test_run_due_schedules_skips_workspaces_without_the_license(
    enterprise_data_fixture, delay_mock, django_capture_on_commit_callbacks
):
    workspace = enterprise_data_fixture.create_workspace()
    enterprise_data_fixture.create_database_application(workspace=workspace)
    with freeze_time("2026-11-04 01:00"):
        schedule = AutomaticSnapshotScheduleHandler().create_schedule(
            workspace, **DAILY
        )

    # Several days pass without the license: no catch-up runs are queued.
    with (
        freeze_time("2026-11-08 02:30"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        AutomaticSnapshotScheduleHandler().run_due_schedules()

    delay_mock.assert_not_called()
    schedule.refresh_from_db()
    assert schedule.paused_reason == AUTOMATIC_SNAPSHOT_PAUSED_LICENSE
    assert schedule.next_run_at == datetime(2026, 11, 9, 2, 0, tzinfo=timezone.utc)
    assert not schedule.last_runs.exists()
    assert schedule.enabled is True


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_creates_and_rotates(
    enterprise_data_fixture, enable_enterprise, no_snapshot_deletion
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    enterprise_data_fixture.create_database_table(user=user, database=application)
    # The manual snapshot is protected, so it's kept and counts towards the max.
    manual = enterprise_data_fixture.create_snapshot(
        snapshot_from_application=application, user=user
    )
    set_max_snapshots(application, 2)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )
    handler = AutomaticSnapshotScheduleHandler()

    with freeze_time("2026-11-04 02:00"):
        handler.create_automatic_snapshot(schedule.id, application.id)
    first = Snapshot.objects.get(created_automatically=True)
    assert first.created_by is None
    assert first.protected is False
    assert first.name == "Automatic snapshot 2026-11-04 02:00"
    assert first.snapshot_to_application is not None
    schedule.refresh_from_db()
    assert schedule.last_runs.get(application=application).finished_at == datetime(
        2026, 11, 4, 2, 0, tzinfo=timezone.utc
    )

    with freeze_time("2026-11-05 02:00"):
        handler.create_automatic_snapshot(schedule.id, application.id)

    restorable = Snapshot.objects.restorable().filter(
        snapshot_from_application=application
    )
    automatic = restorable.filter(created_automatically=True)
    assert [s.name for s in automatic] == ["Automatic snapshot 2026-11-05 02:00"]
    assert restorable.filter(id=manual.id).exists()


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_exits_when_the_license_is_gone(
    enterprise_data_fixture, no_snapshot_deletion
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    with freeze_time("2026-11-04 01:00"):
        old = enterprise_data_fixture.create_snapshot(
            snapshot_from_application=application,
            user=user,
            created_by=None,
            created_automatically=True,
        )
    set_max_snapshots(application, 1)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )

    # The task was queued while licensed, but the license expired before it ran.
    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule.id, application.id
    )

    assert list(
        Snapshot.objects.filter(snapshot_from_application=application).values_list(
            "id", flat=True
        )
    ) == [old.id]
    schedule.refresh_from_db()
    assert schedule.paused_reason == AUTOMATIC_SNAPSHOT_PAUSED_LICENSE


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_MAX_SNAPSHOTS_PER_WORKSPACE=0)
def test_create_automatic_snapshot_records_disabled_snapshots(
    enterprise_data_fixture, enable_enterprise
):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    set_max_snapshots(application, 1)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )

    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule.id, application.id
    )

    assert not Snapshot.objects.filter(created_automatically=True).exists()
    schedule.refresh_from_db()
    assert (
        schedule.last_runs.get(application=application).error
        == NO_ROOM_FOR_SNAPSHOT_MESSAGE
    )


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_reports_an_application_full_of_protected_snapshots(
    enterprise_data_fixture, enable_enterprise
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    enterprise_data_fixture.create_snapshot(
        snapshot_from_application=application, user=user
    )
    set_max_snapshots(application, 1)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )

    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule.id, application.id
    )

    assert not Snapshot.objects.filter(created_automatically=True).exists()
    schedule.refresh_from_db()
    assert (
        schedule.last_runs.get(application=application).error
        == NO_ROOM_FOR_SNAPSHOT_MESSAGE
    )


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_skips_an_application_with_a_max_of_zero(
    enterprise_data_fixture, enable_enterprise
):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(workspace, **DAILY)

    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule.id, application.id
    )

    assert not Snapshot.objects.exists()
    schedule.refresh_from_db()
    assert not schedule.last_runs.exists()


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_skips_an_application_that_left_the_default(
    enterprise_data_fixture, enable_enterprise
):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    default = handler.create_schedule(workspace, **DAILY)
    # The application was turned off after the run was queued.
    handler.create_schedule(workspace, application=application, enabled=False, **DAILY)

    handler.create_automatic_snapshot(default.id, application.id)

    assert not Snapshot.objects.exists()
    assert AutomaticSnapshotSchedule.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_create_automatic_snapshot_stores_a_generic_error(
    enterprise_data_fixture, enable_enterprise, mocker
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    set_max_snapshots(application, 1)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(
        workspace, application=application, **DAILY
    )
    mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.perform_create",
        side_effect=RuntimeError("connection to server at 10.0.0.5 failed"),
    )

    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule.id, application.id
    )

    schedule.refresh_from_db()
    assert (
        schedule.last_runs.get(application=application).error
        == UNEXPECTED_ERROR_MESSAGE
    )
    assert not Snapshot.objects.filter(snapshot_from_application=application).exists()


@pytest.mark.django_db(transaction=True)
def test_a_success_doesnt_clear_an_error_of_the_same_run(
    enterprise_data_fixture,
    enable_enterprise,
    mocker,
    django_capture_on_commit_callbacks,
):
    """Keep a failure across run starts and other apps succeeding, until recovery."""

    workspace = enterprise_data_fixture.create_workspace()
    set_default_max_snapshots(workspace, 1)
    first = enterprise_data_fixture.create_database_application(workspace=workspace)
    second = enterprise_data_fixture.create_database_application(workspace=workspace)
    handler = AutomaticSnapshotScheduleHandler()
    with freeze_time("2026-11-04 01:00"):
        schedule = handler.create_schedule(workspace, **DAILY)
    delay_mock = mocker.patch(
        "baserow_enterprise.automatic_snapshots.tasks.create_automatic_snapshot.delay"
    )
    perform_create = mocker.patch(
        "baserow.core.snapshots.handler.SnapshotHandler.perform_create",
        side_effect=[RuntimeError("failed"), None],
    )
    with (
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
        transaction.atomic(),
    ):
        handler.run_due_schedules()
    delay_mock.assert_called_once_with(schedule.id, first.id, [second.id])

    # The first application fails, then the second one succeeds.
    handler.create_automatic_snapshot(schedule.id, first.id)
    handler.create_automatic_snapshot(schedule.id, second.id)

    schedule.refresh_from_db()
    assert schedule.last_runs.get(application=first).error == UNEXPECTED_ERROR_MESSAGE

    # Starting the next run must not hide an unresolved failure.
    with (
        freeze_time("2026-11-05 02:00"),
        django_capture_on_commit_callbacks(execute=True),
        transaction.atomic(),
    ):
        handler.run_due_schedules()
    schedule.refresh_from_db()
    assert schedule.last_runs.get(application=first).error == UNEXPECTED_ERROR_MESSAGE

    perform_create.side_effect = None
    handler.create_automatic_snapshot(schedule.id, first.id)
    schedule.refresh_from_db()
    assert schedule.last_runs.get(application=first).error == ""
    from baserow_enterprise.automatic_snapshots.models import AutomaticSnapshotLastRun

    assert AutomaticSnapshotLastRun.objects.get(application=first).error == ""
    assert AutomaticSnapshotLastRun.objects.get(application=second).error == ""


@pytest.mark.django_db
def test_run_due_schedules_continues_after_a_failing_schedule(
    enterprise_data_fixture,
    enable_enterprise,
    delay_mock,
    mocker,
    django_capture_on_commit_callbacks,
):
    first_workspace = enterprise_data_fixture.create_workspace()
    set_default_max_snapshots(first_workspace, 1)
    second_workspace = enterprise_data_fixture.create_workspace()
    set_default_max_snapshots(second_workspace, 1)
    enterprise_data_fixture.create_database_application(workspace=first_workspace)
    application = enterprise_data_fixture.create_database_application(
        workspace=second_workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    with freeze_time("2026-11-04 01:00"):
        failing = handler.create_schedule(first_workspace, **DAILY)
        working = handler.create_schedule(second_workspace, **DAILY)

    calculate_next_due_run = handler.calculate_next_due_run

    def fail_for_one_schedule(schedule, now):
        if schedule.id == failing.id:
            raise RuntimeError("failed")
        return calculate_next_due_run(schedule, now)

    mocker.patch.object(
        handler, "calculate_next_due_run", side_effect=fail_for_one_schedule
    )
    with (
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        handler.run_due_schedules()

    delay_mock.assert_called_once_with(working.id, application.id, [])
    failing.refresh_from_db()
    working.refresh_from_db()
    assert failing.next_run_at == datetime(2026, 11, 4, 2, 0, tzinfo=timezone.utc)
    assert working.next_run_at == datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_run_due_schedules_handles_a_batch_at_a_time(
    enterprise_data_fixture,
    enable_enterprise,
    delay_mock,
    mocker,
    django_capture_on_commit_callbacks,
):
    mocker.patch(
        "baserow_enterprise.automatic_snapshots.handler.DUE_SCHEDULES_BATCH_SIZE", 1
    )
    handler = AutomaticSnapshotScheduleHandler()
    schedules = []
    for _ in range(2):
        workspace = enterprise_data_fixture.create_workspace()
        set_default_max_snapshots(workspace, 1)
        enterprise_data_fixture.create_database_application(workspace=workspace)
        with freeze_time("2026-11-04 01:00"):
            schedules.append(handler.create_schedule(workspace, **DAILY))

    with (
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        handler.run_due_schedules()
    assert delay_mock.call_count == 1

    # The schedule that didn't fit in the batch is still due, so the next check
    # handles it.
    with (
        freeze_time("2026-11-04 02:01"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        handler.run_due_schedules()
    assert delay_mock.call_count == 2
    for schedule in schedules:
        schedule.refresh_from_db()
        assert schedule.next_run_at == datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_a_schedule_below_a_raised_minimum_can_still_be_changed(
    enterprise_data_fixture,
):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    with override_settings(
        BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=1
    ):
        schedule = handler.create_schedule(
            workspace,
            application=application,
            interval="MINUTE",
            minute=15,
        )

    with override_settings(
        BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=60
    ):
        handler.update_schedule(schedule, timezone="Europe/Paris")
        handler.update_schedule(schedule, enabled=False)
        with pytest.raises(AutomaticSnapshotScheduleIntervalTooShort):
            handler.update_schedule(schedule, minute=30)

    schedule.refresh_from_db()
    assert schedule.enabled is False
    assert schedule.timezone == "Europe/Paris"
    assert schedule.minute == 15


@pytest.mark.django_db
def test_run_due_schedules_respects_a_raised_minimum(
    enterprise_data_fixture,
    enable_enterprise,
    delay_mock,
    django_capture_on_commit_callbacks,
):
    workspace = enterprise_data_fixture.create_workspace()
    set_default_max_snapshots(workspace, 1)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    with (
        override_settings(
            BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=1
        ),
        freeze_time("2026-11-04 01:45"),
    ):
        schedule = handler.create_schedule(
            workspace,
            application=application,
            interval="MINUTE",
            minute=15,
        )

    with (
        override_settings(
            BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES=60
        ),
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        handler.run_due_schedules()

    delay_mock.assert_called_once_with(schedule.id, application.id, [])
    schedule.refresh_from_db()
    assert schedule.next_run_at == datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_create_schedule_created_at_the_same_time(enterprise_data_fixture, mocker):
    workspace = enterprise_data_fixture.create_workspace()
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    handler = AutomaticSnapshotScheduleHandler()
    handler.create_schedule(workspace, application=application, **DAILY)

    # Another request created the schedule after this one checked for it.
    mocker.patch.object(QuerySet, "exists", return_value=False)
    with pytest.raises(AutomaticSnapshotScheduleAlreadyExists):
        handler.create_schedule(workspace, application=application, **DAILY)

    assert AutomaticSnapshotSchedule.objects.count() == 1


@pytest.mark.django_db
def test_queue_automatic_snapshots_skips_applications_with_a_max_of_zero(
    enterprise_data_fixture, delay_mock
):
    workspace = enterprise_data_fixture.create_workspace()
    max_of_zero = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    max_of_one = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    set_max_snapshots(max_of_one, 1)
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(workspace, **DAILY)

    AutomaticSnapshotScheduleHandler().queue_automatic_snapshots(schedule.id)

    delay_mock.assert_called_once_with(schedule.id, max_of_one.id, [])
    assert max_of_zero.id != max_of_one.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("change", ["protect", "lower_max"])
def test_create_automatic_snapshot_records_a_snapshot_replaced_right_away(
    enterprise_data_fixture, enable_enterprise, no_snapshot_deletion, mocker, change
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    enterprise_data_fixture.create_database_table(user=user, database=application)
    set_max_snapshots(application, 1)
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(workspace, application=application, **DAILY)
    with freeze_time("2026-11-04 02:00"):
        handler.create_automatic_snapshot(schedule.id, application.id)
    older = Snapshot.objects.get(created_automatically=True)

    perform_create = SnapshotHandler.perform_create

    def perform_create_then_change(self, snapshot, progress):
        perform_create(self, snapshot, progress)
        # While the new snapshot was created, an admin protected the older one or
        # lowered the max, so the new one is the oldest unprotected one beyond it.
        if change == "protect":
            Snapshot.objects.filter(id=older.id).update(protected=True)
        else:
            set_max_snapshots(application, 0)

    mocker.patch.object(SnapshotHandler, "perform_create", perform_create_then_change)
    with freeze_time("2026-11-05 02:00"):
        handler.create_automatic_snapshot(schedule.id, application.id)

    newer = Snapshot.objects.exclude(id=older.id).get(created_automatically=True)
    assert newer.mark_for_deletion is True
    schedule.refresh_from_db()
    assert (
        schedule.last_runs.get(application=application).error
        == REPLACED_RIGHT_AWAY_MESSAGE
    )
    notification = Notification.objects.get(type="automatic_snapshot_failed")
    assert notification.data["application_id"] == application.id
    assert notification.data["error"] == REPLACED_RIGHT_AWAY_MESSAGE


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("license_change", ["expired", "revoked"])
def test_a_license_that_ends_pauses_the_schedule_and_keeps_the_snapshots(
    enterprise_data_fixture,
    no_snapshot_deletion,
    delay_mock,
    django_capture_on_commit_callbacks,
    license_change,
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )
    license = enterprise_data_fixture.enable_enterprise()
    with freeze_time("2026-11-04 01:00"):
        automatic = enterprise_data_fixture.create_snapshot(
            snapshot_from_application=application,
            user=user,
            created_by=None,
            created_automatically=True,
        )
    set_max_snapshots(application, 1)
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(workspace, application=application, **DAILY)

    if license_change == "revoked":
        enterprise_data_fixture.delete_all_licenses()
        now = schedule.next_run_at
    else:
        # The first run after the license's last valid day.
        now = license.valid_through + timedelta(days=1)

    with freeze_time(now), django_capture_on_commit_callbacks(execute=True):
        handler.run_due_schedules()
        # A task queued while the license was still valid.
        handler.create_automatic_snapshot(schedule.id, application.id)

    delay_mock.assert_not_called()
    schedule.refresh_from_db()
    assert schedule.paused_reason == AUTOMATIC_SNAPSHOT_PAUSED_LICENSE
    assert schedule.enabled is True
    assert not schedule.last_runs.exists()
    # Nothing is created, and the existing automatic snapshot isn't rotated away.
    assert list(
        Snapshot.objects.filter(
            snapshot_from_application=application, mark_for_deletion=False
        ).values_list("id", flat=True)
    ) == [automatic.id]


@pytest.mark.django_db(transaction=True)
def test_an_automatic_snapshot_can_be_restored_without_the_license(
    enterprise_data_fixture, enable_enterprise
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Sales"
    )
    enterprise_data_fixture.create_database_table(user=user, database=application)
    set_max_snapshots(application, 1)
    handler = AutomaticSnapshotScheduleHandler()
    schedule = handler.create_schedule(workspace, application=application, **DAILY)
    handler.create_automatic_snapshot(schedule.id, application.id)
    snapshot = Snapshot.objects.get(created_automatically=True)

    enterprise_data_fixture.delete_all_licenses()
    restored = SnapshotHandler().perform_restore(snapshot, Progress(100), user)

    assert restored.workspace_id == workspace.id
    assert restored.id != application.id


@pytest.mark.django_db
def test_trashed_applications_and_workspaces_are_skipped(
    enterprise_data_fixture,
    enable_enterprise,
    delay_mock,
    django_capture_on_commit_callbacks,
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    set_default_max_snapshots(workspace, 1)
    kept = enterprise_data_fixture.create_database_application(workspace=workspace)
    trashed = enterprise_data_fixture.create_database_application(workspace=workspace)
    other_workspace = enterprise_data_fixture.create_workspace(user=user)
    set_default_max_snapshots(other_workspace, 1)
    enterprise_data_fixture.create_database_application(workspace=other_workspace)
    handler = AutomaticSnapshotScheduleHandler()
    with freeze_time("2026-11-04 01:00"):
        default = handler.create_schedule(workspace, **DAILY)
        other_default = handler.create_schedule(other_workspace, **DAILY)

    TrashHandler.trash(user, workspace, trashed, trashed)
    TrashHandler.trash(user, other_workspace, None, other_workspace)

    with (
        freeze_time("2026-11-04 02:00"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        handler.run_due_schedules()

    delay_mock.assert_called_once_with(default.id, kept.id, [])
    other_default.refresh_from_db()
    # The trashed workspace's schedule isn't run, so it stays due.
    assert other_default.next_run_at == datetime(2026, 11, 4, 2, 0, tzinfo=timezone.utc)

    # A task queued before the application was trashed creates nothing.
    handler.create_automatic_snapshot(default.id, trashed.id)
    assert not Snapshot.objects.filter(snapshot_from_application=trashed).exists()

    # Once restored, the workspace default covers the application again.
    TrashHandler.restore_item(user, "application", trashed.id)
    assert [app.id for app in handler.get_covered_applications(default)] == [
        kept.id,
        trashed.id,
    ]


@pytest.mark.django_db
def test_a_run_snapshots_its_applications_one_after_another(
    enterprise_data_fixture, enable_enterprise, mocker
):
    from baserow_enterprise.automatic_snapshots.tasks import (
        create_automatic_snapshot,
    )

    workspace = enterprise_data_fixture.create_workspace()
    schedule = AutomaticSnapshotScheduleHandler().create_schedule(workspace, **DAILY)
    order = []

    def snapshot(self, schedule_id, application_id):
        order.append(application_id)
        if application_id == 2:
            raise Exception("Failed")

    mocker.patch.object(
        AutomaticSnapshotScheduleHandler, "create_automatic_snapshot", snapshot
    )
    # Each task queues the next one, which runs eagerly in the tests.
    with pytest.raises(Exception, match="Failed"):
        create_automatic_snapshot.delay(schedule.id, 1, [2, 3])

    # The failure of the second application doesn't stop the third.
    assert order == [1, 2, 3]
