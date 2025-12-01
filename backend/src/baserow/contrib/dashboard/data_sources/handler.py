from decimal import Decimal
from typing import Any, Iterable, cast

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.models import Dashboard
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.utils import find_unused_name

from .types import (
    DashboardDataSourceDict,
    DashboardDataSourceForUpdate,
    UpdatedDashboardDataSource,
)


class DashboardDataSourceHandler:
    def __init__(self):
        self.service_handler = ServiceHandler()

    def get_data_source(
        self, data_source_id: int, base_queryset: QuerySet | None = None
    ) -> DashboardDataSource:
        """
        Returns a dashboard data source instance from the database.

        :param data_source_id: The ID of the data source.
        :param base_queryset: The base queryset to use to build the query.
        :raises DashboardDataSourceDoesNotExist: If the data source can't be found.
        :return: The data source instance.
        """

        queryset = (
            base_queryset
            if base_queryset is not None
            else DashboardDataSource.objects.all()
        )

        try:
            data_source = queryset.select_related(
                "dashboard__workspace", "service"
            ).get(id=data_source_id)
        except DashboardDataSource.DoesNotExist:
            raise DashboardDataSourceDoesNotExist()

        return data_source

    def get_data_source_for_update(
        self, data_source_id: int, base_queryset=None
    ) -> DashboardDataSourceForUpdate:
        """
        Returns a data source instance from the database that can be safely updated.

        :param data_source_id: The ID of the data source.
        :param base_queryset: The base queryset to use to build the query.
        :raises DashboardDataSourceDoesNotExist: If the data source can't be found.
        :return: The data source instance.
        """

        queryset = (
            base_queryset
            if base_queryset is not None
            else DashboardDataSource.objects.all()
        )

        queryset = queryset.select_for_update(of=("self",))

        return cast(
            DashboardDataSourceForUpdate,
            self.get_data_source(
                data_source_id,
                base_queryset=queryset,
            ),
        )

    def get_data_sources(
        self,
        dashboard: Dashboard,
        base_queryset: QuerySet | None = None,
        return_specific_services: bool = True,
    ) -> Iterable[DashboardDataSource]:
        """
        Gets all the specific data sources of a given dashboard.

        :param dashboard: The dashboard that holds the data sources.
        :param base_queryset: The base queryset to use to build the query.
        :param return_specific_services: If True, return the specific version
            of the service related to the integration.
        :return: The data sources of that dashboard.
        """

        data_source_queryset = (
            base_queryset
            if base_queryset is not None
            else DashboardDataSource.objects.all()
        )

        data_source_queryset = data_source_queryset.filter(
            dashboard=dashboard
        ).select_related(
            "dashboard",
            "dashboard__workspace",
            "service",
            "service__integration",
            "service__integration__application",
        )

        if return_specific_services:
            data_source_queryset = data_source_queryset.select_related(
                "service__content_type"
            )
            data_sources = list(data_source_queryset.all())

            # Get all service ids to get them from DB in one query
            service_ids = [
                data_source.service_id
                for data_source in data_sources
                if data_source.service_id is not None
            ]

            specific_services_map = {
                s.id: s
                for s in self.service_handler.get_services(
                    base_queryset=Service.objects.filter(id__in=service_ids)
                )
            }

            # Distribute specific services to their data_source
            for data_source in data_sources:
                if data_source.service_id:
                    data_source.service = specific_services_map[data_source.service_id]

            return data_sources
        else:
            return data_source_queryset.all()

    def find_unused_data_source_name(
        self, dashboard: Dashboard, proposed_name: str
    ) -> str:
        """
        Finds an unused name for a data source in a dashboard.

        :param dashboard: The dashboard that the data source belongs to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        existing_pages_names = list(
            DashboardDataSource.objects_and_trash.filter(
                dashboard=dashboard
            ).values_list("name", flat=True)
        )
        return find_unused_name([proposed_name], existing_pages_names, max_length=255)

    def create_data_source(
        self,
        dashboard: Dashboard,
        name: str,
        service_type: ServiceType,
        **kwargs,
    ) -> DashboardDataSource:
        """
        Creates a new data source for a dashboard.

        :param dashboard: The dashboard the data source should exist in.
        :param name: The human name of the data source.
        :param service_type: The type of the service related to the data source.
        :param kwargs: Additional attributes of the related service.
        :return: The created data source.
        """

        order = DashboardDataSource.get_last_order(dashboard)

        # Currently all Dashboard data sources will be of
        # local baserow integration type
        integration = Integration.objects.filter(application=dashboard).first()
        service = self.service_handler.create_service(
            service_type=service_type, integration=integration, **kwargs
        )
        data_source = DashboardDataSource.objects.create(
            dashboard=dashboard, order=order, name=name, service=service
        )
        return data_source

    def update_data_source(
        self,
        data_source: DashboardDataSourceForUpdate,
        service_type: ServiceType,
        name: str | None = None,
        **kwargs,
    ) -> UpdatedDashboardDataSource:
        """
        Updates the data source and the related service with values.

        :param data_source: The data source that should be updated.
        :param service_type: The new service type. If the service type
            shouldn't change, pass in the current service type.
        :param name: A new name for the data source.
        :param kwargs: The values that should be set on the service.
        :return: The updated data source.
        """

        original_service_type = service_type_registry.get_by_model(
            data_source.service.specific
        )
        original_service = data_source.service
        updated_service = None
        if service_type != original_service_type:
            # If the service type is not the same let's create
            # a new service instead of updating the existing one

            # Check if the new service type can reuse the previous integration
            integration = data_source.service.integration
            integration_type = integration_type_registry.get_by_model(
                integration.specific
            ).type
            if service_type.integration_type != integration_type:
                integration = None

            service = self.service_handler.create_service(
                service_type=service_type,
                integration=integration,
                **kwargs,
            )
            data_source.service = service
        else:
            # Update service itself based on the passed kwargs
            # that are intended for the service
            service_to_update = self.service_handler.get_service_for_update(
                data_source.service.id
            )
            updated_service = self.service_handler.update_service(
                service_type, service_to_update, **kwargs
            )
            data_source.service = updated_service.service

        # Update data source attributes
        if name is not None:
            data_source.name = name

        data_source.full_clean()
        data_source.save()

        if original_service.id != data_source.service.id:
            self.service_handler.delete_service(service_type, original_service)

        return UpdatedDashboardDataSource(
            data_source,
            updated_service.original_service_values if updated_service else {},
            updated_service.new_service_values if updated_service else {},
        )

    def delete_data_source(self, data_source: DashboardDataSource):
        """
        Deletes the provided data source.

        :param data_source: The to-be-deleted data source.
        """

        if data_source.service:
            service_type = service_type_registry.get_by_model(
                data_source.service.specific_class
            )
            ServiceHandler().delete_service(service_type, data_source.service)

        data_source.delete()

    def dispatch_data_source(
        self,
        data_source: DashboardDataSource,
        dispatch_context: DashboardDispatchContext,
    ) -> Any:
        """
        Dispatch the service related to the data source.

        :param data_source: The data source to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :raises DashboardDataSourceImproperlyConfigured: If the data source is
            not properly configured.
        :raises ServiceImproperlyConfiguredDispatchException: If the underlying service
            is not properly configured.
        :raises DoesNotExist: If the requested data from the service
            don't exist.
        :return: The result of dispatching the data source.
        """

        if not data_source.service_id:
            raise DashboardDataSourceImproperlyConfigured(
                "The service type is missing."
            )

        specific_service = ServiceHandler().get_service(data_source.service.id)
        service_dispatch = self.service_handler.dispatch_service(
            specific_service, dispatch_context
        )

        return service_dispatch.data

    def export_data_source(
        self,
        data_source: DashboardDataSource,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict[str, any] | None = None,
    ) -> DashboardDataSourceDict:
        """
        Serializes the given data source.

        :param data_source: The instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Optional storage to use.
        :param cache: Optional cache to use.
        :return: The serialized version.
        """

        serialized_service = None

        if data_source.service:
            serialized_service = ServiceHandler().export_service(
                data_source.service, files_zip=files_zip, storage=storage, cache=cache
            )

        return DashboardDataSourceDict(
            id=data_source.id,
            name=data_source.name,
            order=str(data_source.order),
            service=serialized_service,
        )

    def import_data_source(
        self,
        dashboard: Dashboard,
        serialized_data_source: DashboardDataSourceDict,
        id_mapping: dict[str, dict[int, int]],
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict[str, any] | None = None,
    ) -> DashboardDataSource:
        """
        Creates an instance using the serialized version previously exported with
        `.export_data_source'.

        :param dashboard: The dashboard instance the new data source should belong to.
        :param serialized_data_source: The serialized version of the data source.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the new data source instance.
        """

        if "dashboard_data_sources" not in id_mapping:
            id_mapping["dashboard_data_sources"] = {}

        service = None
        serialized_service = serialized_data_source.get("service", None)
        if serialized_service:
            integration = None
            integration_id = serialized_service.pop("integration_id", None)
            if integration_id:
                integration_id = id_mapping["integrations"].get(
                    integration_id, integration_id
                )
                integration = Integration.objects.get(id=integration_id)

            service = ServiceHandler().import_service(
                integration,
                serialized_service,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
                import_formula=lambda formula, id_mapping, **kwargs: formula,
            )

        data_source = DashboardDataSource.objects.create(
            dashboard=dashboard,
            service=service,
            order=Decimal(serialized_data_source["order"]),
            name=serialized_data_source["name"],
        )

        id_mapping["dashboard_data_sources"][
            serialized_data_source["id"]
        ] = data_source.id

        return data_source
