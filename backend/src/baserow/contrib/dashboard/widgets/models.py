from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)

if TYPE_CHECKING:
    from baserow.contrib.dashboard.models import Dashboard


class Widget(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    FractionOrderableMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
    models.Model,
):
    """
    This model represents a dashboard widget. It displays
    information or something the user can interact with.
    """

    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    dashboard = models.ForeignKey("dashboard.Dashboard", on_delete=models.CASCADE)
    order = models.DecimalField(
        help_text="Lowest first.",
        max_digits=40,
        decimal_places=20,
        editable=False,
        default=Decimal("1"),
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="dashboard_widgets",
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ("order", "id")

    @staticmethod
    def get_type_registry():
        from .registries import widget_type_registry

        return widget_type_registry

    def get_parent(self):
        return self.dashboard

    @classmethod
    def get_last_order(
        cls,
        dashboard: "Dashboard",
    ):
        """
        Returns the last order for the given page.

        :param dashboard: The dashboard we want the order for.
        :param base_queryset: The base queryset to use.
        :return: The last order.
        """

        return cls.get_last_orders(dashboard)[0]

    @classmethod
    def get_last_orders(
        cls,
        dashboard: "Dashboard",
        amount=1,
    ):
        """
        Returns the last orders for the given dashboard.

        :param dashboard: The dashboard we want the order for.
        :param amount: The number of orders you wish to have returned
        :return: The last order.
        """

        queryset = Widget.objects.filter(dashboard=dashboard)
        return cls.get_highest_order_of_queryset(queryset, amount=amount)


class SummaryWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )
