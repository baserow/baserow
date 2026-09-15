from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from baserow.contrib.automation.constants import WORKFLOW_NAME_MAX_LEN
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.core.cache import local_cache
from baserow.core.graph.models import GraphModelMixin
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
    GraphModelMixin,
):
    supports_edges = True

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

    notification_recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="automation_notification_workflows",
        help_text=(
            "The workspace users that should receive notifications related to "
            "this workflow."
        ),
    )

    objects = AutomationWorkflowTrashManager()
    objects_and_trash = models.Manager()

    class Meta:
        ordering = ("order",)

    def get_parent(self):
        return self.automation

    @classmethod
    def get_last_order(cls, automation: "Automation"):
        queryset = AutomationWorkflow.objects.filter(automation=automation)
        return cls.get_highest_order_of_queryset(queryset) + 1

    def is_original(self) -> bool:
        """
        Whether this is an original workflow.
        """

        return not bool(self.automation.published_from_id)

    def get_original(self) -> "AutomationWorkflow":
        """
        Gets the original workflow related to the current instance.

        :return: The original workflow that can be the current instance.
        """

        from .handler import AutomationWorkflowHandler

        return local_cache.get(
            f"automation_workflow_original_{self.id}",
            lambda: (
                AutomationWorkflowHandler().get_workflow(
                    self.automation.published_from_id
                )
                if self.automation.published_from_id
                else self
            ),
        )

    def get_graph_handler(self):
        from baserow.contrib.automation.workflows.graph_handler import (
            AutomationWorkflowGraphHandler,
        )

        return AutomationWorkflowGraphHandler

    def get_trigger(self) -> "AutomationTriggerNode":
        """
        Returns the first node of the workflow A.K.A the trigger.
        """

        return self.get_graph().get_point_at_position(None, "south", "")

    def can_be_immediately_dispatched(self):
        """
        True if the workflow trigger can dispatch without waiting for an event.
        """

        trigger = self.get_trigger()
        if trigger is None:
            return False

        service = trigger.service.specific
        return service.get_type().can_be_immediately_dispatched(service)

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
