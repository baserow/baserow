from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.registries import widget_type_registry


class WidgetGridLayoutSerializer(serializers.Serializer):
    default_width = serializers.IntegerField(min_value=1)
    default_height = serializers.IntegerField(min_value=1)
    min_width = serializers.IntegerField(min_value=1)
    min_height = serializers.IntegerField(min_value=1)
    max_width = serializers.IntegerField(min_value=1)
    max_height = serializers.IntegerField(min_value=1)


class WidgetSerializer(serializers.ModelSerializer):
    """
    Basic widget serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the widget.")
    grid_layout = serializers.SerializerMethodField(
        help_text="The size constraints for this widget type."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return widget_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(WidgetGridLayoutSerializer)
    def get_grid_layout(self, instance):
        return instance.get_type().get_grid_layout().as_dict()

    class Meta:
        model = Widget
        fields = (
            "id",
            "title",
            "description",
            "dashboard_id",
            "type",
            "order",
            "grid_x",
            "grid_y",
            "grid_width",
            "grid_height",
            "grid_layout",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "title": {"read_only": True},
            "description": {"read_only": True},
            "dashboard_id": {"read_only": True},
            "type": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
            "grid_x": {"read_only": True},
            "grid_y": {"read_only": True},
            "grid_width": {"read_only": True},
            "grid_height": {"read_only": True},
            "grid_layout": {"read_only": True},
        }


class CreateWidgetSerializer(serializers.ModelSerializer):
    """
    This serializer allow to set the type of the new widget.
    """

    type = serializers.ChoiceField(
        choices=lazy(widget_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the widget.",
    )

    class Meta:
        model = Widget
        fields = (
            "title",
            "description",
            "type",
        )
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
        }


class UpdateWidgetSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(widget_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the widget.",
    )

    class Meta:
        model = Widget
        fields = (
            "title",
            "description",
        )
        extra_kwargs = {
            "title": {"required": False, "allow_blank": False},
            "description": {"required": False, "allow_blank": True},
        }


class WidgetLayoutItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    grid_x = serializers.IntegerField(min_value=0)
    grid_y = serializers.IntegerField(min_value=0)
    grid_width = serializers.IntegerField(min_value=1)
    grid_height = serializers.IntegerField(min_value=1)


class UpdateWidgetLayoutSerializer(serializers.Serializer):
    widgets = WidgetLayoutItemSerializer(
        many=True,
        help_text=(
            "The complete layout of the dashboard widgets visible to the current "
            "user. It is vertically compacted before being persisted."
        ),
    )
