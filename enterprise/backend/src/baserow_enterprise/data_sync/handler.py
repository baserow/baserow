from datetime import time

from django.contrib.auth.models import AbstractUser

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.table.operations import UpdateDatabaseTableOperationType
from baserow.core.handler import CoreHandler
from baserow_enterprise.data_sync.models import AutoDataSyncInterval
from baserow_enterprise.features import DATA_SYNC


class EnterpriseDataSyncHandler:
    @classmethod
    def update_auto_data_sync_interval(
        cls, user: AbstractUser, data_sync: DataSync, interval: str, when: time
    ) -> AutoDataSyncInterval:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, data_sync.table.database.workspace
        )

        CoreHandler().check_permissions(
            user,
            UpdateDatabaseTableOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )

        auto_data_sync, _ = AutoDataSyncInterval.objects.update_or_create(
            data_sync=data_sync,
            defaults={
                "interval": interval,
                "when": when,
            },
        )

        return auto_data_sync

    @classmethod
    def trigger_auto_data_sync_syncs(cls):
        AutoDataSyncInterval.objects.
