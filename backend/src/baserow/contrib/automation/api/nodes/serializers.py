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
            "label",
            "service",
            "workflow",
            "type",
        )

        extra_kwargs = {
            "id": {"read_only": True},
            "workflow_id": {"read_only": True},
            "type": {"read_only": True},
        }


class CreateAutomationNodeSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the automation node",
    )
    position_node_id = serializers.IntegerField(
        required=False,
        help_text="If provided, creates the node before the node with the given id.",
    )
    position = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The unique ID of the branch this node is an output for.",
    )
    output = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The unique ID of the branch this node is an output for.",
    )

    class Meta:
        model = AutomationNode
        fields = (
            "id",
            "type",
            "position_node_id",
            "position",
            "output",
        )


class UpdateAutomationNodeSerializer(serializers.ModelSerializer):
    service = PolymorphicServiceRequestSerializer(
        required=False, help_text="The service associated with this automation node."
    )

    class Meta:
        model = AutomationNode
        fields = (
            "label",
            "service",
        )


class ReplaceAutomationNodeSerializer(serializers.Serializer):
    new_type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the new automation node",
    )


class MoveAutomationNodeSerializer(serializers.Serializer):
    position_node_id = serializers.IntegerField(
        required=False,
        help_text="The target position node.",
    )
    position = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The new position node.",
    )
    output = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The new output.",
    )
