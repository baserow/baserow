from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import OuterRef

from baserow.contrib.database.fields.models import ButtonField
from baserow.core.formula.field import FormulaField as CoreFormulaModelField
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import OrderableMixin
from baserow.core.registry import ModelRegistryMixin
from baserow.core.services.models import Service
from baserow.core.workflow_actions.models import WorkflowAction


class DatabaseWorkflowAction(WorkflowAction, OrderableMixin):
    """
    An action in a button field's ordered list, run when a user clicks the
    button. Mirrors `BuilderWorkflowAction`, with the button field taking the
    place of the builder's page and element.
    """

    order = models.PositiveIntegerField()

    # Overrides `TrashableModelMixin.trashed` solely to add `db_default` so the
    # column keeps a database-level default (mirrors `BuilderWorkflowAction`).
    trashed = models.BooleanField(default=False, db_default=False, db_index=True)
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="database_workflow_actions",
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        ButtonField,
        on_delete=models.CASCADE,
        related_name="workflow_actions",
        help_text="The button field this action belongs to.",
    )

    @staticmethod
    def get_type_registry() -> ModelRegistryMixin:
        from baserow.contrib.database.workflow_actions.registries import (
            database_workflow_action_type_registry,
        )

        return database_workflow_action_type_registry

    def get_parent(self):
        return self.field

    @classmethod
    def get_last_order(cls, field: ButtonField) -> int:
        queryset = DatabaseWorkflowAction.objects.filter(field=field)
        return cls.get_highest_order_of_queryset(queryset) + 1

    class Meta:
        ordering = ("order", "id")


class DatabaseWorkflowServiceAction(DatabaseWorkflowAction):
    """
    Base for actions backed by a `Service`. Kept separate from
    `DatabaseWorkflowAction` (ADR 006 section 2) so frontend-only action
    types, such as a client-side toast, can be added later without a schema
    migration.
    """

    service = models.ForeignKey(
        Service,
        help_text="The service which this action is associated with.",
        on_delete=models.CASCADE,
        # The builder has models of these exact names pointing at `Service`, so
        # the default reverse accessor would clash with theirs.
        related_name="%(app_label)s_%(class)s_set",
    )

    # Set by `annotate_actions_requiring_reconfiguration` when a field's actions
    # are listed, so the flag costs no query per action there.
    REQUIRES_RECONFIGURATION_ANNOTATION = "requires_reconfiguration_annotated"

    @property
    def requires_reconfiguration(self) -> bool:
        annotated = getattr(self, self.REQUIRES_RECONFIGURATION_ANNOTATION, None)
        if annotated is not None:
            return annotated

        # Imported here: the reconfiguration module imports this one.
        from baserow.contrib.database.workflow_actions.reconfiguration import (
            action_requires_reconfiguration,
        )

        return DatabaseWorkflowAction.objects.filter(
            action_requires_reconfiguration(OuterRef("pk")), pk=self.pk
        ).exists()

    class Meta:
        abstract = True


class OpenUrlWorkflowAction(DatabaseWorkflowAction):
    """
    Opens a URL in the browser. Frontend-only: it is never dispatched server
    side, so it subclasses the base rather than `DatabaseWorkflowServiceAction`
    and carries no `Service` (ADR 006 section 2).
    """

    url = CoreFormulaModelField(default="", db_default="")
    target = models.CharField(
        max_length=10,
        choices=[("self", "Same tab"), ("blank", "New tab")],
        default="self",
        db_default="self",
        help_text="Whether the URL opens in the same tab or a new one.",
    )


class LocalBaserowCreateRowWorkflowAction(DatabaseWorkflowServiceAction): ...


class LocalBaserowUpdateRowWorkflowAction(DatabaseWorkflowServiceAction): ...


class LocalBaserowDeleteRowWorkflowAction(DatabaseWorkflowServiceAction): ...


class CoreHTTPRequestWorkflowAction(DatabaseWorkflowServiceAction): ...


class CoreSMTPEmailWorkflowAction(DatabaseWorkflowServiceAction): ...


class SlackWriteMessageWorkflowAction(DatabaseWorkflowServiceAction): ...


class CoreStartWorkflowWorkflowAction(DatabaseWorkflowServiceAction): ...


class ButtonFieldDispatchJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    """
    One button click that runs behind the request, because an action of it
    reaches outside Baserow. Carries what the click produced once it ran, in
    the shape the inline response has.
    """

    # Set null rather than cascaded: changing the field's type deletes the
    # button row, and a job deleted under its worker could not report back.
    field = models.ForeignKey(
        "database.ButtonField",
        null=True,
        on_delete=models.SET_NULL,
        related_name="dispatch_jobs",
        help_text="The clicked button field. Empty once it is no longer a button.",
    )
    row_id = models.PositiveIntegerField(help_text="The clicked row.")
    workflow_action_ids = models.JSONField(
        default=list,
        help_text="The ids of the actions the click was accepted with, in order. "
        "The job refuses to run a list that differs from it.",
    )
    results = models.JSONField(
        null=True,
        help_text="One result per server action that ran, once the click finished.",
    )
    client_actions = models.JSONField(
        null=True,
        help_text="The frontend-only actions the browser runs after the click.",
    )
