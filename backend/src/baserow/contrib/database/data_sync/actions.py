import dataclasses
from typing import List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    DATABASE_ACTION_CONTEXT,
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder


class CreateDataSyncTableActionType(UndoableActionType):
    type = "create_data_sync_table"
    description = ActionTypeDescription(
        _("Create data sync table"),
        _('Data sync table "%(table_name)s" (%(table_id)s) created'),
        DATABASE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "data_sync_id",
        "data_sync_type",
    ]

    @dataclasses.dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        data_sync_id: int
        data_sync_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        database: Database,
        type_name: str,
        synced_properties: List[str],
        table_name: str,
        **kwargs: dict,
    ) -> DataSync:
        data_sync = DataSyncHandler().create_data_sync_table(
            user=user,
            database=database,
            type_name=type_name,
            synced_properties=synced_properties,
            table_name=table_name,
            **kwargs,
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
            type_name,
        )
        cls.register_action(user, params, cls.scope(database.id), workspace=workspace)

        return data_sync

    @classmethod
    def scope(cls, database_id) -> ActionScopeStr:
        return ApplicationActionScopeType.value(database_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        table = Table.objects.get(id=params.table_id)
        TableHandler().delete_table(user, table)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user, "table", params.table_id, parent_trash_item_id=None
        )


class UpdateDataSyncTableActionType(ActionType):
    type = "update_data_sync_table"
    description = ActionTypeDescription(
        _("Update data sync table"),
        _('Data sync table "%(table_name)s" (%(table_id)s) updated'),
        DATABASE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "data_sync_id",
    ]

    @dataclasses.dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        data_sync_id: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_sync: DataSync,
        synced_properties: Optional[List[str]] = None,
        **kwargs: dict,
    ) -> DataSync:
        data_sync = data_sync.specific

        if not synced_properties:
            synced_properties = list(
                data_sync.synced_properties.all().values_list("key", flat=True)
            )

        data_sync = DataSyncHandler().update_data_sync_table(
            user=user,
            data_sync=data_sync,
            synced_properties=synced_properties,
            **kwargs,
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
        )
        cls.register_action(user, params, cls.scope(database.id), workspace=workspace)

        return data_sync

    @classmethod
    def scope(cls, database_id) -> ActionScopeStr:
        return ApplicationActionScopeType.value(database_id)


class SyncDataSyncTableActionType(ActionType):
    type = "sync_data_sync_table"
    description = ActionTypeDescription(
        _("Sync data sync table"),
        _("The data sync synchronized"),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = ["data_sync_id", "table_id"]

    @dataclasses.dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        data_sync_id: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_sync: DataSync,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        data_sync = data_sync.specific
        data_sync = DataSyncHandler().sync_data_sync_table(
            user, data_sync, progress_builder
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
        )
        cls.register_action(user, params, cls.scope(table.id), workspace=workspace)

        return data_sync

    @classmethod
    def scope(cls, table_id: int) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)
