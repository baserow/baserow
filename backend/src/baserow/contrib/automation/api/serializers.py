from typing import TYPE_CHECKING, List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
)

if TYPE_CHECKING:
    from baserow.contrib.automation.application_types import AutomationApplicationType


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

        workflows = getattr(instance, "workflows", None)
        if workflows is None:
            ctx = self.context
            user = ctx.get("user", None)
            request = ctx.get("request")
            if user is None and hasattr(request, "user"):
                user = request.user if request.user.is_authenticated else None

            automation_type: "AutomationApplicationType" = instance.get_type()
            workflows = automation_type.fetch_workflows_to_serialize(instance, user)

        return AutomationWorkflowSerializer(workflows, many=True).data
