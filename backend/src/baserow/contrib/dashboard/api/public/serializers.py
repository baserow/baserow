from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import PublicServiceSerializer
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.dashboard.api.widgets.serializers import WidgetSerializer
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.core.services.registries import service_type_registry


class PublicDashboardSerializer(serializers.ModelSerializer):
    """
    The part of a dashboard that visitors of its public link may see. The slug,
    the sharing state and the password are deliberately left out.
    """

    class Meta:
        model = Dashboard
        fields = ("id", "name", "description", "show_logo")
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"read_only": True},
            "description": {"read_only": True},
            "show_logo": {"read_only": True},
        }


class PublicDashboardDataSourceSerializer(PublicServiceSerializer):
    """
    Serializes a dashboard data source for visitors of a public dashboard. Like
    the regular data source serializer it flattens the service into the data
    source, but it only exposes what the widgets need to render the dispatched
    data: the schema and the context data. The service configuration, like the
    integration, the view, the filters or the search query, is never included.
    Service types may add their public fields through
    `public_serializer_field_names`. The id of the table is replaced by the
    public placeholder, like publicly shared views do.
    """

    id = serializers.SerializerMethodField(help_text="Data source id.")
    name = serializers.SerializerMethodField(
        help_text=DashboardDataSource._meta.get_field("name").help_text
    )
    type = serializers.SerializerMethodField(help_text="The type of the data source.")
    context_data = serializers.SerializerMethodField(
        help_text="The context data of the data source."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return service_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.INT)
    def get_id(self, instance):
        return self.context["data_source"].id

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance):
        return self.context["data_source"].name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The table service types expose the id of their table, which is part of
        # their public contract in the application builder. Visitors of a
        # dashboard don't need it, so they get the placeholder instead.
        if "table_id" in data:
            data["table_id"] = PUBLIC_PLACEHOLDER_ENTITY_ID
        return data

    class Meta(PublicServiceSerializer.Meta):
        fields = PublicServiceSerializer.Meta.fields + ("name", "context_data")
        extra_kwargs = {
            **PublicServiceSerializer.Meta.extra_kwargs,
            "name": {"read_only": True},
        }


def serialize_public_data_source(data_source: DashboardDataSource) -> dict:
    """
    Serializes a data source with the public serializer of its service type.

    :param data_source: The data source to serialize. It must have a service.
    :return: The serialized data source.
    """

    return service_type_registry.get_serializer(
        data_source.service,
        PublicDashboardDataSourceSerializer,
        context={"data_source": data_source},
        extra_params={"public": True},
    ).data


class PublicDashboardInfoSerializer(serializers.Serializer):
    """
    Everything a visitor needs to render a publicly shared dashboard. The widgets
    and data sources are passed through the serializer context.
    """

    dashboard = serializers.SerializerMethodField()
    widgets = serializers.SerializerMethodField()
    data_sources = serializers.SerializerMethodField()

    @extend_schema_field(PublicDashboardSerializer)
    def get_dashboard(self, instance):
        return PublicDashboardSerializer(instance).data

    @extend_schema_field(
        DiscriminatorCustomFieldsMappingSerializer(
            widget_type_registry, WidgetSerializer, many=True
        )
    )
    def get_widgets(self, instance):
        return [
            widget_type_registry.get_serializer(widget, WidgetSerializer).data
            for widget in self.context["widgets"]
        ]

    @extend_schema_field(
        DiscriminatorCustomFieldsMappingSerializer(
            service_type_registry, PublicDashboardDataSourceSerializer, many=True
        )
    )
    def get_data_sources(self, instance):
        return [
            serialize_public_data_source(data_source)
            for data_source in self.context["data_sources"]
            if data_source.service_id
        ]


class PublicDashboardAuthInfoSerializer(serializers.Serializer):
    """
    What the password page of a publicly shared dashboard needs before the
    visitor has entered the password. Nothing about the dashboard itself is
    revealed.
    """

    show_logo = serializers.BooleanField(
        help_text="Indicates whether the Baserow logo must be shown on the "
        "password page of the publicly shared dashboard."
    )


class PublicDashboardAuthRequestSerializer(serializers.Serializer):
    password = serializers.CharField()


class PublicDashboardAuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
