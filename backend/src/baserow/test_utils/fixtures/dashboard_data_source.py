from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowListRows,
)


class DashboardDataSourceFixtures:
    def create_dashboard_local_baserow_list_rows_data_source(self, **kwargs):
        return self.create_dashboard_data_source(
            service_model_class=LocalBaserowListRows, **kwargs
        )

    def create_dashboard_local_baserow_aggregate_rows_data_source(self, **kwargs):
        return self.create_dashboard_data_source(
            service_model_class=LocalBaserowAggregateRows, **kwargs
        )

    def create_dashboard_data_source(
        self,
        dashboard=None,
        user=None,
        service_model_class=None,
        order=None,
        name=None,
        **kwargs,
    ):
        if not dashboard:
            if user is None:
                user = self.create_user()
            dashboard = self.create_dashboard_application(user=user)

        service = kwargs.pop("service", None)

        if service is None:
            if not service_model_class:
                service_model_class = LocalBaserowAggregateRows

            integrations_args = kwargs.pop("integration_args", {})
            integrations_args["application"] = dashboard
            service = self.create_service(
                service_model_class, integration_args=integrations_args, **kwargs
            )

        if order is None:
            order = DashboardDataSource.get_last_order(dashboard)

        if name is None:
            name = self.fake.unique.word()

        data_source = DashboardDataSource.objects.create(
            dashboard=dashboard,
            name=name,
            service=service,
            order=order,
            trashed=kwargs.get("trashed", False),
        )

        return data_source
