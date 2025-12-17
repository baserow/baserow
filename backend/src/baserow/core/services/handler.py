from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Union, cast
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.builder.pages.models import Page
from baserow.core.db import specific_iterator
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    ServiceDoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.utils import extract_allowed

from .dispatch_context import DispatchContext
from .types import DispatchResult, ServiceForUpdate, UpdatedService


class ServiceHandler:
    def get_service(
        self, service_id: int, base_queryset: QuerySet[Service] = None, specific=True
    ) -> Service:
        """
        Returns an service instance from the database.

        :param service_id: The ID of the service.
        :param base_queryset: The base queryset to use to build the query.
        :raises ServiceDoesNotExist: If the service can't be found.
        :return: The service instance.
        """

        queryset = base_queryset if base_queryset is not None else Service.objects.all()

        try:
            if specific:
                service = queryset.get(id=service_id).specific
                # We use the enhanced version of the queryset to get the related
                # fields.
                service = service.get_type().get_queryset().get(id=service_id)

                if service.integration_id:
                    specific_integration = IntegrationHandler().get_integration(
                        service.integration_id, specific=True
                    )
                    service.__class__.integration.field.set_cached_value(
                        service, specific_integration
                    )
            else:
                service = queryset.select_related(
                    "integration__application__workspace",
                ).get(id=service_id)
        except Service.DoesNotExist:
            raise ServiceDoesNotExist()

        return service

    def get_service_for_update(
        self, service_id: int, base_queryset: QuerySet[Service] = None
    ) -> ServiceForUpdate:
        """
        Returns an service instance from the database that can be safely updated.

        :param service_id: The ID of the service.
        :param base_queryset: The base queryset to use to build the query.
        :raises ServiceDoesNotExist: If the service can't be found.
        :return: The service instance.
        """

        queryset = base_queryset if base_queryset is not None else Service.objects.all()

        queryset = queryset.select_for_update(of=("self",))

        return self.get_service(
            service_id,
            base_queryset=queryset,
        )

    def get_services(
        self,
        integration: Optional[Integration] = None,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> Union[QuerySet[Page], Iterable[Page]]:
        """
        Gets all the specific services of a given integration.

        :param integration: The integration that holds the services if provided.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic services or the specific
            instances.
        :return: The services of that page.
        """

        queryset = base_queryset if base_queryset is not None else Service.objects.all()

        if integration:
            queryset = queryset.filter(integration=integration)

        if specific:
            # Apply the type specific queryset enhancement for performance.
            def per_content_type_queryset_hook(model, queryset):
                service_type = service_type_registry.get_by_model(model)
                return service_type.enhance_queryset(queryset)

            specific_services = list(
                specific_iterator(
                    queryset,
                    per_content_type_queryset_hook=per_content_type_queryset_hook,
                    skip_missing_specific_objects=True,
                )
            )

            integration_ids = [d.integration_id for d in specific_services]

            # Load the specific integrations as well
            specific_integration_map = {
                i.id: i
                for i in IntegrationHandler().get_integrations(
                    base_queryset=Integration.objects.filter(id__in=integration_ids)
                )
            }

            for service in specific_services:
                if service.integration_id:
                    service.integration = specific_integration_map[
                        service.integration_id
                    ]

            return specific_services
        else:
            queryset = queryset.select_related("integration__application")
            return queryset

    def create_service(self, service_type: ServiceType, **kwargs) -> Service:
        """
        Creates a new service.

        :param service_type: The type of the service.
        :param kwargs: Additional attributes of the service.
        :return: The created service.
        """

        shared_allowed_fields = ["type", "integration"]
        allowed_values = extract_allowed(
            kwargs, shared_allowed_fields + service_type.allowed_fields
        )

        model_class = cast(Service, service_type.model_class)

        service = model_class(**allowed_values)
        service.save()

        service_type.after_create(service, kwargs)

        return service

    def update_service(
        self, service_type: ServiceType, service: ServiceForUpdate, **kwargs
    ) -> UpdatedService:
        """
        Updates and service with values. Will also check if the values are allowed
        to be set on the service first.

        :param service_type: The type of the service.
        :param service: The service that should be updated.
        :param kwargs: The values that should be set on the service.
        :return: The updated service.
        """

        shared_allowed_fields = ["integration"]
        allowed_updates = extract_allowed(
            kwargs, shared_allowed_fields + service_type.allowed_fields
        )
        original_service_values = service_type.export_prepared_values(service)

        # Responsible for tracking the fields which changed in this update.
        # This will be passed to `service_type.after_update` so that granular
        # decisions can be made if certain field values changed.
        service_changes: Dict[str, Tuple] = {}

        for key, new_value in allowed_updates.items():
            prev_value = getattr(service, key)
            if prev_value != new_value:
                service_changes[key] = (prev_value, new_value)
            setattr(service, key, new_value)

        service.save()
        service_type.after_update(service, kwargs, service_changes)
        new_service_values = service_type.export_prepared_values(service)

        return UpdatedService(service, original_service_values, new_service_values)

    def delete_service(self, service_type: ServiceType, service: Service):
        """
        Deletes a service.

        :param service_type: The type of the service.
        :param service: The to-be-deleted service.
        """

        service_type.before_delete(service)
        service.delete()

    def dispatch_service(
        self,
        service: Service,
        dispatch_context: DispatchContext,
    ) -> DispatchResult:
        """
        Dispatch the given service.

        :param service: The service to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :return: The result of dispatching the service.
        """

        if (
            service.integration_id is None
            and service.get_type().integration_type is not None
        ):
            raise ServiceImproperlyConfiguredDispatchException(
                "No integration selected"
            )

        return service.get_type().dispatch(service, dispatch_context)

    def export_service(
        self,
        service,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        return service.get_type().export_serialized(
            service,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def import_service(
        self,
        integration,
        serialized_service,
        id_mapping,
        import_formula: Optional[Callable[[str, Dict[str, Any]], str]] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
        import_export_config: Optional[ImportExportConfig] = None,
    ):
        service_type = service_type_registry.get(serialized_service["type"])

        return service_type.import_serialized(
            integration,
            serialized_service,
            id_mapping,
            cache=cache,
            files_zip=files_zip,
            storage=storage,
            import_formula=import_formula,
            import_export_config=import_export_config,
        )
