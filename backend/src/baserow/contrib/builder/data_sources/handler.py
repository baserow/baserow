from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Union
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import QuerySet
from django.db.utils import DatabaseError, IntegrityError

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceDoesNotExist,
    DataSourceNameNotUniqueError,
)
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.types import DataSourceDict
from baserow.core.cache import local_cache
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType
from baserow.core.storage import ExportZipFile
from baserow.core.utils import find_unused_name

from .types import DataSourceForUpdate

if TYPE_CHECKING:
    from baserow.contrib.builder.models import Builder


class DataSourceHandler:
    def __init__(self):
        self.service_handler = ServiceHandler()

    def get_data_source(
        self,
        data_source_id: int,
        base_queryset: Optional[QuerySet] = None,
        specific=True,
        with_cache=False,
    ) -> DataSource:
        """
        Returns a data_source instance from the database.

        :param data_source_id: The ID of the data_source.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Return the specific version of related objects like the
          service and the integration
        :raises DataSourceDoesNotExist: If the data_source can't be found.
        :param with_cache: Whether this method should use the short
          cache for data_sources.
        :return: The data_source instance.
        """

        if with_cache and not base_queryset:
            return local_cache.get(
                f"ab_data_source_{data_source_id}_{specific}",
                lambda: self._get_data_source(
                    data_source_id, base_queryset, specific=specific
                ),
            )
        else:
            return self._get_data_source(
                data_source_id, base_queryset, specific=specific
            )

    def _get_data_source(
        self,
        data_source_id: int,
        base_queryset: Optional[QuerySet] = None,
        specific=True,
    ) -> DataSource:
        """
        Base version of the get_data_source without the caching capabilities.

        :param data_source_id: The ID of the data_source.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Return the specific version of related objects like the
          service and the integration
        :raises DataSourceDoesNotExist: If the data_source can't be found.
        :return: The data_source instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else DataSource.objects.all()
        )

        queryset = queryset.select_related("page__builder__workspace")

        try:
            if specific:
                data_source = queryset.get(id=data_source_id)
                if data_source.service_id:
                    specific_service = ServiceHandler().get_service(
                        data_source.service_id, specific=True
                    )
                    data_source.__class__.service.field.set_cached_value(
                        data_source, specific_service
                    )
            else:
                data_source = queryset.select_related("service__integration").get(
                    id=data_source_id
                )
        except DataSource.DoesNotExist as exc:
            raise DataSourceDoesNotExist() from exc

        return data_source

    def get_data_source_for_update(
        self, data_source_id: int, base_queryset=None
    ) -> DataSourceForUpdate:
        """
        Returns a data_source instance from the database that can be safely updated.

        :param data_source_id: The ID of the data_source.
        :param base_queryset: The base queryset to use to build the query.
        :raises DataSourceDoesNotExist: If the data_source can't be found.
        :return: The data_source instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else DataSource.objects.all()
        )

        queryset = queryset.select_for_update(of=("self",))

        return self.get_data_source(
            data_source_id,
            base_queryset=queryset,
        )

    def _query_data_sources(
        self, base_queryset: QuerySet, specific=True, with_cache=False
    ):
        """
        Query data sources from the base queryset.

        :param base_queryset: The base QuerySet to query from.
        :param specific: A boolean flag indicating whether to include specific service
          instance.
        :param with_cache: Whether this method should populate the short
          cache for data_sources.
        :return: A list of queried data sources.
        """

        data_source_queryset = base_queryset.select_related("page__builder__workspace")

        if specific:
            data_sources = list(data_source_queryset.all())

            # Get all service ids to get them from DB in one query
            service_ids = [
                data_source.service_id
                for data_source in data_sources
                if data_source.service_id is not None
            ]

            specific_services_map = {
                s.id: s
                for s in ServiceHandler().get_services(
                    base_queryset=Service.objects.filter(id__in=service_ids)
                )
            }

            # Distribute specific services to their data_source
            for data_source in data_sources:
                service_id = data_source.service_id
                if service_id is not None and service_id in specific_services_map:
                    service = specific_services_map[service_id]
                    # Only attach the service if it's not trashed
                    data_source.service = service if not service.trashed else None
                else:
                    # Clear the service since it's likely trashed
                    data_source.service = None

            data_sources = [d for d in data_sources if d.service is not None]

        else:
            data_source_queryset.select_related(
                "service__integration__application",
            )
            data_sources = data_source_queryset.all()

        if with_cache:
            for ds in data_sources:
                local_cache.get(
                    f"ab_data_source_{ds.id}_{specific}",
                    ds,
                )
        return data_sources

    def get_data_sources(
        self,
        page: Page,
        base_queryset: Optional[QuerySet] = None,
        with_shared: Optional[bool] = False,
        specific: Optional[bool] = True,
        with_cache=False,
    ) -> Union[QuerySet[DataSource], Iterable[DataSource]]:
        """
        Gets all the specific data_sources of a given page.

        :param page: The page that holds the data_sources.
        :param base_queryset: The base queryset to use to build the query.
        :param with_shared: If True, also returns the data sources from the shared page
          on the same builder.
        :param specific: If True, return the specific version of the service related
          to the data source
        :param with_cache: Whether this method should populate the short
          cache for data_sources.
        :return: The data_sources of that page.
        """

        data_source_queryset = (
            base_queryset if base_queryset is not None else DataSource.objects.all()
        )

        if with_shared:
            # Get the data source for the same builder on the shared page
            data_source_queryset = data_source_queryset.filter(
                page__in=[page.builder.shared_page, page]
                # We order by shared page because shared pages must appear before local
                # data source so that later we can reference previous data sources
                # only in formulas.
            ).order_by("-page__shared", "order", "id")

        else:
            data_source_queryset = data_source_queryset.filter(page=page)

        return self._query_data_sources(
            data_source_queryset,
            specific=specific,
            with_cache=with_cache,
        )

    def get_builder_data_sources(
        self,
        builder: "Builder",
        base_queryset: Optional[QuerySet] = None,
        specific: Optional[bool] = True,
        with_cache=False,
    ) -> Union[QuerySet[DataSource], Iterable[DataSource]]:
        """
        Gets all the specific data_sources of a given builder.

        :param builder: The builder that holds the data_sources.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: If True, return the specific version of the service related
          to the data source
        :param with_cache: Whether this method should populate the short
          cache for data_sources.
        :return: The data_sources of that builder.
        """

        data_source_queryset = (
            base_queryset if base_queryset is not None else DataSource.objects.all()
        )

        data_source_queryset = data_source_queryset.filter(page__builder=builder)

        return self._query_data_sources(
            data_source_queryset,
            specific=specific,
            with_cache=with_cache,
        )

    def get_data_sources_with_cache(
        self,
        page: Page,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ):
        """
        Gets all the data sources of a given page. This version cache the
        data sources of the page onto the page object to improve perfs.

        :param page: The page that holds the data_source.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: If True, return the specific version of the service related
          to the data source
        :return: The data_sources of the page.
        """

        return local_cache.get(
            f"ab_data_sources_{page.id}_{specific}",
            lambda: DataSourceHandler().get_data_sources(
                page,
                base_queryset=base_queryset,
                specific=specific,
                with_shared=True,
            ),
        )

    def get_data_source_with_cache(
        self,
        page: Page,
        data_source_id: int,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> DataSource:
        """
        Returns a data_source linked to a specific page. This version preload all
        data sources of the page at the first access and cache them.

        :param page: The page that holds the data_source.
        :param data_source_id: The ID of the data_source.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: If True, return the specific version of the service related
          to the integration
        :raises DataSourceDoesNotExist: If the data_source can't be found.
        :return: The data_source instance.
        """

        data_sources = self.get_data_sources_with_cache(
            page,
            base_queryset=base_queryset,
            specific=specific,
        )

        for data_source in data_sources:
            if data_source.id == data_source_id:
                return data_source

        raise DataSourceDoesNotExist()

    def find_unused_data_source_name(self, page: Page, proposed_name: str) -> str:
        """
        Finds an unused name for a page in a builder.

        :param page: The page that the data source will belong to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        existing_pages_names = list(
            DataSource.objects.filter(page=page).values_list("name", flat=True)
        )
        return find_unused_name([proposed_name], existing_pages_names, max_length=255)

    def create_data_source(
        self,
        page: Page,
        name: str,
        service_type: Optional[ServiceType] = None,
        before: Optional[DataSource] = None,
        **kwargs,
    ) -> DataSource:
        """
        Creates a new data_source for a page.

        :param page: The page the data_source exists in.
        :param name: The human name of the data_source.
        :param service_type: The type of the service related to the data_source.
        :param before: If set, the new data_source is inserted before this data_source.
        :param kwargs: Additional attributes of the related service.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the data_source of the page must be
            recalculated in this case before calling this method again.
        :return: The created data_source.
        """

        if before:
            order = DataSource.get_unique_order_before_data_source(before)
        else:
            order = DataSource.get_last_order(page)

        if service_type:
            service = self.service_handler.create_service(
                service_type=service_type, **kwargs
            )
        else:
            service = None

        try:
            data_source = DataSource.objects.create(
                page=page, order=order, name=name, service=service
            )
        except IntegrityError as error:
            # The only unique values are page and name, together.
            if "unique" in str(error):
                raise DataSourceNameNotUniqueError(name)
            raise error

        data_source.save()

        return data_source

    def update_data_source(
        self,
        data_source: DataSourceForUpdate,
        service_type: Optional[ServiceType] = None,
        name: Optional[str] = None,
        page: Optional[Page] = None,
        **kwargs,
    ) -> DataSource:
        """
        Updates a data_source and the related service with values.

        :param data_source: The data_source that should be updated.
        :param service_type: The service type for the data_source's service.
        :param name: A new name for the data_source.
        :param page: The data source's page.
        :param kwargs: The values that should be set on the data_source.
        :return: The updated data_source.
        """

        new_service_type = None
        if "new_service_type" in kwargs:
            new_service_type = kwargs.pop("new_service_type")

            integration = None
            integration_type = None
            if data_source.service:
                integration = data_source.service.integration
                ServiceHandler().delete_service(service_type, data_source.service)
                data_source.service = None

            if integration:
                integration_type = integration_type_registry.get_by_model(
                    integration.specific
                ).type

            if new_service_type:
                # Check if the new service type can reuse the previous integration
                if new_service_type.integration_type != integration_type:
                    integration = None

                service = self.service_handler.create_service(
                    service_type=new_service_type,
                    integration=integration,
                    **kwargs,
                )
                data_source.service = service

        if data_source.service and kwargs and new_service_type is None:
            service_to_update = self.service_handler.get_service_for_update(
                data_source.service.id
            )
            self.service_handler.update_service(
                service_type, service_to_update, **kwargs
            )
            data_source.service = service_to_update

        if page is not None and data_source.page_id != page.id:
            data_source.page = page
            # Add the moved data source at the end of the new page
            data_source.order = DataSource.get_last_order(page)
            # Check for name conflicts
            data_source.name = self.find_unused_data_source_name(page, data_source.name)

        if name is not None:
            data_source.name = name

        try:
            data_source.save()
        except DatabaseError:
            # If the `name` changes, on a PATCH Django will raise a `DatabaseError`
            # exception if it's already in use on the page, instead of an
            # `IntegrityError` like in `create_data_source`.
            if name is not None:
                raise DataSourceNameNotUniqueError(name)

        return data_source

    def delete_data_source(self, data_source: DataSource):
        """
        Deletes a data_source.

        :param data_source: The to-be-deleted data_source.
        """

        data_source.delete()

    def dispatch_data_sources(
        self, data_sources, dispatch_context: BuilderDispatchContext
    ):
        """
        Dispatch the service related to the data_sources.

        :param data_sources: The data sources to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :return: The result of dispatching the data source mapped by data source ID.
            If an Exception occurred during the dispatch the exception is return as
            result for this data source.
        """

        data_sources_dispatch = {}
        for data_source in data_sources:
            if (
                dispatch_context.public_allowed_properties is not None
                and data_source.service_id
                not in dispatch_context.public_allowed_properties["all"]
            ):
                # We ignore data sources that have no used properties at all.
                # It means they are not used at least for the current user.
                if data_source.service.get_type().returns_list:
                    data_sources_dispatch[data_source.id] = {
                        "has_next_page": False,
                        "results": [],
                    }
                else:
                    data_sources_dispatch[data_source.id] = {}
                continue

            try:
                data_sources_dispatch[data_source.id] = self.dispatch_data_source(
                    data_source, dispatch_context
                )
            except Exception as e:
                data_sources_dispatch[data_source.id] = e

        return data_sources_dispatch

    def dispatch_data_source(
        self, data_source: DataSource, dispatch_context: BuilderDispatchContext
    ) -> Any:
        """
        Dispatch the service related to the data_source.

        :param data_source: The data source to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :raises ServiceImproperlyConfiguredDispatchException: If the data source is
          not properly configured.
        :return: The result of dispatching the data source.
        """

        if not data_source.service_id:
            raise ServiceImproperlyConfiguredDispatchException(
                "The service type is missing."
            )
        cache = dispatch_context.cache
        page = dispatch_context.page
        current_data_source_dispatched = dispatch_context.data_source or data_source

        if current_data_source_dispatched != data_source:
            data_sources = self.get_data_sources_with_cache(page)
            ordered_ids = [d.id for d in data_sources]
            if ordered_ids.index(current_data_source_dispatched.id) < ordered_ids.index(
                data_source.id
            ):
                raise ServiceImproperlyConfiguredDispatchException(
                    "You can't reference a data source after the current data source"
                )

        # Clone the dispatch context to keep the call stack as it is
        cloned_dispatch_context = dispatch_context.clone(
            data_source=current_data_source_dispatched
        )
        # Declare the call and check for recursion
        cloned_dispatch_context.add_call(data_source.id)

        if data_source.id not in cache.setdefault("data_source_contents", {}):
            service_dispatch = self.service_handler.dispatch_service(
                data_source.service.specific, cloned_dispatch_context
            )

            # Cache the dispatch in the formula cache if we have formulas that need
            # it later
            cache["data_source_contents"][data_source.id] = service_dispatch.data

        return cache["data_source_contents"][data_source.id]

    def move_data_source(
        self, data_source: DataSourceForUpdate, before: Optional[DataSource] = None
    ) -> DataSource:
        """
        Moves the given data_source before the specified `before` data_source in the
        same page.

        :param data_source: The data_source to move.
        :param before: The data_source before which to move the `data_source`. If
            before is not specified, the data_source is moved at the end of the list.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the data_source of the page must be
            recalculated in this case before calling this method again.
        :return: The moved data_source.
        """

        if before:
            data_source.order = DataSource.get_unique_order_before_data_source(before)
        else:
            data_source.order = DataSource.get_last_order(data_source.page)

        data_source.save()

        return data_source

    def recalculate_full_orders(
        self,
        page: Page,
    ):
        """
        Recalculates the order to whole numbers of all data_sources of the given page.
        """

        DataSource.recalculate_full_orders(
            queryset=DataSource.objects.filter(page=page)
        )

    def export_data_source(
        self,
        data_source: DataSource,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> DataSourceDict:
        """
        Serializes the given data source.

        :param data_source: The data source instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        serialized_service = None

        if data_source.service:
            serialized_service = ServiceHandler().export_service(
                data_source.service, files_zip=files_zip, storage=storage, cache=cache
            )

        return DataSourceDict(
            id=data_source.id,
            name=data_source.name,
            order=str(data_source.order),
            service=serialized_service,
        )

    def import_data_source(
        self,
        page,
        serialized_data_source: DataSourceDict,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Creates an instance using the serialized version previously exported with
        `.export_data_source'.

        :param page: The page instance the new data source should belong to.
        :param serialized_data_source: The serialized version of the data source.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the new data source instance.
        """

        if "builder_data_sources" not in id_mapping:
            id_mapping["builder_data_sources"] = {}

        # First we get the service if any
        service = None
        serialized_service = serialized_data_source.get("service", None)
        if serialized_service:
            # Get the integration if any
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
                import_formula=import_formula,
            )

        # Then create the data source with the service
        data_source = DataSource.objects.create(
            page=page,
            service=service,
            order=serialized_data_source["order"],
            name=serialized_data_source["name"],
        )

        id_mapping["builder_data_sources"][
            serialized_data_source["id"]
        ] = data_source.id

        return data_source
