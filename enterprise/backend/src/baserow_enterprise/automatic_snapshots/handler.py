from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from loguru import logger

from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
)
from baserow.contrib.integrations.core.utils import calculate_next_periodic_run
from baserow.core.datetime import get_timezones
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.models import Application, Snapshot, Workspace
from baserow.core.registries import application_type_registry
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    MaxSnapshotsFullOfProtected,
    MaxSnapshotsIsZero,
    SnapshotIsBeingCreated,
)
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.snapshots.quota_handler import SnapshotQuotaHandler
from baserow.core.utils import Progress, extract_allowed
from baserow_enterprise.features import AUTOMATIC_SNAPSHOTS
from baserow_premium.license.handler import LicenseHandler

from .exceptions import (
    AutomaticSnapshotScheduleAlreadyExists,
    AutomaticSnapshotScheduleDoesNotExist,
    AutomaticSnapshotScheduleIntervalTooShort,
    AutomaticSnapshotScheduleInvalid,
)
from .models import (
    AUTOMATIC_SNAPSHOT_PAUSED_LICENSE,
    AutomaticSnapshotLastRun,
    AutomaticSnapshotSchedule,
)
from .notification_types import AutomaticSnapshotFailedNotificationType

# The shortest length, in minutes, of each interval. A month is at least 28 days.
INTERVAL_MINIMUM_MINUTES = {
    PERIODIC_INTERVAL_HOUR: 60,
    PERIODIC_INTERVAL_DAY: 60 * 24,
    PERIODIC_INTERVAL_WEEK: 60 * 24 * 7,
    PERIODIC_INTERVAL_MONTH: 60 * 24 * 28,
}

UNEXPECTED_ERROR_MESSAGE = "Something went wrong while creating the snapshot."
NO_ROOM_FOR_SNAPSHOT_MESSAGE = "There is not enough room to create a new snapshot."
REPLACED_RIGHT_AWAY_MESSAGE = (
    "The new snapshot was deleted right after it was created, because the "
    "application's other snapshots were protected or its max snapshots was lowered "
    "in the meantime."
)

# The most due schedules a single check handles. The rest are still due, so the next
# check handles them.
DUE_SCHEDULES_BATCH_SIZE = 500

SCHEDULE_FIELDS = [
    "enabled",
    "interval",
    "timezone",
    "minute",
    "hour",
    "day_of_week",
    "day_of_month",
]


SCHEDULE_STATE_WORKSPACE_DEFAULT = "workspace_default"
SCHEDULE_STATE_OWN_SCHEDULE = "own_schedule"
SCHEDULE_STATE_OFF = "off"


def get_schedule_state(schedule: Optional["AutomaticSnapshotSchedule"]) -> str:
    """
    Returns which schedule an application follows, given its own schedule.

    :param schedule: The schedule of the application, or `None` if it doesn't have
        one.
    :return: `workspace_default`, `own_schedule` or `off`.
    """

    if schedule is None:
        return SCHEDULE_STATE_WORKSPACE_DEFAULT
    return SCHEDULE_STATE_OWN_SCHEDULE if schedule.enabled else SCHEDULE_STATE_OFF


@dataclass
class UpdatedAutomaticSnapshotSchedule:
    schedule: AutomaticSnapshotSchedule
    original_values: Dict[str, Any]
    new_values: Dict[str, Any]


