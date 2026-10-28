from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowListRows,
)


class DataSourceFixtures:
    def create_builder_local_baserow_get_row_data_source(self, **kwargs):
        return self.create_builder_data_source(
            service_model_class=LocalBaserowGetRow, **kwargs
        )

    def create_builder_local_baserow_list_rows_data_source(self, **kwargs):
        return self.create_builder_data_source(
            service_model_class=LocalBaserowListRows, **kwargs
        )

    def create_builder_data_source(
        self,
        page=None,
        user=None,
        service_model_class=None,
        order=None,
        name=None,
        **kwargs,
    ):
        if not page:
            if user is None:
                user = self.create_user()

            builder = kwargs.pop("builder", None)
            if builder is None and kwargs.get("table") is not None:
                # The table is read through the builder's integration, so they
                # share a workspace.
                builder = self.create_builder_application(
                    user=user, workspace=kwargs["table"].database.workspace
                )
            page_args = kwargs.pop("page_args", {})
            page = self.create_builder_page(user=user, builder=builder, **page_args)

        service = kwargs.pop("service", None)
        if service is None and service_model_class:
            integrations_args = kwargs.pop("integration_args", {})
            integrations_args["application"] = page.builder
            service = self.create_service(
                service_model_class, integration_args=integrations_args, **kwargs
            )

        if order is None:
            order = DataSource.get_last_order(page)

        if name is None:
            name = self.fake.unique.word()

        data_source = DataSource.objects.create(
            page=page, name=name, service=service, order=order
        )

        return data_source
