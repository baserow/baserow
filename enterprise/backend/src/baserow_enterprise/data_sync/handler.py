from datetime import datetime, time

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from baserow_premium.license.handler import LicenseHandler
from loguru import logger

from baserow.contrib.database.data_sync.exceptions import (
    SyncDataSyncTableAlreadyRunning,
)
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.data_sync.operations import SyncTableOperationType
from baserow.core.handler import CoreHandler
from baserow_enterprise.data_sync.models import (
    DATA_SYNC_INTERVAL_DAILY,
    DATA_SYNC_INTERVAL_HOURLY,
    DATA_SYNC_INTERVAL_MANUAL,
    DEACTIVATION_REASON_FAILURE,
    DEACTIVATION_REASON_LICENSE_UNAVAILABLE,
    PeriodicDataSyncInterval,
)
from baserow_enterprise.features import DATA_SYNC

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
        all_to_trigger = (
            PeriodicDataSyncInterval.objects.filter(
                Q(
                    # If the interval is daily, the last periodic sync timestamp must be
                    # yesterday or None meaning it hasn't been executed yet.
                    is_null | Q(last_periodic_sync__lt=beginning_of_day),
                    interval=DATA_SYNC_INTERVAL_DAILY,
                )
                | Q(
                    # If the interval is hourly, the last periodic data sync timestamp
                    # must be at least an hour ago or None meaning it hasn't been
                    # executed yet.
                    is_null | Q(last_periodic_sync__lt=beginning_of_hour),
                    interval=DATA_SYNC_INTERVAL_HOURLY,
                ),
                # Skip deactivated periodic data sync because they're not working
                # anymore.
                automatically_deactivated=False,
                # The now time must be higher than the now time because the data sync
                # must be triggered at the desired the of the user.
                when__lte=now_time,
            ).select_related("data_sync__table__database__workspace")
            # Take a lock on the periodic data sync because the `last_periodic_sync`
            # must be updated immediately. This will make sure that if this method is
            # called frequently, it doesn't trigger the same. If self or `data_sync` is
            # locked, then we can skip the sync for now because the data sync is already
            # being updated. It doesn't matter if we skip it because it will then be
            # picked up the next time this method is called.
            .select_for_update(
                of=(
                    "self",
                    "data_sync",
                ),
                skip_locked=True,
            )
        )

        updated_periodic_data_sync = []
        periodic_syncs_to_disable = []

        for periodic_data_sync in all_to_trigger:
            workspace_has_feature = LicenseHandler.workspace_has_feature(
                DATA_SYNC, periodic_data_sync.data_sync.table.database.workspace
            )
            if workspace_has_feature:
                lock_key = DataSyncHandler().get_table_sync_lock_key(
                    periodic_data_sync.data_sync_id
                )
                sync_is_running = cache.get(lock_key) is not None

                periodic_data_sync.last_periodic_sync = now
                updated_periodic_data_sync.append(periodic_data_sync)

                # If the sync is already running because the lock exists,
                # then nothing sohuld happen because the sync has already happened
                # within the correct periodic timeframe. We do want to update the
                # `last_periodic_sync`, so that it doesn't try again on the next run.
                if sync_is_running:
                    logger.info(
                        f"Skipping periodic data sync of data sync "
                        f"{periodic_data_sync.data_sync_id} because the sync already "
                        f"running."
                    )
                else:
                    transaction.on_commit(
                        lambda: sync_periodic_data_sync.delay(periodic_data_sync.id)
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
        Syncs the data sync of a periodic data sync. This is typically executed by the
        async task `sync_periodic_data_sync`.

        :param periodic_data_sync_id:  The ID of the periodic data sync object that must
            be synced. Note that this not equal to the data sync ID.
        :return: True if the data sync ran, even if it wasn't successful. False if it
            never ran.
        """

        try:
            periodic_data_sync = (
                PeriodicDataSyncInterval.objects.select_related("data_sync")
                .select_for_update(of=("self",))
                .get(id=periodic_data_sync_id, automatically_deactivated=False)
            )
        except PeriodicDataSyncInterval.DoesNotExist:
            logger.info(
                f"Skipping periodic data sync {periodic_data_sync_id} because it "
                f"doesn't exist or has been deactivated."
            )
            return False

        try:
            data_sync = DataSyncHandler().sync_data_sync_table(
                periodic_data_sync.authorized_user,
                periodic_data_sync.data_sync.specific,
            )
        except SyncDataSyncTableAlreadyRunning:
            # If the sync has started in the meantime, then we don't want to do
            # anything because the sync already ran.
            logger.info(
                f"Skipping periodic data sync of data sync "
                f"{periodic_data_sync.data_sync_id} because the sync is running."
            )
            return False

        if data_sync.last_error:
            # If the data sync has an error, then something went wrong during execution,
            # and we need to increase the consecutive count so that when the max errors
            # is reached, we can deactivate it. This to protect the system from
            # periodically syncing a data sync that doesn't work anyway.
            periodic_data_sync.consecutive_failed_count += 1
            if (
                periodic_data_sync.consecutive_failed_count
                >= settings.BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS
            ):
                periodic_data_sync.automatically_deactivated = True
                periodic_data_sync.deactivation_reason = DEACTIVATION_REASON_FAILURE

                # Send a notification to the authorized user that the periodic data
                # sync was deactivated.
                transaction.on_commit(
                    lambda: PeriodicDataSyncDeactivatedNotificationType.notify_authorized_user(
                        periodic_data_sync
                    )
                )

            periodic_data_sync.save()
        elif periodic_data_sync.consecutive_failed_count > 0:
            # Once it runs successfully, the consecutive count can be reset because we
            # now know it actually works, and it doesn't have to be deactivated anymore.
            periodic_data_sync.consecutive_failed_count = 0
            periodic_data_sync.save()

        return True
