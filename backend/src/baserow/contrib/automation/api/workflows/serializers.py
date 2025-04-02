from rest_framework import serializers

from baserow.contrib.automation.models import AutomationWorkflow


class AutomationWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflow
        fields = (
            "id",
            "name",
            "order",
            "automation_id",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "automation_id": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }


class CreateAutomationWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflow
        fields = ("name",)


class UpdateAutomationWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflow
        fields = ("name",)
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
