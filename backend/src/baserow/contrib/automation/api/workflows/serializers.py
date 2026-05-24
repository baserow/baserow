from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.pagination import PageNumberPagination
from baserow.contrib.automation.models import (
    AutomationHistory,
    AutomationNodeHistory,
    AutomationWorkflow,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.workflows.constants import (
    ALLOW_TEST_RUN_MINUTES,
    WorkflowState,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


class AutomationWorkflowSerializer(serializers.ModelSerializer):
    published_on = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    notification_recipient_ids = serializers.SerializerMethodField()

    class Meta:
        model = AutomationWorkflow
        fields = (
            "id",
            "name",
            "order",
            "automation_id",
            "allow_test_run_until",
            "simulate_until_node_id",
            "published_on",
            "state",
            "graph",
            "notification_recipient_ids",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "automation_id": {"read_only": True},
            "published_on": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_published_on(self, obj):
        published_workflow = AutomationWorkflowHandler().get_published_workflow(obj)
        return str(published_workflow.created_on) if published_workflow else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_state(self, obj):
        published_workflow = AutomationWorkflowHandler().get_published_workflow(obj)
        return published_workflow.state if published_workflow else WorkflowState.DRAFT

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_notification_recipient_ids(self, obj):
        """
        Use the prefetched recipients.
        """

        return sorted((recipient.id for recipient in obj.notification_recipients.all()))


class CreateAutomationWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflow
        fields = ("name",)


class UpdateAutomationWorkflowSerializer(serializers.ModelSerializer):
    allow_test_run = serializers.BooleanField(
        required=False,
        help_text=(
            "If provided, enables the workflow to be triggerable for the next "
            f"{ALLOW_TEST_RUN_MINUTES} minutes."
        ),
    )
    notification_recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text=(
            "The user IDs of the workspace members that should receive "
            "notifications related to this workflow."
        ),
    )

    class Meta:
        model = AutomationWorkflow
        fields = (
            "name",
            "allow_test_run",
            "state",
            "notification_recipient_ids",
        )
        extra_kwargs = {
            "name": {"required": False},
        }


class OrderAutomationWorkflowsSerializer(serializers.Serializer):
    workflow_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text=(
            "The ids of the workflows in the order they are supposed to be set in."
        ),
    )


class AutomationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationHistory
        fields = (
            "id",
            "started_on",
            "completed_on",
            "message",
            "status",
        )


class AutomationNodeHistorySerializer(AutomationHistorySerializer):
    parent_node_id = serializers.SerializerMethodField()
    iteration = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()
    node_type = serializers.SerializerMethodField()
    node_label = serializers.SerializerMethodField()

    class Meta:
        model = AutomationNodeHistory
        fields = AutomationHistorySerializer.Meta.fields + (
            "workflow_history",
            "node",
            "node_type",
            "node_label",
            "parent_node_id",
            "iteration",
            "result",
        )

    def _get_first_node_result(self, obj):
        results = obj.node_results.all()
        return results[0] if results else None

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

    @extend_schema_field(OpenApiTypes.INT)
    def get_iteration(self, obj):
        result = self._get_first_node_result(obj)
        if result is None:
            return None

        if result.iteration_path:
            return int(result.iteration_path.rsplit(".", 1)[-1])

        return 0

    def get_result(self, obj):
        result = self._get_first_node_result(obj)
        return result.result if result else {}


class AutomationWorkflowHistorySerializer(AutomationHistorySerializer):
    node_histories = AutomationNodeHistorySerializer(read_only=True, many=True)

    class Meta:
        model = AutomationWorkflowHistory
        fields = AutomationHistorySerializer.Meta.fields + (
            "is_test_run",
            "event_payload",
            "simulate_until_node",
            "node_histories",
        )


class AutomationWorkflowHistoryPagination(PageNumberPagination):
    def get_paginated_response(self, data, *, success_count: int, fail_count: int):
        response = super().get_paginated_response(data)
        response.data["success_count"] = success_count
        response.data["fail_count"] = fail_count
        return response
