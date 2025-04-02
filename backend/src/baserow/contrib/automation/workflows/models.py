import typing

from django.db import models

from baserow.contrib.automation.constants import WORKFLOW_NAME_MAX_LEN
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
)

if typing.TYPE_CHECKING:
    from baserow.contrib.automation.models import Automation


class AutomationWorkflow(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
):
    automation = models.ForeignKey(
        "automation.Automation", on_delete=models.CASCADE, related_name="workflows"
    )

    name = models.CharField(max_length=WORKFLOW_NAME_MAX_LEN)

    order = models.PositiveIntegerField()

    def get_parent(self):
        return self.automation

    @classmethod
    def get_last_order(cls, automation: "Automation"):
        queryset = AutomationWorkflow.objects.filter(automation=automation)
        return cls.get_highest_order_of_queryset(queryset) + 1
