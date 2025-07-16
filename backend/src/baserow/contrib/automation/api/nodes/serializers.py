from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry


class AutomationNodeSerializer(serializers.ModelSerializer):
    """Basic automation node serializer."""

    type = serializers.SerializerMethodField(help_text="The automation node type.")
    service = PolymorphicServiceSerializer(
        help_text="The service associated with this automation node."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return automation_node_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = AutomationNode
        fields = (
            "id",
            "order",
            "service",
            "workflow",
            "type",
            "previous_node_id",
            "previous_node_output",
        )

        extra_kwargs = {
            "id": {"read_only": True},
            "workflow_id": {"read_only": True},
            "type": {"read_only": True},
            "previous_node_id": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
        }


class CreateAutomationNodeSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the automation node",
    )
    before_id = serializers.IntegerField(
        required=False,
        help_text="If provided, creates the node before the node with the given id.",
    )

    class Meta:
        model = AutomationNode
        fields = ("id", "type", "before_id")


class UpdateAutomationNodeSerializer(serializers.ModelSerializer):
    service = PolymorphicServiceRequestSerializer(
        required=False, help_text="The service associated with this automation node."
    )

    class Meta:
        model = AutomationNode
        fields = (
            "service",
            "previous_node_output",
        )


class OrderAutomationNodesSerializer(serializers.Serializer):
    node_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text=("The ids of the nodes in the order they are supposed to be set in."),
    )


class ReplaceAutomationNodeSerializer(serializers.Serializer):
    new_type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the new automation node",
    )
