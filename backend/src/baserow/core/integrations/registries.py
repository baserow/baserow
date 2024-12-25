from abc import ABC
from typing import Any, Dict, Optional, Type, TypeVar

from django.contrib.auth.models import AbstractUser

from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

from .models import Integration
from .types import IntegrationDictSubClass, IntegrationSubClass


class IntegrationType(
    ModelInstanceMixin[Integration],
    EasyImportExportMixin[IntegrationSubClass],
    CustomFieldsInstanceMixin,
    Instance,
    ABC,
):
    SerializedDict: Type[IntegrationDictSubClass]
    parent_property_name = "application"
    id_mapping_name = "integrations"

    """
    An integration type define a specific integration with a given external service.
    """

    def enhance_queryset(self, queryset):
        """
        Allow to enhance the queryset when querying the integration mainly to improve
        performances.
        """

        return queryset

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        that just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :return: The updated values.
        """

        return values

    def serialize_property(
        self,
        integration: Integration,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "order":
            return str(integration.order)

        return super().serialize_property(
            integration, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
    ) -> IntegrationSubClass:
        return super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def after_import(self, user: AbstractUser, instance: Integration) -> None:
        """
        Hook to trigger any post import logic.
        """

    def get_context_data(self, instance: Integration) -> Optional[Dict]:
        """
        Get all the context data for an integration that is required by the editor to
        configure a service.

        :return: Context data
        """

        return None


IntegrationTypeSubClass = TypeVar("IntegrationTypeSubClass", bound=IntegrationType)


class IntegrationTypeRegistry(
    ModelRegistryMixin[IntegrationSubClass, IntegrationTypeSubClass],
    Registry[IntegrationTypeSubClass],
    CustomFieldsRegistryMixin,
):
    """
    Contains all the integration types.
    """

    name = "integration"


integration_type_registry: IntegrationTypeRegistry = IntegrationTypeRegistry()
