from typing import Any, Iterable

from django.contrib.auth.models import AbstractUser
from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.operations import (
    CreateDashboardDataSourceOperationType,
    DeleteDashboardDataSourceOperationType,
    DispatchDashboardDataSourceOperationType,
    ListDashboardDataSourcesOperationType,
    ReadDashboardDataSourceOperationType,
    UpdateDashboardDataSourceOperationType,
)
from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.core.handler import CoreHandler
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.services.registries import (
    DispatchTypes,
    ServiceType,
    service_type_registry,
)

from .exceptions import DashboardDataSourceDoesNotExist, ServiceConfigurationNotAllowed
from .signals import (
    dashboard_data_source_created,
    dashboard_data_source_deleted,
    dashboard_data_source_updated,
)
from .types import UpdatedDashboardDataSource


class DashboardDataSourceService:
    def __init__(self):
        self.handler = DashboardDataSourceHandler()
        self.dashboard_handler = DashboardHandler()

    def get_data_source(
        self, user: AbstractUser, data_source_id: int
    ) -> DashboardDataSource:
        """
        Returns dashboard data source instance from the database and
        checks the user permissions.

        :param user: The user trying to get the data source.
        :param data_source_id: The ID of the data source.
        :raises DashboardDataSourceDoesNotExist: If the data source can't be found.
        :raises PermissionException: If the user doesn't have access to
             the data source.
        :return: The data source instance.
        """

        data_source = self.handler.get_data_source(data_source_id)

        if data_source.dashboard.trashed:
            raise DashboardDataSourceDoesNotExist()

        CoreHandler().check_permissions(
            user,
            ReadDashboardDataSourceOperationType.type,
            workspace=data_source.dashboard.workspace,
            context=data_source,
        )

        return data_source

    def get_data_sources(
        self, user: AbstractUser, dashboard_id: int
    ) -> Iterable[DashboardDataSource]:
        """
        Gets all the data_sources of a given dashboard visible to the given user.

        :param user: The user trying to get the data sources.
        :param dashboard_id: The dashboard that holds the data sources.
        :raises DashboardDoesNotExist: If the dashboard id doesn't point
             to an existing dashboard.
        :raises PermissionException: If the user doesn't have access to
             list the data sources.
        :return: The data sources of that dashboard.
        """

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)

        CoreHandler().check_permissions(
            user,
            ListDashboardDataSourcesOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        data_sources_queryset = CoreHandler().filter_queryset(
            user,
            ListDashboardDataSourcesOperationType.type,
            DashboardDataSource.objects.filter(dashboard=dashboard),
            workspace=dashboard.workspace,
        )

        return self.handler.get_data_sources(
            dashboard, base_queryset=data_sources_queryset
        )

    def create_data_source(
        self,
        user: AbstractUser,
        dashboard_id: int,
        service_type: ServiceType,
        name: str | None = None,
        **kwargs,
    ) -> DashboardDataSource:
        """
        Creates a new data source for a dashboard given the user permissions.

        :param user: The user trying to create the data source.
        :param dashboard_id: The dashboard's id the data source should exists in.
        :param service_type: The type of the related service.
        :param kwargs: Additional attributes of the data source and the service.
        :raises DashboardDoesNotExist: If the dashboard id doesn't point
            to an existing dashboard.
        :raises InvalidServiceTypeDispatchSource: If the dispatch type
            is invalid.
        :raises PermissionException: If the user doesn't have access to
            list the data sources.
        :return: The created data_source.
        """

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)

        CoreHandler().check_permissions(
            user,
            CreateDashboardDataSourceOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        if not service_type.can_be_dispatched_as(DispatchTypes.DATA):
            raise InvalidServiceTypeDispatchSource()

        prepared_values = service_type.prepare_values(kwargs, user)

        if name is None:
            with translation.override(user.profile.language):
                name = self.handler.find_unused_data_source_name(
                    dashboard, _("Data source")
                )

        new_data_source = self.handler.create_data_source(
            dashboard,
            service_type=service_type,
            name=name,
            **prepared_values,
        )

        dashboard_data_source_created.send(self, user=user, data_source=new_data_source)

        return new_data_source

    def update_data_source(
        self,
        user: AbstractUser,
        data_source_id: int,
        service_type: ServiceType,
        **kwargs,
    ) -> UpdatedDashboardDataSource:
        """
        Updates a data source if the user has sufficient permissions.
        Will also check if the values are allowed to be set on the
        data source first.

        :param user: The user trying to update the data_source.
        :param data_source_id: The Id of the data source that should be updated.
        :param service_type: The type of the related service.
        :param kwargs: Additional attributes of the data source and the service.
        :raises DashboardDataSourceDoesNotExist: If the data source
            doesn't exist.
        :raises ServiceConfigurationNotAllowed: If the kwargs contain
            forbidden configuration for the data source service.
        :raises PermissionException: If the user doesn't have the
            correct permissions.
        :return: The updated data source.
        """

        data_source = self.handler.get_data_source_for_update(data_source_id)

        if data_source.dashboard.trashed:
            raise DashboardDataSourceDoesNotExist()

        CoreHandler().check_permissions(
            user,
            UpdateDashboardDataSourceOperationType.type,
            workspace=data_source.dashboard.workspace,
            context=data_source,
        )

        if not service_type.can_be_dispatched_as(DispatchTypes.DATA):
            raise InvalidServiceTypeDispatchSource()

        if "integration_id" in kwargs:
            raise ServiceConfigurationNotAllowed()

        service = data_source.service.specific
        original_service_type = service_type_registry.get_by_model(service)

        if original_service_type != service_type:
            raise ServiceConfigurationNotAllowed()

        prepared_values = service_type.prepare_values(kwargs, user, instance=service)

        updated_data_source = self.handler.update_data_source(
            data_source, service_type=service_type, **prepared_values
        )

        dashboard_data_source_updated.send(
            self, user=user, data_source=updated_data_source.data_source
        )

        return updated_data_source

    def delete_data_source(self, user: AbstractUser, data_source_id: int):
        """
        Deletes the data source based on the provided Id if the user
        has permission to do so.

        :param user: The user trying to delete the data source.
        :param data_source_id: The Id of the to-be-deleted data source.
        :raises DashboardDataSourceDoesNotExist: If the data source
            doesn't exist.
        :raises PermissionException: If the user doesn't have the
            correct permissions.
        """

        data_source = self.handler.get_data_source_for_update(data_source_id)

        if data_source.dashboard.trashed:
            raise DashboardDataSourceDoesNotExist()

        CoreHandler().check_permissions(
            user,
            DeleteDashboardDataSourceOperationType.type,
            workspace=data_source.dashboard.workspace,
            context=data_source,
        )

        self.handler.delete_data_source(data_source)

        dashboard_data_source_deleted.send(
            self, user=user, data_source_id=data_source_id
        )

    def dispatch_data_source(
        self,
        user,
        data_source_id: int,
        dispatch_context: DashboardDispatchContext,
    ) -> Any:
        """
        Dispatch the service related to the data source if the user has the permission.

        :param user: The current user.
        :param data_source_id: The data source to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :raises DashboardDataSourceDoesNotExist: If the data source can't be found.
        :raises PermissionException: If the user doesn't have the
            correct permissions.
        :raises DashboardDataSourceImproperlyConfigured: If the data source is
            not properly configured.
        :raises ServiceImproperlyConfiguredDispatchException: If the underlying service
            is not properly configured.
        :raises DoesNotExist: If the requested data from the service
            don't exist.
        :return: return the dispatch result.
        """

        data_source = self.handler.get_data_source(data_source_id)

        if data_source.dashboard.trashed:
            raise DashboardDataSourceDoesNotExist()

        CoreHandler().check_permissions(
            user,
            DispatchDashboardDataSourceOperationType.type,
            context=data_source,
            workspace=data_source.dashboard.workspace,
        )

        result = self.handler.dispatch_data_source(data_source, dispatch_context)
        return result
