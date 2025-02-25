from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.registries import widget_type_registry


class WidgetSerializer(serializers.ModelSerializer):
    """
    Basic widget serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the widget.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return widget_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = Widget
        fields = (
            "id",
            "title",
            "description",
            "dashboard_id",
            "type",
            "order",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "title": {"read_only": True},
            "description": {"read_only": True},
            "dashboard_id": {"read_only": True},
            "type": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
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
