from decimal import Decimal
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Manager, QuerySet

from baserow.contrib.automation.workflows.models import (
    AutomationWorkflow,
    DuplicateAutomationWorkflowJob,
)
from baserow.core.db import get_unique_orders_before_item
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
    "LocalBaserowUpdateRowActionNode",
    "LocalBaserowDeleteRowActionNode",
    "CoreSMTPEmailActionNode",
]


def get_default_node_content_type():
    return ContentType.objects.get_for_model(AutomationNode)


class AutomationNodeTrashManager(models.Manager):
    """
    Manager for the AutomationNode model.

    Ensure all trashed relations are excluded from the default queryset.
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(
                models.Q(trashed=True)
                | models.Q(workflow__trashed=True)
                | models.Q(workflow__automation__trashed=True)
                | models.Q(workflow__automation__workspace__trashed=True)
            )
        )


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

    objects = AutomationNodeTrashManager()
    objects_and_trash = Manager()

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

    @classmethod
    def get_unique_order_before_node(
        cls, before: "AutomationNode", parent_node_id: Optional[int]
    ) -> Decimal:
        """
        Returns a safe order value before the given node in the given workflow.

        :param before: The node before which we want the safe order
        :param parent_node_id: The id of the parent node.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: The order value.
        """

        queryset = AutomationNode.objects.filter(workflow=before.workflow).filter(
            parent_node_id=parent_node_id
        )

        return cls.get_unique_orders_before_item(before, queryset)[0]

    @classmethod
    def get_unique_orders_before_item(
        cls,
        before: Optional[models.Model],
        queryset: QuerySet,
        amount: int = 1,
        field: str = "order",
    ) -> List[Decimal]:
        """
        Calculates a list of unique decimal orders that can safely be used before the
        provided `before` item.

        :param before: The model instance where the before orders must be
            calculated for.
        :param queryset: The base queryset used to compute the value.
        :param amount: The number of orders that must be requested. Can be higher if
            multiple items are inserted or moved.
        :param field: The order field name.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: A list of decimals containing safe to use orders in order.
        """

        return get_unique_orders_before_item(before, queryset, amount, field=field)


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


class LocalBaserowUpdateRowActionNode(AutomationActionNode):
    ...


class LocalBaserowDeleteRowActionNode(AutomationActionNode):
    ...


class LocalBaserowGetRowActionNode(AutomationActionNode):
    ...


class LocalBaserowListRowsActionNode(AutomationActionNode):
    ...


class LocalBaserowAggregateRowsActionNode(AutomationActionNode):
    ...


class CoreHTTPRequestActionNode(AutomationActionNode):
    ...


class CoreSMTPEmailActionNode(AutomationActionNode):
    ...
