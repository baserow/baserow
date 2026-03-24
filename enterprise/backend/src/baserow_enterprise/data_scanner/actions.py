import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType
from baserow_enterprise.data_scanner.handler import DataScannerHandler


class CreateDataScanActionType(ActionType):
    type = "create_data_scan"
    description = ActionTypeDescription(
        _("Create data scan"),
        _('Data scan "%(scan_name)s" (%(scan_id)s) created'),
    )
    analytics_params = ["scan_id"]

    @dataclasses.dataclass
    class Params:
        scan_id: int
        scan_name: str

    @classmethod
    def do(cls, user: AbstractUser, **kwargs):
        scan = DataScannerHandler.create_scan(user=user, **kwargs)

        params = cls.Params(scan.id, scan.name)
        cls.register_action(user, params, cls.scope())

        return scan

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class UpdateDataScanActionType(ActionType):
    type = "update_data_scan"
    description = ActionTypeDescription(
        _("Update data scan"),
        _('Data scan "%(scan_name)s" (%(scan_id)s) updated'),
    )
    analytics_params = ["scan_id"]

    @dataclasses.dataclass
    class Params:
        scan_id: int
        scan_name: str

    @classmethod
    def do(cls, user: AbstractUser, scan_id: int, **kwargs):
        scan = DataScannerHandler.update_scan(user=user, scan_id=scan_id, **kwargs)

        params = cls.Params(scan.id, scan.name)
        cls.register_action(user, params, cls.scope())

        return scan

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class DeleteDataScanActionType(ActionType):
    type = "delete_data_scan"
    description = ActionTypeDescription(
        _("Delete data scan"),
        _('Data scan "%(scan_name)s" (%(scan_id)s) deleted'),
    )
    analytics_params = ["scan_id"]

    @dataclasses.dataclass
    class Params:
        scan_id: int
        scan_name: str

    @classmethod
    def do(cls, user: AbstractUser, scan_id: int):
        scan = DataScannerHandler.get_scan(user=user, scan_id=scan_id)

        scan_name = scan.name
        DataScannerHandler.delete_scan(user=user, scan_id=scan_id)

        params = cls.Params(scan_id, scan_name)
        cls.register_action(user, params, cls.scope())

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
