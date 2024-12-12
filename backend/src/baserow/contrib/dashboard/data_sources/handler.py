from typing import Any, Iterable, cast

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
from baserow.core.utils import find_unused_name

from .types import DashboardDataSourceForUpdate


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
            DashboardDataSource.objects.filter(dashboard=dashboard).values_list(
                "name", flat=True
            )
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
    ) -> DashboardDataSource:
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
            data_source.service = self.service_handler.update_service(
                service_type, service_to_update, **kwargs
            )

        # Update data source attributes
        if name is not None:
            data_source.name = name

        data_source.full_clean()
        data_source.save()

        if original_service.id != data_source.service.id:
            self.service_handler.delete_service(service_type, original_service)

        return data_source

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
        :raises ServiceImproperlyConfigured: If the underlying service is
            not properly configured.
        :raises DoesNotExist: If the requested data from the service
            don't exist.
        :return: The result of dispatching the data source.
        """

        if not data_source.service_id:
            raise DashboardDataSourceImproperlyConfigured(
                "The service type is missing."
            )

        service_dispatch = self.service_handler.dispatch_service(
            data_source.service.specific, dispatch_context
        )

        return service_dispatch
