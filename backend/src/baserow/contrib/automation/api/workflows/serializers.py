from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.models import (
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

    class Meta:
        model = AutomationWorkflow
        fields = ("name", "allow_test_run", "state")
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


class AutomationWorkflowHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflowHistory
        fields = (
            "id",
            "started_on",
            "completed_on",
            "is_test_run",
            "message",
            "status",
        )
