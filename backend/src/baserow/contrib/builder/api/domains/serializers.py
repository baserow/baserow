from typing import List

from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.app_auth_providers.serializers import AppAuthProviderSerializer
from baserow.api.polymorphic import PolymorphicSerializer
from baserow.api.services.serializers import PublicServiceSerializer
from baserow.api.user_files.serializers import UserFileField
from baserow.api.workspaces.serializers import WorkspaceSerializer
from baserow.contrib.builder.api.pages.serializers import (
    PathParamSerializer,
    QueryParamSerializer,
)
from baserow.contrib.builder.api.serializers import BuilderSerializer
from baserow.contrib.builder.api.validators import image_file_validation
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.registries import domain_type_registry
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.services.registries import service_type_registry
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import user_source_type_registry


class DomainSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(help_text="The type of the domain.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return domain_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = Domain
        fields = ("id", "type", "domain_name", "order", "builder_id", "last_published")
        extra_kwargs = {
            "id": {"read_only": True},
            "builder_id": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }


class CreateDomainSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(domain_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the domain.",
    )

    class Meta:
        model = Domain
        fields = (
            "type",
            "domain_name",
        )


class UpdateDomainSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(domain_type_registry.get_types, list)(),
        required=False,
        help_text="The type of the domain.",
    )

    domain_name = serializers.CharField(
        required=False, help_text=Domain._meta.get_field("domain_name").help_text
    )

    class Meta:
        model = Domain
        fields = (
            "type",
            "domain_name",
        )


class OrderDomainsSerializer(serializers.Serializer):
    domain_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The ids of the domains in the order they are supposed to be set in",
    )


class PublicElementSerializer(serializers.ModelSerializer):
    """
    Basic element serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the element.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return element_type_registry.get_by_model(instance.specific_class).type

    visibility_condition = FormulaSerializerField(
        help_text=Element._meta.get_field("visibility_condition").help_text,
    )

    style_background_file = UserFileField(
        allow_null=True,
        help_text="The background image file",
        validators=[image_file_validation],
    )

    class Meta:
        model = Element
        fields = (
            "id",
            "page_id",
            "type",
            "order",
            "page_id",
            "parent_element_id",
            "place_in_container",
            "css_classes",
            "visibility",
            "visibility_condition",
            "styles",
            "style_border_top_color",
            "style_border_top_size",
            "style_padding_top",
            "style_margin_top",
            "style_border_bottom_color",
            "style_border_bottom_size",
            "style_padding_bottom",
            "style_margin_bottom",
            "style_border_left_color",
            "style_border_left_size",
            "style_padding_left",
            "style_margin_left",
            "style_border_right_color",
            "style_border_right_size",
            "style_padding_right",
            "style_margin_right",
            "style_background_radius",
            "style_border_radius",
            "style_background",
            "style_background_color",
            "style_background_file",
            "style_background_mode",
            "style_width",
            "style_width_child",
            "role_type",
            "roles",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "page_id": {"read_only": True},
            "type": {"read_only": True},
        }


class PublicPageSerializer(serializers.ModelSerializer):
    """
    A public version of the page serializer with less data to prevent data leaks.
    """

    path_params = PathParamSerializer(many=True, required=False)
    query_params = QueryParamSerializer(many=True, required=False)

    class Meta:
        model = Page
        fields = (
            "id",
            "name",
            "path",
            "path_params",
            "shared",
            "visibility",
            "role_type",
            "roles",
            "query_params",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "builder_id": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }


class PublicPolymorphicAppAuthProviderSerializer(PolymorphicSerializer):
    """
    Polymorphic serializer for App Auth providers.
    """

    base_class = AppAuthProviderSerializer
    registry = app_auth_provider_type_registry
    extra_params = {"public": True}


class BasePublicUserSourceSerializer(serializers.ModelSerializer):
    """
    Basic user source serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the user_source.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return user_source_type_registry.get_by_model(instance.specific_class).type

    auth_providers = PublicPolymorphicAppAuthProviderSerializer(
        required=False,
        many=True,
        help_text="Auth providers related to this user source.",
    )

    class Meta:
        model = UserSource
        fields = (
            "id",
            "uid",
            "type",
            "name",
            "order",
            "auth_providers",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "uid": {"read_only": True},
            "auth_providers": {"read_only": True},
            "type": {"read_only": True},
            "name": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
        }


class PolymorphicPublicUserSourceSerializer(PolymorphicSerializer):
    """
    Public polymorphic serializer for user sources.
    """

    base_class = BasePublicUserSourceSerializer
    registry = user_source_type_registry
    request = False


class PublicBuilderSerializer(BuilderSerializer):
    """
    A public version of the builder serializer with less data to prevent data leaks.
    """

    user_sources = serializers.SerializerMethodField(
        help_text="The user sources related with this builder."
    )

    workspace = serializers.SerializerMethodField()

    class Meta:
        ref_name = "PublicBuilderApplication"

    @extend_schema_field(PublicPageSerializer(many=True))
    def get_pages(self, instance: Builder) -> List:
        """
        Returns the pages related to this public builder.

        :param instance: The builder application instance.
        :return: A list of serialized pages that belong to this instance.
        """

        pages = PageHandler().get_pages(instance)

        return PublicPageSerializer(pages, many=True).data

    @extend_schema_field(PolymorphicPublicUserSourceSerializer(many=True))
    def get_user_sources(self, instance: Builder) -> List:
        """
        Returns the user sources related to this public builder.

        :param instance: The builder application instance.
        :return: A list of serialized user sources that belong to this instance.
        """

        user_sources = instance.user_sources.all()

        return PolymorphicPublicUserSourceSerializer(user_sources, many=True).data

    def get_workspace(self, obj):
        return WorkspaceSerializer(obj.get_workspace()).data


class PublicDataSourceSerializer(PublicServiceSerializer):
    """
    Basic data_source serializer mostly for returned values. This serializer flatten the
    service properties so that from an API POV the data_source object only exists.
    """

    id = serializers.SerializerMethodField(help_text="Data source id.")
    name = serializers.SerializerMethodField(
        help_text=DataSource._meta.get_field("name").help_text
    )
    page_id = serializers.SerializerMethodField(
        help_text=DataSource._meta.get_field("page").help_text
    )
    order = serializers.SerializerMethodField(
        help_text=DataSource._meta.get_field("order").help_text
    )
    type = serializers.SerializerMethodField(help_text="The type of the data source.")
    context_data = serializers.SerializerMethodField(
        help_text="The context data of the data source."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        if isinstance(instance, DataSource):
            return None
        else:
            return service_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.INT)
    def get_id(self, instance):
        return self.context["data_source"].id

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance):
        return self.context["data_source"].name

    @extend_schema_field(OpenApiTypes.INT)
    def get_page_id(self, instance):
        return self.context["data_source"].page_id

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_order(self, instance):
        return self.context["data_source"].order

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data(self, instance):
        service_instance = (
            instance.service if isinstance(instance, DataSource) else instance
        )
        if service_instance:
            return super().get_context_data(service_instance)
        else:
            return {}

    class Meta(PublicServiceSerializer.Meta):
        fields = PublicServiceSerializer.Meta.fields + (
            "name",
            "page_id",
            "order",
            "context_data",
        )
        extra_kwargs = {
            **PublicServiceSerializer.Meta.extra_kwargs,
            "name": {"read_only": True},
            "page_id": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
            "context_data": {"read_only": True},
        }
