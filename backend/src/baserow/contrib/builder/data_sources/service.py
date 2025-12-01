from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import DataSourceNotInSamePage
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    CreateDataSourceOperationType,
    DeleteDataSourceOperationType,
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
    ReadDataSourceOperationType,
    UpdateDataSourceOperationType,
)
from baserow.contrib.builder.data_sources.signals import (
    data_source_created,
    data_source_deleted,
    data_source_moved,
    data_source_orders_recalculated,
    data_source_updated,
)
from baserow.contrib.builder.data_sources.types import DataSourceForUpdate
from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.handler import CoreHandler
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.types import PermissionCheck

if TYPE_CHECKING:
    from baserow.contrib.builder.models import Builder


class DataSourceService:
    def __init__(self):
        self.handler = DataSourceHandler()

    def get_data_source(self, user: AbstractUser, data_source_id: int) -> DataSource:
        """
        Returns an data_source instance from the database. Also checks the user
        permissions.

        :param user: The user trying to get the data_source
        :param data_source_id: The ID of the data_source
        :return: The data_source instance
        """

        data_source = self.handler.get_data_source(data_source_id)

        CoreHandler().check_permissions(
            user,
            ReadDataSourceOperationType.type,
            workspace=data_source.page.builder.workspace,
            context=data_source,
        )

        return data_source

    def get_data_sources(self, user: AbstractUser, page: Page) -> List[DataSource]:
        """
        Gets all the data_sources of a given page visible to the given user.

        :param user: The user trying to get the data_sources.
        :param page: The page that holds the data_sources.
        :return: The data_sources of that page.
        """

        CoreHandler().check_permissions(
            user,
            ListDataSourcesPageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        user_data_sources = CoreHandler().filter_queryset(
            user,
            ListDataSourcesPageOperationType.type,
            DataSource.objects.all(),
            workspace=page.builder.workspace,
        )

        return self.handler.get_data_sources(page, base_queryset=user_data_sources)

    def get_builder_data_sources(
        self, user: AbstractUser, builder: "Builder", with_cache=False
    ) -> List[DataSource]:
        """
        Gets all the data_sources of a given builder visible to the given user.

        :param user: The user trying to get the data_sources.
        :param page: The builder that holds the data_sources.
        :param with_cache: Whether this method should populate the short
          cache for data_sources.
        :return: The data_sources of that builder.
        """

        user_data_sources = CoreHandler().filter_queryset(
            user,
            ListDataSourcesPageOperationType.type,
            DataSource.objects.all(),
            workspace=builder.workspace,
        )

        return self.handler.get_builder_data_sources(
            builder,
            base_queryset=user_data_sources,
            with_cache=with_cache,
        )

    def create_data_source(
        self,
        user: AbstractUser,
        page: Page,
        service_type: ServiceType,
        name: Optional[str] = None,
        before: Optional[DataSource] = None,
        **kwargs,
    ) -> DataSource:
        """
        Creates a new data_source for a page given the user permissions.

        :param user: The user trying to create the data_source.
        :param page: The page the data_source exists in.
        :param service_type: The type of the related service.
        :param before: If set, the new data_source is inserted before this data_source.
        :param kwargs: Additional attributes of the data_source and the service.
        :return: The created data_source.
        """

        CoreHandler().check_permissions(
            user,
            CreateDataSourceOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        # Check we are on the same page.
        if before and page.id != before.page_id:
            raise DataSourceNotInSamePage()

        if service_type:
            # Verify the `service_type` is dispatch-able as DATA.
            if not service_type.can_be_dispatched_as(DispatchTypes.DATA):
                raise InvalidServiceTypeDispatchSource()
            prepared_values = service_type.prepare_values(kwargs, user)
        else:
            prepared_values = kwargs

        if name is None:
            with translation.override(user.profile.language):
                name = self.handler.find_unused_data_source_name(page, _("Data source"))

        try:
            new_data_source = self.handler.create_data_source(
                page,
                service_type=service_type,
                before=before,
                name=name,
                **prepared_values,
            )
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, page)
            # If the `find_intermediate_order` fails with a
            # `CannotCalculateIntermediateOrder`, it means that it's not possible
            # calculate an intermediate fraction. Therefore, must reset all the
            # orders of the data_sources (while respecting their original order),
            # so that we can then can find the fraction any many more after.
            before.refresh_from_db()
            new_data_source = self.handler.create_data_source(
                page,
                service_type=service_type,
                before=before,
                name=name,
                **prepared_values,
            )

        data_source_created.send(
            self,
            data_source=new_data_source,
            user=user,
            before_id=before.id if before else None,
        )

        return new_data_source

    def update_data_source(
        self,
        user: AbstractUser,
        data_source: DataSourceForUpdate,
        service_type: Optional[ServiceType] = None,
        **kwargs,
    ) -> DataSource:
        """
        Updates and data_source with values. Will also check if the values are allowed
        to be set on the data_source first.

        :param user: The user trying to update the data_source.
        :param data_source: The data_source that should be updated.
        :param service_type: The type of the related service.
        :param kwargs: Additional attributes of the data_source and the service.
        :return: The updated data_source.
        """

        CoreHandler().check_permissions(
            user,
            UpdateDataSourceOperationType.type,
            workspace=data_source.page.builder.workspace,
            context=data_source,
        )

        page = None
        if "page" in kwargs:
            page = kwargs.pop("page")
            # Check we are in the same builder.
            if page.builder_id != data_source.page.builder_id:
                raise PageNotInBuilder(page.id)

        # The service type we're using for preparing the values. If we're not
        # changing service types, then it's `service_type`, otherwise below we
        # swap to `new_service_type` instead.
        service_type_for_preparation = service_type

        new_service_type: ServiceType = kwargs.get("new_service_type", None)
        if new_service_type:
            # Verify the new `service_type` is dispatch-able as DATA.
            if not new_service_type.can_be_dispatched_as(DispatchTypes.DATA):
                raise InvalidServiceTypeDispatchSource()
            # If we're changing service types, we need to prepare the values with
            # the new one, instead of the old one.
            service_type_for_preparation = new_service_type

        if service_type_for_preparation:
            service = data_source.service.specific if data_source.service_id else None
            prepared_values = service_type_for_preparation.prepare_values(
                kwargs, user, instance=service
            )
        else:
            prepared_values = kwargs

        if page is not None:
            prepared_values["page"] = page

        data_source = self.handler.update_data_source(
            data_source, service_type, **prepared_values
        )

        data_source_updated.send(self, data_source=data_source, user=user)

        return data_source

    def delete_data_source(self, user: AbstractUser, data_source: DataSourceForUpdate):
        """
        Deletes an data_source.

        :param user: The user trying to delete the data_source.
        :param data_source: The to-be-deleted data_source.
        """

        page = data_source.page

        CoreHandler().check_permissions(
            user,
            DeleteDataSourceOperationType.type,
            workspace=data_source.page.builder.workspace,
            context=data_source,
        )

        self.handler.delete_data_source(data_source)

        data_source_deleted.send(
            self, data_source_id=data_source.id, page=page, user=user
        )

    def dispatch_data_sources(
        self,
        user,
        data_sources: List[DataSource],
        dispatch_context: BuilderDispatchContext,
    ) -> Dict[int, Union[Any, Exception]]:
        """
        Dispatch the service related to the given data_sources if the user
        has the permission.

        :param user: The current user.
        :param data_sources: The data sources to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :return: The result of dispatching the data source mapped by data_source ID.
        """

        checks = [
            PermissionCheck(user, DispatchDataSourceOperationType.type, d)
            for d in data_sources
        ]

        CoreHandler().check_multiple_permissions(
            checks,
            workspace=data_sources[0].page.builder.workspace,
        )

        results = self.handler.dispatch_data_sources(data_sources, dispatch_context)

        # When public_allowed_properties is None, it indicates that filtering
        # shouldn't be applied, thus the results are returned without changes.
        if dispatch_context.public_allowed_properties is None:
            return results

        # We filter the fields before returning the result
        new_results = {}
        for data_source in data_sources:
            if isinstance(results[data_source.id], Exception):
                new_results[data_source.id] = results[data_source.id]
                continue

            allowed_field_names = dispatch_context.public_allowed_properties.get(
                "external", {}
            ).get(data_source.service.id, [])

            new_results[
                data_source.id
            ] = data_source.service.get_type().sanitize_result(
                data_source.service.specific,
                results[data_source.id],
                allowed_field_names,
            )

        return new_results

    def dispatch_page_data_sources(
        self,
        user,
        page: Page,
        dispatch_context: BuilderDispatchContext,
    ) -> Dict[int, Union[Any, Exception]]:
        """
        Dispatch the service related data_source of the given page if the user
        has the permission.

        :param user: The current user.
        :param page: the page we want to dispatch the data_sources for.
        :param dispatch_context: The context used for the dispatch.
        :return: The result of dispatching all the data source dispatch mapped by ID.
        """

        # We cache all data sources even the shared ones...
        data_sources = self.handler.get_data_sources_with_cache(page)

        # ...but we want to dispatch only those for this page
        dispatchable_data_sources = [d for d in data_sources if d.page_id == page.id]

        if not dispatchable_data_sources:
            return {}

        return self.dispatch_data_sources(
            user, dispatchable_data_sources, dispatch_context
        )

    def dispatch_data_source(
        self,
        user,
        data_source: DataSource,
        dispatch_context: BuilderDispatchContext,
    ) -> Any:
        """
        Dispatch the service related to the data_source if the user has the permission.

        :param user: The current user.
        :param data_source: The data source to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :return: return the dispatch result.
        """

        result = self.dispatch_data_sources(user, [data_source], dispatch_context)[
            data_source.id
        ]

        if isinstance(result, Exception):
            raise result

        return result

    def move_data_source(
        self,
        user: AbstractUser,
        data_source: DataSourceForUpdate,
        before: Optional[DataSource] = None,
    ) -> DataSource:
        """
        Moves an data_source in the page before another data_source. If the `before`
        data_source is omitted the data_source is moved at the end of the page.

        :param user: The user who move the data_source.
        :param data_source: The data_source we want to move.
        :param before: The data_source before which we want to move the given
            data_source.
        :return: The data_source with an updated order.
        """

        CoreHandler().check_permissions(
            user,
            UpdateDataSourceOperationType.type,
            workspace=data_source.page.builder.workspace,
            context=data_source,
        )

        # Check we are on the same page.
        if before and data_source.page_id != before.page_id:
            raise DataSourceNotInSamePage()

        try:
            data_source = self.handler.move_data_source(data_source, before=before)
        except CannotCalculateIntermediateOrder:
            # If it's failing, we need to recalculate all orders then move again.
            self.recalculate_full_orders(user, data_source.page)
            # Refresh the before data_source as the order might have changed.
            before.refresh_from_db()
            data_source = self.handler.move_data_source(data_source, before=before)

        data_source_moved.send(self, data_source=data_source, before=before, user=user)

        return data_source

    def recalculate_full_orders(self, user: AbstractUser, page: Page):
        """
        Recalculates the order to whole numbers of all data_sources of the given page
        and send a signal.
        """

        self.handler.recalculate_full_orders(page)

        data_source_orders_recalculated.send(self, page=page)
