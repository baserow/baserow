from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.workflows.constants import ALLOW_TEST_RUN_MINUTES
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler


class AutomationWorkflowSerializer(serializers.ModelSerializer):
    published_on = serializers.SerializerMethodField()
    disabled = serializers.SerializerMethodField()
    paused = serializers.SerializerMethodField()

    class Meta:
        model = AutomationWorkflow
        fields = (
            "id",
            "name",
            "order",
            "automation_id",
            "allow_test_run_until",
            "published_on",
            "disabled",
            "paused",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "automation_id": {"read_only": True},
            "published_on": {"read_only": True},
            "disabled": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_published_on(self, obj):
        published_workflow = AutomationWorkflowHandler().get_published_workflow(obj)
        return str(published_workflow.created_on) if published_workflow else None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_disabled(self, obj):
        published_workflow = AutomationWorkflowHandler().get_published_workflow(obj)
        return bool(published_workflow.disabled_on) if published_workflow else False

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_paused(self, obj):
        published_workflow = AutomationWorkflowHandler().get_published_workflow(obj)
        return published_workflow.paused if published_workflow else False


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
    paused = serializers.BooleanField(
        required=False,
        help_text="Whether the published workflow is currently paused.",
    )

    class Meta:
        model = AutomationWorkflow
        fields = ("name", "allow_test_run", "paused")
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
