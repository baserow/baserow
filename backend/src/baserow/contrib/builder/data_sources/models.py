from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.contrib.builder.mixins import BuilderInstanceWithFormulaMixin
from baserow.contrib.builder.pages.models import Page
from baserow.core.mixins import (
    FractionOrderableMixin,
    HierarchicalModelMixin,
    TrashableModelMixin,
)
from baserow.core.models import Service


def get_default_data_source_content_type():
    return ContentType.objects.get_for_model(DataSource)


class DataSource(
    HierarchicalModelMixin,
    TrashableModelMixin,
    FractionOrderableMixin,
    BuilderInstanceWithFormulaMixin,
    models.Model,
):
    """
    A data source is a link between a page and a service that provides data. It expose
    this data to the related page for formula interpretation.
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
        default=1,
    )
    page = models.ForeignKey(
        Page, on_delete=models.CASCADE, help_text="Page this data source is linked to."
    )
    service = models.OneToOneField(
        Service, on_delete=models.SET_NULL, null=True, related_name="data_source"
    )

    class Meta:
        ordering = ("page_id", "order", "id")
        unique_together = [["page", "name"]]
        indexes = [
            models.Index(fields=["page_id", "order", "id"]),
        ]

    def get_parent(self):
        return self.page

    @classmethod
    def get_last_order(cls, page: Page):
        """
        Returns the last order for the given page.

        :param page: The page we want the order for.
        :return: The last order.
        """

        queryset = DataSource.objects.filter(page=page)
        return cls.get_highest_order_of_queryset(queryset)[0]

    @classmethod
    def get_unique_order_before_data_source(cls, before: "DataSource"):
        """
        Returns a safe order value before the given element in the given page.

        :param page: The page we want the order for.
        :param before: The element before which we want the safe order
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: The order value.
        """

        queryset = DataSource.objects.filter(page=before.page)
        return cls.get_unique_orders_before_item(before, queryset)[0]

    def formula_generator(self, instance: "DataSource"):
        """
        Yield the formulas from the current data source instance and from the underlying
        service if it exists.
        """

        yield from super().formula_generator(instance)

        service = instance.service.specific if instance.service else None

        # The Data Source's service can be None if the user created a Data
        # Source but didn't finish configuring it.
        if service:
            yield from service.get_type().formula_generator(service)
