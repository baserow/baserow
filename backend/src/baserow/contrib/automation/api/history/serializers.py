from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
)


class AutomationNodeHistorySerializer(serializers.ModelSerializer):
    """
    The AutomationNodeHistory serializer.

    The result field is intentionally excluded for performance reasons; it is
    fetched on demand from the frontend.
    """

    node_type = serializers.SerializerMethodField()
    node_label = serializers.SerializerMethodField()
    parent_node_id = serializers.SerializerMethodField()
    iteration = serializers.SerializerMethodField()
    iteration_path = serializers.SerializerMethodField()
    is_container = serializers.SerializerMethodField()
    has_error_descendant = serializers.SerializerMethodField()

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
            "is_container",
            "has_error_descendant",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_node_type(self, obj):
        return obj.node.get_type().type

    @extend_schema_field(OpenApiTypes.STR)
    def get_node_label(self, obj):
        return obj.node.label

    @extend_schema_field(OpenApiTypes.INT)
    def get_parent_node_id(self, obj):
        parent_map = self.context.get("parent_map", {})
        return parent_map.get(obj.node_id)

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

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_container(self, obj):
        return obj.node.get_type().is_container

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_error_descendant(self, obj):
        return obj.node_id in self.context["error_ancestor_ids"]


class NodeHistoriesQueryParamsSerializer(serializers.Serializer):
    parent_node_id = serializers.IntegerField(required=False, allow_null=True)
    iteration_path = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "When provided, only node histories whose iteration_path starts "
            "with iteration_path are returned."
        ),
    )


class AutomationNodeResultSerializer(serializers.ModelSerializer):
    """
    Serializer for the AutomationNodeResult's result field.
    """

    class Meta:
        model = AutomationNodeResult
        fields = ("result",)
