from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.polymorphic import PolymorphicRequestSerializer, PolymorphicSerializer
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


class ServiceSerializer(serializers.ModelSerializer):
    """
    Basic service serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the service.")
    schema = serializers.SerializerMethodField(help_text="The schema of the service.")
    context_data = serializers.SerializerMethodField(
        help_text="The context data of the service."
    )
    context_data_schema = serializers.SerializerMethodField(
        help_text="The schema context data of the service."
    )

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data(self, instance):
        return instance.get_type().get_context_data(instance.specific)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data_schema(self, instance):
        return instance.get_type().get_context_data_schema(instance.specific)

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return instance.get_type().type

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_schema(self, instance):
        return instance.get_type().generate_schema(instance.specific)

    class Meta:
        model = Service
        fields = (
            "id",
            "integration_id",
            "type",
            "schema",
            "context_data",
            "context_data_schema",
            "sample_data",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "integration_id": {"read_only": True},
            "type": {"read_only": True},
            "schema": {"read_only": True},
            "context_data": {"read_only": True},
            "context_data_schema": {"read_only": True},
            "sample_data": {"read_only": True},
        }


class PublicServiceSerializer(serializers.ModelSerializer):
    """
    Basic service serializer mostly for public returned values.
    Don't add sensitive data here.
    """

    type = serializers.SerializerMethodField(help_text="The type of the service.")
    schema = serializers.SerializerMethodField(help_text="The schema of the service.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return service_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data(self, instance):
        return instance.get_type().get_context_data(
            instance.specific, allowed_fields=self.context.get("allowed_fields")
        )

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_schema(self, instance):
        return instance.get_type().generate_schema(
            instance.specific, allowed_fields=self.context.get("allowed_fields")
        )

    class Meta:
        model = Service
        fields = ("id", "type", "schema")
        extra_kwargs = {
            "id": {"read_only": True},
            "type": {"read_only": True},
            "schema": {"read_only": True},
            "context_data": {"read_only": True},
        }


class CreateServiceSerializer(serializers.ModelSerializer):
    """
    This serializer allow to set the type of a service and the service id before which
    we want to insert the new service.
    """

    type = serializers.ChoiceField(
        choices=lazy(service_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the service.",
    )

    class Meta:
        model = Service
        fields = ("type",)


class UpdateServiceSerializer(serializers.ModelSerializer):
    integration_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="The related integration id.",
    )

    class Meta:
        model = Service
        fields = ("integration_id",)


class PolymorphicServiceSerializer(PolymorphicSerializer):
    base_class = ServiceSerializer
    registry = service_type_registry


class BasePolymorphicRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id",)


class PolymorphicServiceRequestSerializer(PolymorphicRequestSerializer):
    base_class = BasePolymorphicRequestSerializer
    registry = service_type_registry


class PublicPolymorphicServiceSerializer(PolymorphicServiceSerializer):
    extra_params = {"public": True}
