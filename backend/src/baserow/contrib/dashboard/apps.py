from django.apps import AppConfig

from baserow.core.feature_flags import FF_DASHBOARDS, feature_flag_is_enabled


class DashboardConfig(AppConfig):
    name = "baserow.contrib.dashboard"

    def ready(self):
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )

        from .application_types import DashboardApplicationType

        if feature_flag_is_enabled(FF_DASHBOARDS):
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
                UpdateWidgetOperationType,
            )

            operation_type_registry.register(ListWidgetsOperationType())
            operation_type_registry.register(ReadWidgetOperationType())
            operation_type_registry.register(CreateWidgetOperationType())
            operation_type_registry.register(UpdateWidgetOperationType())
            operation_type_registry.register(DeleteWidgetOperationType())

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

            from baserow.contrib.dashboard.widgets.registries import (
                widget_type_registry,
            )
            from baserow.contrib.dashboard.widgets.widget_types import SummaryWidgetType

            widget_type_registry.register(SummaryWidgetType())
