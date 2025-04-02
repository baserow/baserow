from rest_framework import serializers

from baserow.contrib.automation.models import AutomationWorkflow


class CreateAutomationWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationWorkflow
        fields = ("name",)


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