class AutomaticSnapshotScheduleHandler:
    def get_schedule(
        self,
        schedule_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> AutomaticSnapshotSchedule:
        """
        Returns the schedule with the provided id.

        :param schedule_id: The id of the schedule.
        :param base_queryset: An optional queryset to select the schedule from.
        :raises AutomaticSnapshotScheduleDoesNotExist: When the schedule doesn't
            exist.
        :return: The schedule.
        """

        if base_queryset is None:
            base_queryset = AutomaticSnapshotSchedule.objects.all()

        try:
            return base_queryset.select_related("workspace", "application").get(
                id=schedule_id
            )
        except AutomaticSnapshotSchedule.DoesNotExist:
            raise AutomaticSnapshotScheduleDoesNotExist()

    def get_application_schedule(
        self, application: Application, for_update: bool = False
    ) -> AutomaticSnapshotSchedule:
        """
        Returns the schedule of the provided application.

        :param application: The application to get the schedule of.
        :param for_update: Whether to lock the schedule for update.
        :raises AutomaticSnapshotScheduleDoesNotExist: When the application doesn't
            have a schedule of its own.
        :return: The schedule.
        """

        queryset = AutomaticSnapshotSchedule.objects.filter(application=application)
        if for_update:
            queryset = queryset.select_for_update(of=("self",))

        try:
            return queryset.select_related("workspace", "application").get()
        except AutomaticSnapshotSchedule.DoesNotExist:
            raise AutomaticSnapshotScheduleDoesNotExist()

    def get_workspace_default(
        self, workspace: Workspace, for_update: bool = False
    ) -> AutomaticSnapshotSchedule:
        """
        Returns the workspace default schedule of the provided workspace.

        :param workspace: The workspace to get the default schedule of.
        :param for_update: Whether to lock the schedule for update.
        :raises AutomaticSnapshotScheduleDoesNotExist: When the workspace doesn't
            have a default schedule.
        :return: The schedule.
        """

        queryset = AutomaticSnapshotSchedule.objects.filter(
            workspace=workspace, application__isnull=True
        )
        if for_update:
            queryset = queryset.select_for_update(of=("self",))

        try:
            return queryset.select_related("workspace").get()
        except AutomaticSnapshotSchedule.DoesNotExist:
            raise AutomaticSnapshotScheduleDoesNotExist()

    def list_workspace_schedules(self, workspace: Workspace) -> QuerySet:
        """
        Returns every schedule of the provided workspace: the workspace default, if
        there is one, and the schedules of its applications.

        :param workspace: The workspace to list the schedules of.
        :return: A queryset of schedules.
        """

        return AutomaticSnapshotSchedule.objects.filter(
            workspace=workspace
        ).select_related("application")

    def validate_values(
        self, values: Dict[str, Any], check_min_interval: bool = True
    ) -> None:
        """
        Validates the schedule values, including the shortest interval allowed by
        `BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES`.

        :param values: The complete schedule values.
        :param check_min_interval: Whether to check the shortest interval allowed.
        :raises AutomaticSnapshotScheduleInvalid: When a value is out of range.
        :raises AutomaticSnapshotScheduleIntervalTooShort: When the schedule runs
            more often than allowed.
        """

        interval = values["interval"]
        minute = values["minute"]

        if values["timezone"] not in get_timezones():
            raise AutomaticSnapshotScheduleInvalid(
                f"The timezone `{values['timezone']}` is not a valid timezone."
            )
        if not 0 <= values["hour"] <= 23:
            raise AutomaticSnapshotScheduleInvalid("The hour must be between 0-23.")
        if not 0 <= values["day_of_week"] <= 6:
            raise AutomaticSnapshotScheduleInvalid(
                "The day of the week must be between 0-6."
            )
        if not 1 <= values["day_of_month"] <= 31:
            raise AutomaticSnapshotScheduleInvalid(
                "The day of the month must be between 1-31."
            )

        if interval == PERIODIC_INTERVAL_MINUTE:
            if minute < 1:
                raise AutomaticSnapshotScheduleInvalid(
                    "The number of minutes between runs must be at least 1."
                )
            interval_minutes = minute
        else:
            if not 0 <= minute <= 59:
                raise AutomaticSnapshotScheduleInvalid(
                    "The minute must be between 0-59."
                )
            interval_minutes = INTERVAL_MINIMUM_MINUTES[interval]

        min_interval = (
            settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES
        )
        if check_min_interval and interval_minutes < min_interval:
            raise AutomaticSnapshotScheduleIntervalTooShort(
                f"Automatic snapshots can't run more often than every {min_interval} "
                "minutes."
            )

    def calculate_next_run(
        self,
        schedule: AutomaticSnapshotSchedule,
        from_time: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        Calculates the next time the provided schedule runs.

        :param schedule: The schedule.
        :param from_time: Calculate the next run from this time, defaults to now.
        :return: The next run time in UTC.
        """

        return calculate_next_periodic_run(
            interval=schedule.interval,
            minute=schedule.minute,
            hour=schedule.hour,
            day_of_week=schedule.day_of_week,
            day_of_month=schedule.day_of_month,
            from_time=from_time,
            tz=schedule.timezone,
        )

    def calculate_next_due_run(
        self, schedule: AutomaticSnapshotSchedule, now: datetime
    ) -> Optional[datetime]:
        """
        Calculates the next run of a schedule that is running now. A schedule saved
        before the shortest interval allowed was raised can run more often than
        allowed, so its next run is moved to the first one after that interval.

        :param schedule: The schedule that is running.
        :param now: The time of the current run.
        :return: The next run time in UTC.
        """

        next_run = self.calculate_next_run(schedule, from_time=now)
        earliest = now + timedelta(
            minutes=settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES
        )
        if next_run is None or next_run >= earliest:
            return next_run
        if schedule.interval == PERIODIC_INTERVAL_MINUTE:
            # A frequency, so it runs as soon as the shortest interval allows.
            return earliest
        # Runs are calculated strictly after `from_time`, to the minute.
        return self.calculate_next_run(
            schedule, from_time=earliest - timedelta(minutes=1)
        )

    def create_schedule(
        self,
        workspace: Workspace,
        application: Optional[Application] = None,
        **kwargs,
    ) -> AutomaticSnapshotSchedule:
        """
        Creates a schedule for the provided application, or the workspace default
        when no application is provided.

        :param workspace: The workspace the schedule belongs to.
        :param application: The application to create the schedule for. `None`
            creates the workspace default.
        :param kwargs: The schedule values.
        :raises AutomaticSnapshotScheduleAlreadyExists: When the application, or the
            workspace, already has a schedule.
        :return: The created schedule.
        """

        existing = AutomaticSnapshotSchedule.objects.filter(
            workspace=workspace, application=application
        )
        if existing.exists():
            raise AutomaticSnapshotScheduleAlreadyExists()

        schedule = AutomaticSnapshotSchedule(
            workspace=workspace,
            application=application,
            **extract_allowed(kwargs, SCHEDULE_FIELDS),
        )
        self.validate_values(
            {field: getattr(schedule, field) for field in SCHEDULE_FIELDS}
        )
        schedule.next_run_at = self.calculate_next_run(schedule)
        try:
            with transaction.atomic():
                schedule.save()
        except IntegrityError:
            # Another request created the schedule after the check above.
            raise AutomaticSnapshotScheduleAlreadyExists()
        return schedule

    def update_schedule(
        self, schedule: AutomaticSnapshotSchedule, **kwargs
    ) -> UpdatedAutomaticSnapshotSchedule:
        """
        Updates the provided schedule.

        :param schedule: The schedule to update.
        :param kwargs: The schedule values to change.
        :return: The updated schedule, with its original and new values.
        """

        original_values = {field: getattr(schedule, field) for field in SCHEDULE_FIELDS}
        allowed_values = extract_allowed(kwargs, SCHEDULE_FIELDS)
        for name, value in allowed_values.items():
            setattr(schedule, name, value)

        new_values = {field: getattr(schedule, field) for field in SCHEDULE_FIELDS}
        # The shortest interval allowed can be raised after the schedule was saved, so
        # it's only checked when the interval changes. This way the schedule can still
        # be turned off, or have its other values changed.
        interval_changed = any(
            original_values[field] != new_values[field]
            for field in ["interval", "minute"]
        )
        self.validate_values(new_values, check_min_interval=interval_changed)
        schedule.next_run_at = self.calculate_next_run(schedule)
        schedule.save()
        return UpdatedAutomaticSnapshotSchedule(schedule, original_values, new_values)

    def delete_schedule(self, schedule: AutomaticSnapshotSchedule) -> None:
        """
        Deletes the provided schedule. The automatic snapshots it created are kept.

        :param schedule: The schedule to delete.
        """

        schedule_id = schedule.id
        schedule.delete()
        # Django clears the id of a deleted instance, but the audit log entry of
        # the deletion still refers to it.
        schedule.id = schedule_id

    def get_covered_applications(
        self, schedule: AutomaticSnapshotSchedule
    ) -> List[Application]:
        """
        Returns the applications the provided schedule creates snapshots of. A
        schedule of an application covers that application. The workspace default
        covers every application in the workspace without a schedule of its own.
        Trashed applications are never covered.

        :param schedule: The schedule.
        :return: The covered applications.
        """

        return list(
            self._get_covered_applications_queryset(schedule)
            .select_related("workspace")
            .order_by("id")
        )

    def _get_covered_applications_queryset(
        self, schedule: AutomaticSnapshotSchedule
    ) -> QuerySet:
        """
        Returns a queryset of the applications the provided schedule covers. See
        `get_covered_applications`.

        :param schedule: The schedule.
        :return: The queryset of covered applications.
        """

        applications = Application.objects.filter(workspace_id=schedule.workspace_id)
        if schedule.is_workspace_default:
            return applications.exclude(automatic_snapshot_schedules__isnull=False)
        return applications.filter(id=schedule.application_id)

    def run_due_schedules(self, now: Optional[datetime] = None) -> None:
        """
        Finds the enabled schedules that are due, moves them to their next run and
        queues the snapshots of the applications they cover. The licence of each
        workspace is checked before anything is queued, and a schedule of a
        workspace without it is paused. Missed runs are not caught up.

        At most `DUE_SCHEDULES_BATCH_SIZE` schedules are handled per call, and each
        one in its own savepoint, so a schedule that fails doesn't stop the others.

        :param now: The current time, defaults to now.
        """

        if now is None:
            now = timezone.now()
        now = now.replace(second=0, microsecond=0)

        due_schedules = (
            AutomaticSnapshotSchedule.objects.filter(
                enabled=True,
                next_run_at__lte=now,
                workspace__trashed=False,
            )
            .select_related("workspace")
            .select_for_update(of=("self",), skip_locked=True)
            .order_by("next_run_at", "id")[:DUE_SCHEDULES_BATCH_SIZE]
        )

        licensed_by_workspace_id: Dict[int, bool] = {}
        for schedule in due_schedules:
            try:
                with transaction.atomic():
                    self._start_run(schedule, now, licensed_by_workspace_id)
            except Exception:
                logger.exception(
                    "Automatic snapshot schedule {} could not be run.", schedule.id
                )

    def _start_run(
        self,
        schedule: AutomaticSnapshotSchedule,
        now: datetime,
        licensed_by_workspace_id: Dict[int, bool],
    ) -> None:
        """
        Moves the provided due schedule to its next run, and queues the task that
        queues its snapshots once the transaction is committed.

        :param schedule: The due schedule.
        :param now: The time of the current run.
        :param licensed_by_workspace_id: Whether each workspace already checked has
            the licence.
        """

        from .tasks import queue_automatic_snapshots

        schedule.next_run_at = self.calculate_next_due_run(schedule, now)

        workspace_id = schedule.workspace_id
        if workspace_id not in licensed_by_workspace_id:
            licensed_by_workspace_id[workspace_id] = (
                LicenseHandler.workspace_has_feature(
                    AUTOMATIC_SNAPSHOTS, schedule.workspace
                )
            )

        if not licensed_by_workspace_id[workspace_id]:
            schedule.paused_reason = AUTOMATIC_SNAPSHOT_PAUSED_LICENSE
            schedule.save(update_fields=["next_run_at", "paused_reason"])
            return

        # Keep the previous failure until that application successfully snapshots.
        schedule.paused_reason = None
        schedule.save(update_fields=["next_run_at", "paused_reason"])

        transaction.on_commit(
            lambda schedule_id=schedule.id: queue_automatic_snapshots.delay(schedule_id)
        )

    def queue_automatic_snapshots(self, schedule_id: int) -> None:
        """
        Queues the snapshots of every application the provided schedule covers.
        They run one after another: the task of each application queues the next
        one, so a run never takes more than one worker at a time.

        :param schedule_id: The id of the schedule that is running.
        """

        from .tasks import create_automatic_snapshot

        try:
            schedule = self.get_schedule(schedule_id)
        except AutomaticSnapshotScheduleDoesNotExist:
            return

        if not schedule.enabled:
            return

        quota_handler = SnapshotQuotaHandler()
        # Applications with a max of 0 snapshots are left out, so no task is queued
        # for them.
        application_ids = [
            application.id
            for application in self.get_covered_applications(schedule)
            if quota_handler.get_effective_max_snapshots(application) != 0
        ]
        if application_ids:
            create_automatic_snapshot.delay(
                schedule.id, application_ids[0], application_ids[1:]
            )

    def get_snapshot_name(
        self, schedule: AutomaticSnapshotSchedule, application: Application
    ) -> str:
        """
        Returns a unique name for a new automatic snapshot, based on the current
        time in the timezone of the schedule.

        :param schedule: The schedule creating the snapshot.
        :param application: The application the snapshot is created of.
        :return: The snapshot name.
        """

        from zoneinfo import ZoneInfo

        local_now = timezone.now().astimezone(ZoneInfo(schedule.timezone))
        base_name = f"Automatic snapshot {local_now:%Y-%m-%d %H:%M}"
        existing_names = set(
            Snapshot.objects.filter(
                snapshot_from_application=application,
                name__startswith=base_name,
            ).values_list("name", flat=True)
        )

        name = base_name
        suffix = 2
        while name in existing_names:
            name = f"{base_name} ({suffix})"
            suffix += 1
        return name

    def create_automatic_snapshot(self, schedule_id: int, application_id: int) -> None:
        """
        Creates an automatic snapshot of the provided application, then deletes its
        oldest unprotected snapshots beyond the application's max snapshots. An
        application with a max of 0 snapshots is skipped. The licence is checked again
        first, because it can expire or be revoked while the task waits in the queue.
        Nothing is created or deleted when it isn't valid.

        :param schedule_id: The id of the schedule creating the snapshot.
        :param application_id: The id of the application to snapshot.
        """

        try:
            schedule = self.get_schedule(schedule_id)
        except AutomaticSnapshotScheduleDoesNotExist:
            return

        if not schedule.enabled:
            return

        if not LicenseHandler.workspace_has_feature(
            AUTOMATIC_SNAPSHOTS, schedule.workspace
        ):
            AutomaticSnapshotSchedule.objects.filter(id=schedule.id).update(
                paused_reason=AUTOMATIC_SNAPSHOT_PAUSED_LICENSE
            )
            return

        try:
            application = (
                Application.objects.filter(
                    id=application_id,
                    workspace_id=schedule.workspace_id,
                    workspace__trashed=False,
                )
                .select_related("workspace")
                .get()
            )
        except Application.DoesNotExist:
            return

        # The schedule may have changed since this task was queued, for example the
        # application got a schedule of its own, or it was turned off.
        if (
            not self._get_covered_applications_queryset(schedule)
            .filter(id=application.id)
            .exists()
        ):
            return

        snapshot_handler = SnapshotHandler()
        try:
            snapshot = snapshot_handler.create_automatic(
                application, self.get_snapshot_name(schedule, application)
            )
        except (
            SnapshotIsBeingCreated,
            MaxSnapshotsIsZero,
        ):
            # A manual snapshot is already being created, or this application has
            # opted out of snapshots by setting its max to 0.
            return
        except (
            MaximumSnapshotsReached,
            MaxSnapshotsFullOfProtected,
            ApplicationOperationNotSupported,
        ) as exc:
            self._record_failure(schedule, exc, application)
            return
        except Exception as exc:
            logger.exception(
                "Starting automatic snapshot of application {} failed.", application.id
            )
            self._record_failure(schedule, exc, application)
            return

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        try:
            with application_type.export_safe_transaction_context(application.specific):
                snapshot_handler.perform_create(snapshot, Progress(100))
        except Exception as exc:
            logger.exception(
                "Automatic snapshot of application {} failed.", application.id
            )
            snapshot.delete()
            self._record_failure(schedule, exc, application)
            return

        try:
            snapshot_handler.rotate_after_create(application.id)
        except Exception:
            # The snapshot was created, so the run succeeded. The snapshots beyond
            # the max snapshots are deleted by the next rotation instead.
            logger.exception(
                "Rotating the snapshots of application {} failed.", application.id
            )
            self._record_run_result(schedule, application)
            return

        # The rotation deletes the oldest unprotected snapshots beyond the max. When
        # the other snapshots were protected, or the max lowered, while this one was
        # created, that's the new snapshot itself, so the run tells why it's gone.
        if Snapshot.objects.filter(id=snapshot.id, mark_for_deletion=True).exists():
            self._record_run_result(schedule, application, REPLACED_RIGHT_AWAY_MESSAGE)
        else:
            self._record_run_result(schedule, application)

    def _record_failure(
        self,
        schedule: AutomaticSnapshotSchedule,
        exc: Exception,
        application: Application,
    ) -> None:
        """
        Records the failed application attempt for the snapshots modal. Only known
        failures get a specific message. Any other failure gets a generic one, and
        its details are only in the server log.

        :param schedule: The schedule that ran.
        :param exc: The exception the attempt failed with.
        :param application: The application the attempt was for.
        """

        if isinstance(exc, DatabaseSnapshotMaxLocksExceededException):
            message = DatabaseSnapshotMaxLocksExceededException.message
        elif isinstance(exc, (MaximumSnapshotsReached, MaxSnapshotsFullOfProtected)):
            message = NO_ROOM_FOR_SNAPSHOT_MESSAGE
        elif isinstance(exc, ApplicationOperationNotSupported):
            message = "The application doesn't support snapshots."
        else:
            message = UNEXPECTED_ERROR_MESSAGE
        self._record_run_result(schedule, application, message)

    def _record_run_result(
        self,
        schedule: AutomaticSnapshotSchedule,
        application: Application,
        error: str = "",
    ) -> None:
        """
        Keeps the result of the latest attempt of the provided application. The
        workspace admins are notified when it fails for a new reason: the previous
        attempt succeeded, there was none, or it failed with another error. A
        failure that repeats on every run notifies them only once.

        :param schedule: The schedule that ran.
        :param application: The application the attempt was for.
        :param error: The error the attempt failed with, empty when it succeeded.
        """

        with transaction.atomic():
            previous_error = (
                AutomaticSnapshotLastRun.objects.select_for_update()
                .filter(application=application)
                .values_list("error", flat=True)
                .first()
            )
            AutomaticSnapshotLastRun.objects.update_or_create(
                application=application,
                defaults={
                    "schedule": schedule,
                    "finished_at": timezone.now(),
                    "error": error,
                },
            )
            if error and error != previous_error:
                AutomaticSnapshotFailedNotificationType.notify_admins(
                    schedule, application, error
                )
