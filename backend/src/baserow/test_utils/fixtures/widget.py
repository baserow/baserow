from baserow.contrib.dashboard.widgets.models import SummaryWidget


class WidgetFixtures:
    def create_summary_widget(self, dashboard=None, **kwargs):
        dashboard_args = kwargs.pop("dashboard_args", {})
        if dashboard is None:
            dashboard = self.create_dashboard_application(**dashboard_args)
        if "data_source" not in kwargs:
            data_source = (
                self.create_dashboard_local_baserow_aggregate_rows_data_source(
                    dashboard=dashboard
                )
            )
            kwargs["data_source"] = data_source
        widget = SummaryWidget.objects.create(dashboard=dashboard, **kwargs)
        return widget
