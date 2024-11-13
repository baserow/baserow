from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowDeleteRow,
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
    LocalBaserowUpsertRow,
)


class ServiceFixtures:
    def create_local_baserow_get_row_service(self, **kwargs) -> LocalBaserowGetRow:
        service = self.create_service(LocalBaserowGetRow, **kwargs)
        return service

    def create_local_baserow_list_rows_service(self, **kwargs) -> LocalBaserowListRows:
        service = self.create_service(LocalBaserowListRows, **kwargs)
        return service

    def create_local_baserow_upsert_row_service(
        self, **kwargs
    ) -> LocalBaserowUpsertRow:
        service = self.create_service(LocalBaserowUpsertRow, **kwargs)
        return service

    def create_local_baserow_delete_row_service(
        self, **kwargs
    ) -> LocalBaserowDeleteRow:
        service = self.create_service(LocalBaserowDeleteRow, **kwargs)
        return service

    def create_local_baserow_aggregate_rows_service(
        self, **kwargs
    ) -> LocalBaserowAggregateRows:
        service = self.create_service(LocalBaserowAggregateRows, **kwargs)
        return service

    def create_local_baserow_table_service_filter(
        self, **kwargs
    ) -> LocalBaserowTableServiceFilter:
        if "type" not in kwargs:
            kwargs["type"] = "equal"
        if "order" not in kwargs:
            kwargs["order"] = 0
        return LocalBaserowTableServiceFilter.objects.create(**kwargs)

    def create_local_baserow_table_service_sort(
        self, **kwargs
    ) -> LocalBaserowTableServiceSort:
        return LocalBaserowTableServiceSort.objects.create(**kwargs)

    def create_service(self, model_class, **kwargs):
        if "integration" not in kwargs:
            integrations_args = kwargs.pop("integration_args", {})
            integration = self.create_local_baserow_integration(**integrations_args)
        else:
            integration = kwargs.pop("integration", None)
            kwargs.pop("integration_args", None)

        service = model_class.objects.create(integration=integration, **kwargs)

        return service
