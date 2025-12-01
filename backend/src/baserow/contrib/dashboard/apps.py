from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = "baserow.contrib.dashboard"

    def ready(self):
        from baserow.core.action.registries import action_type_registry
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry
        from baserow.ws.registries import page_registry

        from .application_types import DashboardApplicationType

        application_type_registry.register(DashboardApplicationType())

        from baserow.contrib.dashboard.object_scopes import DashboardObjectScopeType

        object_scope_type_registry.register(DashboardObjectScopeType())

        from baserow.contrib.dashboard.data_sources.object_scopes import (
            DashboardDataSourceObjectScopeType,
        )

        object_scope_type_registry.register(DashboardDataSourceObjectScopeType())

        from baserow.contrib.dashboard.widgets.object_scopes import (
            WidgetObjectScopeType,
        )

        object_scope_type_registry.register(WidgetObjectScopeType())

        from baserow.contrib.dashboard.widgets.operations import (
            CreateWidgetOperationType,
            DeleteWidgetOperationType,
            ListWidgetsOperationType,
            ReadWidgetOperationType,
            RestoreWidgetOperationType,
            UpdateWidgetOperationType,
        )

        operation_type_registry.register(ListWidgetsOperationType())
        operation_type_registry.register(ReadWidgetOperationType())
        operation_type_registry.register(CreateWidgetOperationType())
        operation_type_registry.register(UpdateWidgetOperationType())
        operation_type_registry.register(DeleteWidgetOperationType())
        operation_type_registry.register(RestoreWidgetOperationType())

        from baserow.contrib.dashboard.data_sources.operations import (
            CreateDashboardDataSourceOperationType,
            DeleteDashboardDataSourceOperationType,
            DispatchDashboardDataSourceOperationType,
            ListDashboardDataSourcesOperationType,
            ReadDashboardDataSourceOperationType,
            UpdateDashboardDataSourceOperationType,
        )

        operation_type_registry.register(ListDashboardDataSourcesOperationType())
        operation_type_registry.register(CreateDashboardDataSourceOperationType())
        operation_type_registry.register(DeleteDashboardDataSourceOperationType())
        operation_type_registry.register(UpdateDashboardDataSourceOperationType())
        operation_type_registry.register(ReadDashboardDataSourceOperationType())
        operation_type_registry.register(DispatchDashboardDataSourceOperationType())

        from baserow.contrib.dashboard.widgets.registries import widget_type_registry
        from baserow.contrib.dashboard.widgets.widget_types import SummaryWidgetType

        widget_type_registry.register(SummaryWidgetType())

        from baserow.contrib.dashboard.widgets.trash_types import (
            WidgetTrashableItemType,
        )

        trash_item_type_registry.register(WidgetTrashableItemType())

        from .ws.pages import DashboardPageType

        page_registry.register(DashboardPageType())

        from baserow.core.registries import permission_manager_type_registry

        from .permission_manager import AllowIfTemplatePermissionManagerType

        prev_manager = permission_manager_type_registry.get(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.unregister(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType(prev_manager)
        )

        from baserow.contrib.dashboard.data_sources.actions import (
            UpdateDashboardDataSourceActionType,
        )
        from baserow.contrib.dashboard.widgets.actions import (
            CreateWidgetActionType,
            DeleteWidgetActionType,
            UpdateWidgetActionType,
        )

        from .ws.receivers import (  # noqa: F401
            dashboard_data_source_updated,
            widget_created,
            widget_deleted,
            widget_updated,
        )

        action_type_registry.register(CreateWidgetActionType())
        action_type_registry.register(UpdateWidgetActionType())
        action_type_registry.register(DeleteWidgetActionType())
        action_type_registry.register(UpdateDashboardDataSourceActionType())

        from baserow.core.search.registries import workspace_search_registry

        from .search_types import DashboardSearchType

        workspace_search_registry.register(DashboardSearchType())
