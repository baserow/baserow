from django.utils.functional import lazy

from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.polymorphic import PolymorphicRequestSerializer, PolymorphicSerializer
from baserow.api.workspaces.serializers import WorkspaceSerializer
from baserow.core.db import specific_iterator
from baserow.core.models import Application
from baserow.core.registries import application_type_registry


class ApplicationSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    workspace = WorkspaceSerializer(
        help_text="The workspace that the application belongs to."
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "name",
            "order",
            "type",
            "workspace",
            "created_on",
        )
        extra_kwargs = {"id": {"read_only": True}}

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return application_type_registry.get_by_model(instance.specific_class).type


class PolymorphicApplicationResponseSerializer(PolymorphicSerializer):
    base_class = ApplicationSerializer
    registry = application_type_registry
    request = False


class PublicPolymorphicApplicationResponseSerializer(
    PolymorphicApplicationResponseSerializer
):
    name_prefix = "public_"
    extra_params = {"public": True}


class BaseApplicationCreatePolymorphicSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(application_type_registry.get_types, list)()
    )
    init_with_data = serializers.BooleanField(default=False)

    class Meta:
        model = Application
        fields = ("name", "type", "init_with_data")


class PolymorphicApplicationCreateSerializer(PolymorphicRequestSerializer):
    base_class = BaseApplicationCreatePolymorphicSerializer
    registry = application_type_registry


class BaseApplicationUpdatePolymorphicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ("name",)


class PolymorphicApplicationUpdateSerializer(PolymorphicRequestSerializer):
    base_class = BaseApplicationUpdatePolymorphicSerializer
    registry = application_type_registry


class OrderApplicationsSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Application ids in the desired order.",
    )


class InstallTemplateJobApplicationsSerializer(serializers.JSONField):
    def to_representation(self, value):
        application_ids = super().to_representation(value)

        if not application_ids:
            return None

        applications = specific_iterator(
            Application.objects.select_related("content_type", "workspace").filter(
                pk__in=application_ids, workspace__trashed=False
            )
        )
        return [
            PolymorphicApplicationResponseSerializer(app).data for app in applications
        ]
