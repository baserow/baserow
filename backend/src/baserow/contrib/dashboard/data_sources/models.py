from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models

from baserow.core.mixins import (
    FractionOrderableMixin,
    HierarchicalModelMixin,
    TrashableModelMixin,
)
from baserow.core.models import Service

if TYPE_CHECKING:
    from baserow.contrib.dashboard.models import Dashboard


class DashboardDataSource(
    HierarchicalModelMixin,
    TrashableModelMixin,
    FractionOrderableMixin,
    models.Model,
):
    """
    A data source is a link between a dashboard and a service.
    """

    name = models.CharField(
        blank=True,
        max_length=255,
        default="",
        help_text="Human name for this data source.",
    )
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=Decimal("1"),
    )
    dashboard = models.ForeignKey(
        "dashboard.Dashboard",
        on_delete=models.CASCADE,
        help_text="Dashboard this data source is linked to.",
    )
    service = models.OneToOneField(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        related_name="dashboard_data_source",
    )

    class Meta:
        ordering = ("order", "id")
        unique_together = [["dashboard", "name"]]

    def get_parent(self):
        return self.dashboard

    @classmethod
    def get_last_order(cls, dashboard: "Dashboard"):
        """
        Returns the last order for the given dashboard.

        :param Dashboard: The dashboard we want the order for.
        :return: The last order.
        """

        queryset = DashboardDataSource.objects.filter(dashboard=dashboard)
        return cls.get_highest_order_of_queryset(queryset)[0]
