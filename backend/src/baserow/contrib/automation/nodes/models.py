from typing import Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Manager

from baserow.contrib.automation.workflows.models import AutomationWorkflow
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

    def get_parent(self):
        return self.workflow

    def get_label(self):
        if self.label:
            return self.label
        else:
            return self.get_type().type

    def get_previous_nodes(self):
        """
        Returns the nodes before the current node. A previous node can be a
        `previous node` or a `parent node`.
        """

        return [
            position[0]
            for position in self.workflow.get_graph().get_previous_positions(self)
        ]

    def get_previous_service_outputs(self):
        """
        Returns the list of edge UIDs to choose to get to this node from the first node.
        """

        previous_positions = self.workflow.get_graph().get_previous_positions(self)

        return {node.service_id: str(out) for [node, _, out] in previous_positions}

    def get_parent_nodes(self):
        """
        Returns the ancestors of this node which are the container nodes that contain
        the current node instance.
        """

        return [
            position[0]
            for position in self.workflow.get_graph().get_previous_positions(self)
            if position[1] == "child"
        ]

    def get_next_nodes(
        self, output_uid: str | None = None
    ) -> Iterable["AutomationNode"]:
        """
        Returns all nodes which directly follow this node in the workflow.
        A list of nodes is returned as there can be multiple nodes that follow this one,
        for example when there are multiple branches in the workflow.

        :param output_uid: filter nodes only for this output uid.
        """

        return self.workflow.get_graph().get_next_nodes(self, output_uid)

    def get_children(self):
        """
        Returns the direct children of this node if any.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        return AutomationNodeHandler().get_children(self)


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


class CorePeriodicTriggerNode(AutomationTriggerNode):
    ...


class CoreHTTPTriggerNode(AutomationTriggerNode):
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


class CoreRouterActionNode(AutomationActionNode):
    ...


class CoreIteratorActionNode(AutomationActionNode):
    ...


class AIAgentActionNode(AutomationActionNode):
    ...


class SlackWriteMessageActionNode(AutomationActionNode):
    ...
