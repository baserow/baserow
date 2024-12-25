from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.polymorphic import PolymorphicSerializer
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.auth_provider.validators import validate_domain


class AppAuthProviderSerializer(serializers.ModelSerializer):
    """
    Basic app_auth_provider serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(
        help_text="The type of the app_auth_provider."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return app_auth_provider_type_registry.get_by_model(
            instance.specific_class
        ).type

    class Meta:
        model = AppAuthProvider
        fields = ("type", "id", "domain")
        extra_kwargs = {
            "id": {"read_only": True},
            "user_source_id": {"read_only": True},
            "type": {"read_only": True},
        }


class BaseAppAuthProviderSerializer(serializers.ModelSerializer):
    """
    This serializer allow to set the type of an app_auth_provider and the
    app_auth_provider id before which we want to insert the new app_auth_provider.
    """

    type = serializers.ChoiceField(
        choices=lazy(app_auth_provider_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the app_auth_provider.",
    )

    domain = serializers.CharField(
        validators=[validate_domain],
        required=False,
        allow_null=True,
        help_text=AppAuthProvider._meta.get_field("domain").help_text,
    )

    class Meta:
        model = AppAuthProvider
        fields = ("type", "user_source_id", "domain")


class PolymorphicAppAuthProviderSerializer(PolymorphicSerializer):
    """
    Polymorphic serializer for App Auth providers.
    """

    base_class = BaseAppAuthProviderSerializer
    registry = app_auth_provider_type_registry
    request = True


class ReadPolymorphicAppAuthProviderSerializer(PolymorphicSerializer):
    """
    Polymorphic serializer for App Auth providers.
    """

    base_class = AppAuthProviderSerializer
    registry = app_auth_provider_type_registry
