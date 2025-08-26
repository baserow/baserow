from baserow_premium.dashboard.widgets.models import ChartWidget, PieChartWidget
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)


class DashboardFixture:
    def create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        self, **kwargs
    ):
        return self.create_dashboard_data_source(
            service_model_class=LocalBaserowGroupedAggregateRows, **kwargs
        )

    def create_chart_widget(self, dashboard=None, **kwargs):
        dashboard_args = kwargs.pop("dashboard_args", {})
        if dashboard is None:
            dashboard = self.create_dashboard_application(**dashboard_args)
        if "data_source" not in kwargs:
            data_source = (
                self.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
                    dashboard=dashboard
                )
            )
            kwargs["data_source"] = data_source
        widget = ChartWidget.objects.create(dashboard=dashboard, **kwargs)
        return widget

    def create_pie_chart_widget(self, dashboard=None, **kwargs):
        dashboard_args = kwargs.pop("dashboard_args", {})
        if dashboard is None:
            dashboard = self.create_dashboard_application(**dashboard_args)
        if "data_source" not in kwargs:
            data_source = (
                self.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
                    dashboard=dashboard
                )
            )
            kwargs["data_source"] = data_source
        widget = PieChartWidget.objects.create(dashboard=dashboard, **kwargs)
        return widget
