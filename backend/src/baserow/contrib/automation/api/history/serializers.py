from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
)


class AutomationNodeHistorySerializer(serializers.ModelSerializer):
    node_type = serializers.SerializerMethodField()
    node_label = serializers.SerializerMethodField()
    parent_node_id = serializers.SerializerMethodField()
    iteration = serializers.SerializerMethodField()
    iteration_path = serializers.SerializerMethodField()
    edge_label = serializers.SerializerMethodField()

    class Meta:
        model = AutomationNodeHistory
        fields = (
            "id",
            "started_on",
            "completed_on",
            "message",
            "status",
            "workflow_history",
            "node",
            "node_type",
            "node_label",
            "parent_node_id",
            "iteration",
            "iteration_path",
            "edge_label",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_node_type(self, obj):
        return obj.node.get_type().type

    @extend_schema_field(OpenApiTypes.STR)
    def get_node_label(self, obj):
        return obj.node.label

    @extend_schema_field(OpenApiTypes.INT)
    def get_parent_node_id(self, obj):
        parent_nodes = obj.node.get_parent_nodes()
        if not parent_nodes:
            return None
        return parent_nodes[-1].id

    def _get_first_node_result(self, obj):
        results = obj.node_results.all()
        return results[0] if results else None

    @extend_schema_field(OpenApiTypes.INT)
    def get_iteration(self, obj):
        result = self._get_first_node_result(obj)
        if result is None:
            return None
        if result.iteration_path:
            return int(result.iteration_path.rsplit(".", 1)[-1])
        return 0

    @extend_schema_field(OpenApiTypes.STR)
    def get_iteration_path(self, obj):
        result = self._get_first_node_result(obj)
        return result.iteration_path if result else ""

    @extend_schema_field(OpenApiTypes.STR)
    def get_edge_label(self, obj):
        return self.context.get("edge_labels", {}).get(obj.id, "")


class AutomationNodeResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationNodeResult
        fields = ("result",)
