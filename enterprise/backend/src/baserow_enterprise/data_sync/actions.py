import dataclasses
from datetime import time

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import DATABASE_ACTION_CONTEXT
from baserow.contrib.database.data_sync.models import DataSync
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler


class UpdatePeriodicDataSyncIntervalActionType(ActionType):
    type = "update_periodic_data_sync_interval"
    description = ActionTypeDescription(
        _("Update periodic data sync interval"),
        _('Data sync table "%(table_name)s" (%(table_id)s) updated'),
        DATABASE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "data_sync_id",
        "interval",
        "when",
    ]

    @dataclasses.dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        data_sync_id: int
        interval: str
        when: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_sync: DataSync,
        interval: str,
        when: time,
    ) -> DataSync:
        data_sync = data_sync.specific

        periodic_interval = (
            EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
                user=user,
                data_sync=data_sync,
                interval=interval,
                when=when,
            )
        )

        table = data_sync.table
        database = table.database
        workspace = database.workspace
        params = cls.Params(
            database.id,
            database.name,
            table.id,
            table.name,
            data_sync.id,
            interval,
            when.strftime("%H:%M:%S"),
        )
        cls.register_action(user, params, cls.scope(database.id), workspace=workspace)

        return periodic_interval

    @classmethod
    def scope(cls, database_id) -> ActionScopeStr:
        return ApplicationActionScopeType.value(database_id)
