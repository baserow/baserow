from typing import TYPE_CHECKING

from django.db import models

from baserow.contrib.automation.constants import WORKFLOW_NAME_MAX_LEN
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.core.cache import local_cache
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
    WithRegistry,
)

if TYPE_CHECKING:
    from baserow.contrib.automation.models import Automation
    from baserow.contrib.automation.nodes.models import AutomationTriggerNode


class AutomationWorkflowTrashManager(models.Manager):
    """
    Manager for the AutomationWorkflow model.

    Ensure all trashed relations are excluded from the default queryset.
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(
                models.Q(trashed=True)
                | models.Q(automation__trashed=True)
                | models.Q(automation__workspace__trashed=True)
            )
        )


class AutomationWorkflow(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    WithRegistry,
):
    automation = models.ForeignKey(
        "automation.Automation", on_delete=models.CASCADE, related_name="workflows"
    )
    simulate_until_node = models.ForeignKey(
        "automation.AutomationNode",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=(
            "When set, upon the next workflow run, simulates the dispatch of "
            "the workflow until this node and updates the sample_data of the "
            "node's service."
        ),
    )

    name = models.CharField(max_length=WORKFLOW_NAME_MAX_LEN)
    state = models.CharField(
        choices=WorkflowState.choices,
        default=WorkflowState.DRAFT,
        db_default=WorkflowState.DRAFT,
        max_length=20,
    )

    order = models.PositiveIntegerField()

    allow_test_run_until = models.DateTimeField(null=True, blank=True)

    graph = models.JSONField(default=dict, help_text="Contains the node graph.")

    objects = AutomationWorkflowTrashManager()
    objects_and_trash = models.Manager()

    class Meta:
        ordering = ("order",)
        unique_together = [["automation", "name"]]

    def get_parent(self):
        return self.automation

    @classmethod
    def get_last_order(cls, automation: "Automation"):
        queryset = AutomationWorkflow.objects.filter(automation=automation)
        return cls.get_highest_order_of_queryset(queryset) + 1

    def get_trigger(self) -> "AutomationTriggerNode":
        """
        Returns the first node of the workflow A.K.A the trigger.
        """

        return self.get_graph().get_node_at_position(None, "south", "")

    def can_immediately_be_tested(self):
        """
        True of the workflow trigger can immediately be dispatched in test mode.
        """

        service = self.get_trigger().service.specific
        return service.get_type().can_immediately_be_tested(service)

    def get_graph(self):
        """
        Returns the workflow graph. Use the same graph instance related to the workflow
        ID regardless of the workflow instance.
        """

        from .graph_handler import NodeGraphHandler

        # always return the same instance to avoid using different graphs from different
        # instances of the same workflow

        return local_cache.get(
            f"automation_workflow__{self.id}",
            lambda: NodeGraphHandler(self),
        )

    @property
    def is_published(self) -> bool:
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )

        workflow = self
        if published_workflow := AutomationWorkflowHandler().get_published_workflow(
            self
        ):
            workflow = published_workflow

        return workflow.state == WorkflowState.LIVE

    def print(self, message=None, original=False):
        """
        Prints the graph in a pretty way. Useful for debug.
        """

        import pprint

        if message:
            print(message)

        if original:
            pprint.pprint(self.get_graph().graph, indent=2)
        else:
            pprint.pprint(self.get_graph().labeled_graph(), indent=2)

    def assert_reference(self, reference):
        """
        Used in test, compare the current workflow graph with the given reference and
        raise an error if the graph doesn't match.
        """

        import pprint

        try:
            assert (
                self.get_graph().labeled_graph() == reference  # nosec B101
            ), "Failed to match the reference."
        except AssertionError:
            print("Failed to match the reference:")
            pprint.pprint(reference, indent=2)
            self.print("Current graph:")
            raise


class DuplicateAutomationWorkflowJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_automation_workflow = models.ForeignKey(
        AutomationWorkflow,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The automation workflow to duplicate.",
    )

    duplicated_automation_workflow = models.OneToOneField(
        AutomationWorkflow,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated automation workflow.",
    )


class PublishAutomationWorkflowJob(JobWithUserIpAddress, Job):
    automation_workflow = models.ForeignKey(
        AutomationWorkflow,
        null=True,
        on_delete=models.SET_NULL,
    )
