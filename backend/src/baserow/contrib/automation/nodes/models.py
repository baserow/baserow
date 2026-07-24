from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Manager

from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.graph.models import GraphPointMixin
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.services.models import Service


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
    GraphPointMixin,
    WithRegistry,
):
    """
    This model represents an Automation Workflow's Node.

    The Node is the basic constituent of a workflow. Each workflow will
    typically have a Trigger Node and one or more Action Nodes.
    """

    label = models.CharField(
        blank=True,
        default="",
        db_default="",
        max_length=75,
        help_text="A label to use when displaying this node in a graph.",
    )
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
    service = models.OneToOneField(
        Service,
        help_text="The service which this node is associated with.",
        related_name="automation_workflow_node",
        on_delete=models.CASCADE,
    )

    objects = AutomationNodeTrashManager()
    objects_and_trash = Manager()

    class Meta:
        ordering = ("id",)

    @staticmethod
    def get_type_registry():
        from baserow.contrib.automation.nodes.registries import (
            automation_node_type_registry,
        )

        return automation_node_type_registry

    def __str__(self):
        return str(self.get_type().display_name)

    def get_parent(self):
        return self.workflow

    def get_previous_service_outputs(self):
        """
        Returns the list of edge UIDs to choose to get to this node from the first node.
        """

        previous_positions = self.workflow.get_graph().get_previous_positions(self)

        return {node.service_id: str(out) for [node, _, out] in previous_positions}

    def get_children(self, first_only: bool = False):
        """
        Returns the children of this node if any.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        return AutomationNodeHandler().get_children(self, first_only=first_only)

    def graph_point_edge_label(self, uid: str) -> str:
        edges = self.service.get_type().get_edges(self.service.specific)
        return edges[uid]["label"]


class AutomationActionNode(AutomationNode):
    class Meta:
        abstract = True


class AutomationTriggerNode(AutomationNode):
    class Meta:
        abstract = True


class LocalBaserowRowsCreatedTriggerNode(AutomationTriggerNode): ...


class LocalBaserowRowsUpdatedTriggerNode(AutomationTriggerNode): ...


class LocalBaserowRowsDeletedTriggerNode(AutomationTriggerNode): ...


class LocalBaserowFieldsUpdatedTriggerNode(AutomationTriggerNode): ...


class CorePeriodicTriggerNode(AutomationTriggerNode): ...


class CoreHTTPTriggerNode(AutomationTriggerNode): ...


class CoreManualTriggerNode(AutomationTriggerNode): ...


class LocalBaserowCreateRowActionNode(AutomationActionNode): ...


class LocalBaserowCreateRowsActionNode(AutomationActionNode): ...


class LocalBaserowUpdateRowsActionNode(AutomationActionNode): ...


class LocalBaserowUpdateRowActionNode(AutomationActionNode): ...


class LocalBaserowDeleteRowActionNode(AutomationActionNode): ...


class LocalBaserowGetRowActionNode(AutomationActionNode): ...


class LocalBaserowListRowsActionNode(AutomationActionNode): ...


class LocalBaserowAggregateRowsActionNode(AutomationActionNode): ...


class CoreHTTPRequestActionNode(AutomationActionNode): ...


class CoreSMTPEmailActionNode(AutomationActionNode): ...


class CoreRouterActionNode(AutomationActionNode): ...


class CoreGotoActionNode(AutomationActionNode): ...


class CoreIteratorActionNode(AutomationActionNode): ...


class CoreCSVFileReaderActionNode(AutomationActionNode): ...


class CoreStartWorkflowActionNode(AutomationActionNode): ...


class AIAgentActionNode(AutomationActionNode): ...


class SlackWriteMessageActionNode(AutomationActionNode): ...
