from typing import List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
)
from baserow.contrib.automation.models import Automation


class AutomationSerializer(serializers.ModelSerializer):
    """
    The Automation serializer.
    """

    workflows = serializers.SerializerMethodField(
        help_text="This field is specific to the `automation` application and "
        "contains an array of workflows that are in the automation."
    )

    class Meta:
        model = Automation
        ref_name = "AutomationApplication"
        fields = ("id", "name", "workflows")

    @extend_schema_field(AutomationWorkflowSerializer(many=True))
    def get_workflows(self, instance: Automation) -> List:
        return AutomationWorkflowSerializer(instance.workflows, many=True).data
