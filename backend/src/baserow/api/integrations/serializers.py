from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.polymorphic import PolymorphicSerializer
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry


class IntegrationSerializer(serializers.ModelSerializer):
    """
    Basic integration serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the integration.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return integration_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = Integration
        fields = ("id", "application_id", "type", "name", "order")
        extra_kwargs = {
            "id": {"read_only": True},
            "application_id": {"read_only": True},
            "type": {"read_only": True},
            "name": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
        }


class PolymorphicIntegrationSerializer(PolymorphicSerializer):
    """
    Polymorphic serializer for the integrations.
    """

    base_class = IntegrationSerializer
    registry = integration_type_registry
    request = False


class CreateIntegrationSerializer(serializers.ModelSerializer):
    """
    This serializer allow to set the type of an integration and the integration id
    before which we want to insert the new integration.
    """

    type = serializers.ChoiceField(
        choices=lazy(integration_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the integration.",
    )
    before_id = serializers.IntegerField(
        required=False,
        help_text="If provided, creates the integration before the integration with "
        "the given id.",
    )

    class Meta:
        model = Integration
        fields = ("before_id", "type", "name")


class UpdateIntegrationSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(
        required=False,
        help_text="Moves the integration to this application, which can only be the "
        "shared application of its workspace: the integration becomes a workspace "
        "integration, usable by every application of the workspace.",
    )

    class Meta:
        model = Integration
        fields = ("name", "application_id")
        extra_kwargs = {
            "name": {"required": False},
        }


class MoveIntegrationSerializer(serializers.Serializer):
    before_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text=(
            "If provided, the integration is moved before the integration with this Id. "
            "Otherwise the integration is placed at the end of the page."
        ),
    )
