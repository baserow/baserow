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
    payload = serializers.SerializerMethodField()

    class Meta:
        model = AutomationNodeHistory
        fields = AutomationHistorySerializer.Meta.fields + (
            "workflow_history",
            "node",
            "parent_node_id",
            "iteration",
            "payload",
        )

    @extend_schema_field(OpenApiTypes.INT)
    def get_parent_node_id(self, obj):
        parent_nodes = obj.node.get_parent_nodes()
        if not parent_nodes:
            return None
        return parent_nodes[-1].id

    @extend_schema_field(OpenApiTypes.INT)
    def get_iteration(self, obj):
        result = obj.node_results.first()
        return result.iteration if result else None

    def get_payload(self, obj):
        # TODO: optimize the n+1 queries
        previous_node = (
            obj.node.get_previous_nodes()[-1] if obj.node.get_previous_nodes() else None
        )

        # if trigger, return the workflow's event_payload
        if not previous_node:
            # TODO: for periodic trigger, there is no payload. Maybe we should return
            # the sample data?
            return obj.workflow_history.event_payload

        # if node, return previous node's result
        prev_node_history = previous_node.node_histories.filter(
            workflow_history=obj.workflow_history
        ).first()
        if not prev_node_history:
            return {}

        current_result = obj.node_results.first()
        current_iteration = current_result.iteration if current_result else 0

        prev_result = prev_node_history.node_results.filter(
            iteration=current_iteration
        ).first()
        return prev_result.result if prev_result else {}


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
