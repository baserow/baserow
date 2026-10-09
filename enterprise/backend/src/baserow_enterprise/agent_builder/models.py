from django.db import models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
)
from baserow.core.models import Application


class AgentBuilder(Application):
    def get_parent(self):
        self.application_ptr.workspace = self.workspace
        return self.application_ptr


class AgentDefinitionTrashManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .exclude(
                models.Q(trashed=True)
                | models.Q(agent_builder__trashed=True)
                | models.Q(agent_builder__workspace__trashed=True)
            )
        )


class AgentDefinition(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
):
    """An empty reusable agent definition awaiting configuration and execution."""

    agent_builder = models.ForeignKey(
        AgentBuilder, on_delete=models.CASCADE, related_name="agents"
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    objects = AgentDefinitionTrashManager()
    objects_and_trash = models.Manager()

    class Meta:
        ordering = ("order", "id")

    def get_parent(self):
        return self.agent_builder

    @classmethod
    def get_last_order(cls, agent_builder: AgentBuilder):
        return (
            cls.get_highest_order_of_queryset(
                cls.objects_and_trash.filter(agent_builder=agent_builder)
            )
            + 1
        )
