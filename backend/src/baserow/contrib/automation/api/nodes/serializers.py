from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.workflow_actions.serializers import WorkflowActionSerializer
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry


class AutomationNodeSerializer(WorkflowActionSerializer):
    """Basic automation node serializer."""

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return automation_node_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = AutomationNode
        fields = ("id", "order", "workflow", "type", "previous_node_output")

        extra_kwargs = {
            "id": {"read_only": True},
            "workflow_id": {"read_only": True},
        }


class CreateAutomationNodeSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the automation node",
    )

    class Meta:
        model = AutomationNode
        fields = ("id", "type")


class UpdateAutomationNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationNode
        fields = ("previous_node_output",)


class OrderAutomationNodesSerializer(serializers.Serializer):
    node_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text=("The ids of the nodes in the order they are supposed to be set in."),
    )
