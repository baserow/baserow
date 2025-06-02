from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.contrib.automation.workflows.models import (
    AutomationWorkflow,
    DuplicateAutomationWorkflowJob,
)
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.services.models import Service

__all__ = [
    "AutomationNode",
    "AutomationWorkflow",
    "DuplicateAutomationWorkflowJob",
    "LocalBaserowRowsCreatedTriggerNode",
    "LocalBaserowRowsUpdatedTriggerNode",
    "LocalBaserowRowsDeletedTriggerNode",
    "LocalBaserowCreateRowActionNode",
]


def get_default_node_content_type():
    return ContentType.objects.get_for_model(AutomationNode)


class AutomationNode(
    TrashableModelMixin,
    PolymorphicContentTypeMixin,
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    FractionOrderableMixin,
    WithRegistry,
):
    """
    This model represents an Automation Workflow's Node.

    The Node is the basic constituent of a workflow. Each workflow will
    typically have a Trigger Node and one or more Action Nodes.
    """

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="automation_workflow_node_content_types",
        on_delete=models.SET(get_default_node_content_type),
    )
    workflow = models.ForeignKey(
        AutomationWorkflow,
        on_delete=models.CASCADE,
        related_name="automation_workflow_nodes",
    )
    parent_node = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The parent automation node.",
        related_name="automation_workflow_child_nodes",
    )
    previous_node = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The previous automation node.",
        related_name="automation_workflow_previous_nodes",
    )
    service = models.OneToOneField(
        Service,
        help_text="The service which this node is associated with.",
        related_name="automation_workflow_node",
        on_delete=models.CASCADE,
    )
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=1,
    )

    previous_node_output = models.CharField(default="")

    class Meta:
        ordering = ("order", "id")

    @staticmethod
    def get_type_registry():
        from baserow.contrib.automation.nodes.registries import (
            automation_node_type_registry,
        )

        return automation_node_type_registry

    def get_parent(self):
        return self.workflow

    @classmethod
    def get_last_order(cls, workflow: "AutomationWorkflow"):
        queryset = AutomationNode.objects.filter(workflow=workflow)
        return cls.get_highest_order_of_queryset(queryset)[0]


class AutomationActionNode(AutomationNode):
    class Meta:
        abstract = True


class AutomationTriggerNode(AutomationNode):
    class Meta:
        abstract = True


class LocalBaserowRowsCreatedTriggerNode(AutomationTriggerNode):
    ...


class LocalBaserowRowsUpdatedTriggerNode(AutomationTriggerNode):
    ...


class LocalBaserowRowsDeletedTriggerNode(AutomationTriggerNode):
    ...


class LocalBaserowCreateRowActionNode(AutomationActionNode):
    ...
