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


class LocalBaserowCreateRowWorkflowAction(BuilderWorkflowServiceAction):
    ...


class LocalBaserowUpdateRowWorkflowAction(BuilderWorkflowServiceAction):
    ...


class LocalBaserowDeleteRowWorkflowAction(BuilderWorkflowServiceAction):
    ...


class CoreHTTPRequestWorkflowAction(BuilderWorkflowServiceAction):
    ...


class CoreSMTPEmailWorkflowAction(BuilderWorkflowServiceAction):
    ...


class AIAgentWorkflowAction(BuilderWorkflowServiceAction):
    ...


class SlackWriteMessageWorkflowAction(BuilderWorkflowServiceAction):
    ...
