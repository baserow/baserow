from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
)


class DashboardFilter(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    models.Model,
):
    """Shared filter configuration and selections for a dashboard."""

    class Mode(models.TextChoices):
        DROPDOWN = "dropdown", "Dropdown"
        INPUT = "input", "Input"

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"

    dashboard = models.ForeignKey(
        "dashboard.Dashboard", on_delete=models.CASCADE, related_name="filters"
    )
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(db_default=0)
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.TEXT)
    operator = models.CharField(max_length=32, default="equal")
    mode = models.CharField(max_length=32, choices=Mode.choices, default=Mode.DROPDOWN)
    multiple = models.BooleanField(default=False)
    formula_value = FormulaField(db_default="")
    values = models.JSONField(default=list, db_default=[])

    class Meta:
        ordering = ("order", "id")

    def get_parent(self):
        return self.dashboard
