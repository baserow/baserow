from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.dashboard.actions import DASHBOARD_ACTION_CONTEXT
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.services.registries import service_type_registry

from .models import DashboardDataSource
from .service import DashboardDataSourceService


class UpdateDashboardDataSourceActionType(UndoableActionType):
    type = "update_dashboard_data_source"
    description = ActionTypeDescription(
        _("Update dashboard data source"),
        _('Data source "%(data_source_name)s" (%(data_source_id)s) updated'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "data_source_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        data_source_id: int
        data_source_name: str
        service_type: str
        data_source_original_params: dict[str, any]
        data_source_new_params: dict[str, any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_source_id: int,
        service_type,
        new_data: dict,
    ) -> DashboardDataSource:
        updated_data_source = DashboardDataSourceService().update_data_source(
            user, data_source_id, service_type=service_type, **new_data
        )

        # For now remove information about integrations as they cannot
        # change and would be rejected later on undo/redo calls
        updated_data_source.original_values.pop("integration_id", None)
        updated_data_source.new_values.pop("integration_id", None)

        cls.register_action(
            user=user,
            params=cls.Params(
                updated_data_source.data_source.dashboard.id,
                updated_data_source.data_source.dashboard.name,
                updated_data_source.data_source.id,
                updated_data_source.data_source.name,
                service_type.type,
                updated_data_source.original_values,
                updated_data_source.new_values,
            ),
            scope=cls.scope(updated_data_source.data_source.dashboard.id),
            workspace=updated_data_source.data_source.dashboard.workspace,
        )
        return updated_data_source.data_source

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        service_type = service_type_registry.get(params.service_type)
        DashboardDataSourceService().update_data_source(
            user,
            params.data_source_id,
            service_type=service_type,
            **params.data_source_original_params,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        service_type = service_type_registry.get(params.service_type)
        DashboardDataSourceService().update_data_source(
            user,
            params.data_source_id,
            service_type=service_type,
            **params.data_source_new_params,
        )
