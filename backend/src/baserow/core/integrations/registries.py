from abc import ABC
from typing import Any, Dict, List, Optional, Type, TypeVar

from django.contrib.auth.models import AbstractUser

from baserow.api.integrations.fields import HasSecretField
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

    secret_fields: List[str] = []
    """
    Credentials that are write-only: they can be set and overwritten, but are
    never serialized back to any user, the creator included.

    This is deliberately narrower than `sensitive_fields`, which is stripped
    from workspace exports and kept out of the action log, and which for some
    types covers ordinary configuration such as the host and port.
    """

    secret_field_dependencies: Dict[str, List[str]] = {}
    """
    Maps a secret field to the request-target fields it protects. If any target
    field changes value, the secret must be re-supplied in the same request,
    otherwise the stored credential would be sent to a destination its owner
    never chose.

    Example: {"password": ["host", "port", "use_tls"]}
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

    def get_field_names(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> List[str]:
        """
        Removes the secret fields from the response serializer and replaces each
        with a `has_<name>` boolean. The request serializer keeps them, because
        setting a credential is the only thing a user may do with it.
        """

        field_names = super().get_field_names(
            request_serializer, extra_params, **kwargs
        )

        if request_serializer or not self.secret_fields:
            return field_names

        # Only the secrets this type actually serialises get a flag, so an
        # inconsistent declaration cannot surface a `has_` for a field the
        # response never carried.
        serialised_secrets = [n for n in field_names if n in self.secret_fields]

        return [name for name in field_names if name not in self.secret_fields] + [
            f"has_{name}" for name in serialised_secrets
        ]

    def get_field_overrides(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> Dict:
        """
        Declares the `has_<name>` booleans on the response serializer.
        """

        overrides = super().get_field_overrides(
            request_serializer, extra_params, **kwargs
        )

        if request_serializer or not self.secret_fields:
            return overrides

        # Only declare fields the name list carries: DRF asserts on every read
        # and write if a declared field is missing from it.
        field_names = self.get_field_names(request_serializer, extra_params, **kwargs)
        return {
            **overrides,
            **{
                f"has_{name}": HasSecretField(name)
                for name in self.secret_fields
                if f"has_{name}" in field_names
            },
        }

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
