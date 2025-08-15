from django.conf import settings
from django.db import transaction

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.models import DataSync, DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import (
    TwoWaySyncStrategy,
    data_sync_type_registry,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.signals import table_updated
from baserow_enterprise.features import DATA_SYNC

from .notification_types import (
    TwoWaySyncDeactivatedNotificationType,
    TwoWaySyncUpdateFailedNotificationType,
)


class RealtimePushTwoWaySyncStrategy(TwoWaySyncStrategy):
    """
    Two-way data sync strategy that pushes the changes made in the synced table
    directly to the data sync source. It's a simple implementation that just uses the
    data sync type to create everything is real-time.

    The changes made in the source table must be synced in periodically or manually.
    This strategy is perfect for systems where you can write to, but not receive
    real-time events. Because the source table will always be up to date, there will
    be no conflicts.
    """

    type = "realtime_push"

    def before_enable(self, workspace):
        LicenseHandler.raise_if_workspace_doesnt_have_feature(DATA_SYNC, workspace)

    def _deactivate_two_way_sync(self, data_sync):
        data_sync.two_way_sync = False
        data_sync.save()
        # Change all the fields to read only because it should not be
        # possible to change the cell value after the two-way sync is
        # disabled.
        Field.objects.filter(
            id__in=DataSyncSyncedProperty.objects.filter(
                data_sync=data_sync,
                field__read_only=False,
            ).values_list("field_id", flat=True)
        ).update(read_only=True)
        TwoWaySyncDeactivatedNotificationType.notify_admins_in_workspace(data_sync)
        table_updated.send(
            self, table=data_sync.table, user=None, force_table_refresh=False
        )

    def retry_of_fail_with_notification(self, sync_error, task_context, data_sync):
        if task_context.request.retries >= settings.BASEROW_TWO_WAY_SYNC_MAX_RETRIES:
            data_sync.two_way_sync_consecutive_failures += 1
            data_sync.save()

            TwoWaySyncUpdateFailedNotificationType.notify_admins_in_workspace(
                data_sync, str(sync_error)
            )

            # If the update failed 8 consecutive times, excluding the retries,
            # then there is a problem with the two-way data sync, and we want to
            # disable it.
            if (
                data_sync.two_way_sync_consecutive_failures
                >= settings.BASEROW_TWO_WAY_SYNC_MAX_CONSECUTIVE_FAILURES
            ):
                with transaction.atomic():
                    # Do a select_for_update to avoid creating multiple notifications if
                    # errors occur concurrently.
                    data_sync = (
                        DataSync.objects.filter(pk=data_sync.id, two_way_sync=True)
                        .select_for_update()
                        .first()
                    )
                    if data_sync:
                        self._deactivate_two_way_sync(data_sync)
        else:
            # Retries the task with an exponential backoff.
            task_context.retry(countdown=2**task_context.request.retries)

    def reset_failures_if_needed(self, data_sync):
        if data_sync.two_way_sync_consecutive_failures > 0:
            data_sync.two_way_sync_consecutive_failures = 0
            data_sync.save()

    def rows_created(self, task_context, serialized_rows, data_sync):
        if not LicenseHandler.workspace_has_feature(
            DATA_SYNC, data_sync.table.database.workspace
        ):
            return

        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)

        try:
            # This creates the row in the data sync source using the protocol of the
            # data sync type. Note that the returned list can contain a list of changes
            # that must be applied in the Baserow table. This can be the case when the
            # unique ID is managed by the data source.
            rows_to_update = data_sync_type.create_rows(serialized_rows, data_sync)
        except SyncError as sync_error:
            return self.retry_of_fail_with_notification(
                sync_error, task_context, data_sync
            )

        self.reset_failures_if_needed(data_sync)

        if rows_to_update is None:
            return

        rows_to_update = [
            row
            for row in rows_to_update
            # Filter out the objects that don't contain any updates.
            if row and not (len(row) == 1 and "id" in row)
        ]

        if len(rows_to_update) == 0:
            return

        # When creating a row, it's possible that the unique primary value was
        # generated. If the data sync returns a list of dict rows, it means that some
        # values must be updated.
        with transaction.atomic():
            RowHandler().force_update_rows(
                user=None,
                table=data_sync.table,
                rows_values=rows_to_update,
                signal_params={"skip_two_way_sync": True},
            )

    def rows_updated(self, task_context, serialized_rows, data_sync, updated_field_ids):
        if not LicenseHandler.workspace_has_feature(
            DATA_SYNC, data_sync.table.database.workspace
        ):
            return

        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)

        try:
            data_sync_type.update_rows(serialized_rows, data_sync, updated_field_ids)
        except SyncError as sync_error:
            return self.retry_of_fail_with_notification(
                sync_error, task_context, data_sync
            )

        self.reset_failures_if_needed(data_sync)

    def rows_deleted(self, task_context, serialized_rows, data_sync):
        if not LicenseHandler.workspace_has_feature(
            DATA_SYNC, data_sync.table.database.workspace
        ):
            return

        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)

        try:
            data_sync_type.delete_rows(serialized_rows, data_sync)
        except SyncError as sync_error:
            return self.retry_of_fail_with_notification(
                sync_error, task_context, data_sync
            )

        self.reset_failures_if_needed(data_sync)
