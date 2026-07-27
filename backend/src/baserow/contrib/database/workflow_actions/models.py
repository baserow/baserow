from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.contrib.database.fields.models import ButtonField
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
    )

    class Meta:
        abstract = True


class CreateRowWorkflowAction(DatabaseWorkflowServiceAction): ...


class UpdateRowWorkflowAction(DatabaseWorkflowServiceAction): ...


class DeleteRowWorkflowAction(DatabaseWorkflowServiceAction): ...
