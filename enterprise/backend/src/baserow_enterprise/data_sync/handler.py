from datetime import datetime, time

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from loguru import logger

from baserow.contrib.database.api.data_sync.errors import (
    ERROR_SYNC_DATA_SYNC_ALREADY_RUNNING,
)
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.models import (
    DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    DataSync,
)
from baserow.contrib.database.data_sync.operations import SyncTableOperationType
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow_enterprise.data_sync.models import (
    DATA_SYNC_INTERVAL_DAILY,
    DATA_SYNC_INTERVAL_HOURLY,
    DATA_SYNC_INTERVAL_MANUAL,
    DEACTIVATION_REASON_FAILURE,
    DEACTIVATION_REASON_LICENSE_UNAVAILABLE,
    PeriodicDataSyncInterval,
)
from baserow_enterprise.features import DATA_SYNC
from baserow_premium.license.handler import LicenseHandler

from .notification_types import PeriodicDataSyncDeactivatedNotificationType
from .tasks import sync_periodic_data_sync


class EnterpriseDataSyncHandler:
    @classmethod
    def update_periodic_data_sync_interval(
        cls,
        user: AbstractUser,
        data_sync: DataSync,
        interval: str,
        when: time,
    ) -> PeriodicDataSyncInterval:
        """
        Updates the periodic configuration of a data sync.

        :param user: The user on whose behalf the periodic configuration is updated.
            This user is saved on the object, and is used when syncing the data sync.
        :param data_sync: The data sync where the periodic configuration must be
            updated for.
        :param interval: Accepts either `DATA_SYNC_INTERVAL_DAILY` or
            `DATA_SYNC_INTERVAL_DAILY` indicating how frequently the data sync must be
            updated.
        :param when: Indicates when the data sync must periodically be synced.
        :return: The created or updated periodic data sync object.
        """

        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, data_sync.table.database.workspace
        )

        CoreHandler().check_permissions(
            user,
            SyncTableOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )

        periodic_data_sync, _ = PeriodicDataSyncInterval.objects.update_or_create(
            data_sync=data_sync,
            defaults={
                "interval": interval,
                "when": when,
                "authorized_user": user,
                "automatically_deactivated": False,
            },
        )

        return periodic_data_sync

    @classmethod
    def call_periodic_data_sync_syncs_that_are_due(cls):
        """
        This method is typically called by an async task. It loops over all daily and
        hourly periodic data sync that are due to the synced, and fires a task for each
        to sync it.
        """

        now = timezone.now()
        now_time = time(
            now.hour, now.minute, now.second, now.microsecond, tzinfo=now.tzinfo
        )
        beginning_of_day = datetime(
            now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=now.tzinfo
        )
        beginning_of_hour = datetime(
            now.year, now.month, now.day, now.hour, 0, 0, 0, tzinfo=now.tzinfo
        )

        is_null = Q(last_periodic_sync__isnull=True)
        daily_due = Q(
            # If the interval is daily, the last periodic sync timestamp must be
            # yesterday or None meaning it hasn't been executed yet.
            is_null | Q(last_periodic_sync__lt=beginning_of_day),
            interval=DATA_SYNC_INTERVAL_DAILY,
            # The data sync must be triggered at the time desired by the user.
            when__lte=now_time,
        )
        hourly_due = Q(
            # If the interval is hourly, the last periodic data sync timestamp
            # must be at least an hour ago or None meaning it hasn't been
            # executed yet.
            is_null | Q(last_periodic_sync__lt=beginning_of_hour),
            # Only the minute and second of `when` matter because it runs every hour.
            Q(when__minute__lt=now.minute)
            | Q(when__minute=now.minute, when__second__lte=now.second),
            interval=DATA_SYNC_INTERVAL_HOURLY,
        )
        all_to_trigger = (
            PeriodicDataSyncInterval.objects.filter(
                daily_due | hourly_due,
                # Skip deactivated periodic data sync because they're not working
                # anymore.
                automatically_deactivated=False,
            )
            .select_related("data_sync__table__database__workspace")
            # Take a lock on the periodic data sync because the `last_periodic_sync`
            # must be updated immediately. This will make sure that if this method is
            # called frequently, it doesn't trigger the same. If self or `data_sync` is
            # locked, then we can skip the sync for now because the data sync is already
            # being updated. It doesn't matter if we skip it because it will then be
            # picked up the next time this method is called.
            .select_for_update(of=("self", "data_sync"), skip_locked=True)
        )

        updated_periodic_data_sync = []
        periodic_syncs_to_disable = []

        for periodic_data_sync in all_to_trigger:
            workspace_has_feature = LicenseHandler.workspace_has_feature(
                DATA_SYNC, periodic_data_sync.data_sync.table.database.workspace
            )
            if workspace_has_feature:
                periodic_data_sync.last_periodic_sync = now
                updated_periodic_data_sync.append(periodic_data_sync)

                transaction.on_commit(
                    lambda pds_id=periodic_data_sync.id: sync_periodic_data_sync.delay(
                        pds_id
                    )
                )
            else:
                periodic_data_sync.interval = DATA_SYNC_INTERVAL_MANUAL
                periodic_data_sync.automatically_deactivated = True
                periodic_data_sync.deactivation_reason = (
                    DEACTIVATION_REASON_LICENSE_UNAVAILABLE
                )
                periodic_syncs_to_disable.append(periodic_data_sync)

        # Update the last periodic sync so the periodic sync won't be triggerd the next
        # time this method is called.
        if len(updated_periodic_data_sync) > 0:
            PeriodicDataSyncInterval.objects.bulk_update(
                updated_periodic_data_sync, fields=["last_periodic_sync"]
            )

        if len(periodic_syncs_to_disable) > 0:
            PeriodicDataSyncInterval.objects.bulk_update(
                periodic_syncs_to_disable,
                fields=["interval", "automatically_deactivated", "deactivation_reason"],
            )

            for periodic_data_sync in periodic_syncs_to_disable:
                transaction.on_commit(
                    lambda pds=periodic_data_sync: PeriodicDataSyncDeactivatedNotificationType.notify_authorized_user(
                        pds
                    )
                )

    @classmethod
    def sync_periodic_data_sync(cls, periodic_data_sync_id):
        """
        Syncs the data sync of a periodic data sync by running a
        `sync_data_sync_table` job on behalf of the authorized user, so that the
        run is recorded in the sync job history. This is typically executed by
        the async task `sync_periodic_data_sync`.

        :param periodic_data_sync_id:  The ID of the periodic data sync object that must
            be synced. Note that this not equal to the data sync ID.
        :return: True if the data sync ran, even if it wasn't successful. False if it
            never ran.
        """

        try:
            periodic_data_sync = PeriodicDataSyncInterval.objects.select_related(
                "data_sync"
            ).get(id=periodic_data_sync_id, automatically_deactivated=False)
        except PeriodicDataSyncInterval.DoesNotExist:
            logger.info(
                f"Skipping periodic data sync {periodic_data_sync_id} because it "
                f"doesn't exist or has been deactivated."
            )
            return False

        authorized_user = periodic_data_sync.authorized_user
        data_sync_id = periodic_data_sync.data_sync_id

        # The job runs outside a transaction: its context sets the isolation level.
        try:
            job = JobHandler().create_and_start_job(
                authorized_user,
                SyncDataSyncTableJobType.type,
                sync=True,
                data_sync_id=data_sync_id,
                triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
            )
        except MaxJobCountExceeded:
            # A pending/running sync job means it already ran within this timeframe.
            logger.info(
                f"Skipping periodic data sync of data sync {data_sync_id} because "
                f"a sync job is already running."
            )
            return False
        except Exception:
            # Job creation errors and unexpected run errors both count as failed runs.
            logger.exception(
                f"The periodic data sync of data sync {data_sync_id} failed."
            )
            run_failed = True
        else:
            # A lost race with a concurrent manual sync is not a real failure.
            run_failed = (
                job.failed
                and job.human_readable_error != ERROR_SYNC_DATA_SYNC_ALREADY_RUNNING[2]
            )

        with transaction.atomic():
            try:
                periodic_data_sync = PeriodicDataSyncInterval.objects.select_for_update(
                    of=("self",)
                ).get(id=periodic_data_sync_id)
            except PeriodicDataSyncInterval.DoesNotExist:
                return True

            if run_failed:
                # Deactivate after too many consecutive failures to protect the system.
                periodic_data_sync.consecutive_failed_count += 1
                if (
                    periodic_data_sync.consecutive_failed_count
                    >= settings.BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS
                ):
                    periodic_data_sync.automatically_deactivated = True
                    periodic_data_sync.deactivation_reason = DEACTIVATION_REASON_FAILURE
                    transaction.on_commit(
                        lambda: PeriodicDataSyncDeactivatedNotificationType.notify_authorized_user(
                            periodic_data_sync
                        )
                    )

                periodic_data_sync.save()
            elif periodic_data_sync.consecutive_failed_count > 0:
                # A successful run proves it works again, so the count can reset.
                periodic_data_sync.consecutive_failed_count = 0
                periodic_data_sync.save()

        return True
