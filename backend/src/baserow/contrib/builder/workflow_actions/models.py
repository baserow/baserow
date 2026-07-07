from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.contrib.builder.elements.models import Element, NavigationElementMixin
from baserow.contrib.builder.pages.models import Page
from baserow.core.formula.field import FormulaField
from baserow.core.mixins import OrderableMixin
from baserow.core.registry import ModelRegistryMixin
from baserow.core.services.models import Service
from baserow.core.workflow_actions.models import WorkflowAction


class EventTypes(models.TextChoices):
    CLICK = "click"
    SUBMIT = "submit"
    AFTER_LOGIN = "after_login"


class BuilderWorkflowActionManager(models.Manager):
    """
    By default, we will only return workflow
    actions associated with untrashed elements.
    """

    def get_queryset(self):
        # `exclude` rather than `filter(element__trashed=False)` so that
        # page-scoped actions, whose `element` is NULL, are still returned.
        # An `element__trashed=False` filter is an inner join that would
        # silently drop those NULL-element rows.
        return super().get_queryset().exclude(element__trashed=True)


class BuilderWorkflowAction(
    WorkflowAction,
    OrderableMixin,
):
    order = models.PositiveIntegerField()
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="builder_workflow_actions",
        on_delete=models.CASCADE,
    )
    event = models.CharField(
        max_length=60,
        help_text="The event that triggers the execution",
    )
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    element = models.ForeignKey(
        Element, on_delete=models.CASCADE, null=True, default=None
    )

    # The default manager hides actions whose element has been trashed. Use
    # `objects_including_trashed_elements` in the rare places that must operate on
    # those actions regardless of their element's trash state, such as cleaning them
    # up when the element is permanently deleted.
    objects = BuilderWorkflowActionManager()
    objects_including_trashed_elements = models.Manager()

    @classmethod
    def is_dynamic_event(cls, event: str) -> bool:
        """
        :return: Whether the given event is dynamically generated.
        """

        default_event_types = [e.value for e in EventTypes]
        return event and event not in default_event_types

    @staticmethod
    def get_type_registry() -> ModelRegistryMixin:
        from baserow.contrib.builder.workflow_actions.registries import (
            builder_workflow_action_type_registry,
        )

        return builder_workflow_action_type_registry

    def get_parent(self):
        return self.page

    @classmethod
    def get_last_order_element_scope(cls, element: Element):
        queryset = BuilderWorkflowAction.objects.filter(element=element)
        return cls.get_highest_order_of_queryset(queryset) + 1

    @classmethod
    def get_last_order_page_scope(cls, page: Page):
        queryset = BuilderWorkflowAction.objects.filter(page=page, element=None)
        return cls.get_highest_order_of_queryset(queryset) + 1

    class Meta:
        ordering = ("order", "id")


class NotificationWorkflowAction(BuilderWorkflowAction):
    title = FormulaField(default="")
    description = FormulaField(default="")


class OpenPageWorkflowAction(BuilderWorkflowAction, NavigationElementMixin):
    pass


class LogoutWorkflowAction(BuilderWorkflowAction):
    pass


class RefreshDataSourceWorkflowAction(BuilderWorkflowAction):
    data_source = models.ForeignKey(
        "builder.DataSource",
        null=True,
        on_delete=models.SET_NULL,
        help_text="The data source we want to refresh for this action.",
    )


class BuilderWorkflowServiceAction(BuilderWorkflowAction):
    service = models.ForeignKey(
        Service,
        help_text="The service which this action is associated with.",
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True


class LocalBaserowCreateRowWorkflowAction(BuilderWorkflowServiceAction): ...


class LocalBaserowCreateRowsWorkflowAction(BuilderWorkflowServiceAction): ...


class LocalBaserowUpdateRowWorkflowAction(BuilderWorkflowServiceAction): ...


class LocalBaserowUpdateRowsWorkflowAction(BuilderWorkflowServiceAction): ...


class LocalBaserowDeleteRowWorkflowAction(BuilderWorkflowServiceAction): ...


class CoreHTTPRequestWorkflowAction(BuilderWorkflowServiceAction): ...


class CoreSMTPEmailWorkflowAction(BuilderWorkflowServiceAction): ...


class CoreCSVFileReaderWorkflowAction(BuilderWorkflowServiceAction): ...


class CoreStartWorkflowWorkflowAction(BuilderWorkflowServiceAction): ...


class AIAgentWorkflowAction(BuilderWorkflowServiceAction): ...


class SlackWriteMessageWorkflowAction(BuilderWorkflowServiceAction): ...
