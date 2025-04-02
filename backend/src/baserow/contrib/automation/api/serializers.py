from typing import List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.operations import ListAutomationWorkflowsOperationType
from baserow.contrib.automation.workflows.serializers import (
    AutomationWorkflowSerializer,
)
from baserow.core.handler import CoreHandler


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
        """
        Because the instance doesn't know at this point that it is an Automation
        instance, we have to select the related workflows this way.

        :param instance: The Automation application instance.
        :return: A list of serialized workflows that belong to this instance.
        """

        workflows = instance.workflows.all()
        user = self.context.get("user")
        request = self.context.get("request")

        if user is None and hasattr(request, "user"):
            user = request.user

        if user:
            workflows = CoreHandler().filter_queryset(
                user,
                ListAutomationWorkflowsOperationType.type,
                workflows,
                workspace=instance.workspace,
            )

        return AutomationWorkflowSerializer(workflows, many=True).data
